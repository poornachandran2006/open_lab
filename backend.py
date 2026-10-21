"""
GridGuard Backend - AI-Powered Power Quality Monitor & Protector
FastAPI + Paho-MQTT + Joblib + Scikit-Learn + WebSockets

Key Functions:
1. Loads pre-trained Random Forest model (gridguard_rf_model_combined.pkl) using joblib on startup.
2. Subscribes to MQTT topics:
   - gridguard/line_a/features
   - gridguard/line_b/features
   Payload: JSON array of 4 floats: [rms, crest_factor, thd, band_energy]
3. Runs inference mapping prediction (0-7) to IEEE 1159 classes:
   [Normal, Voltage Sag, Voltage Swell, Interruption, Flicker, Transient Spike, Harmonic Distortion, Notching]
4. Evaluates severity & relay action:
   - Normal -> severity: "normal", relay_action: "HOLD"
   - Voltage Sag, Voltage Swell, Flicker -> severity: "warning", relay_action: "TRIP"
   - Transient Spike, Harmonic Distortion, Interruption, Notching -> severity: "critical", relay_action: "TRIP"
5. Publishes result back to MQTT:
   - gridguard/line_a/class or gridguard/line_b/class as JSON
6. Broadcasts result to WebSocket clients at /ws using asyncio
7. Maintains in-memory event log (last 100 events) accessible via GET /events
"""

import os
import json
import asyncio
import logging
from datetime import datetime
from collections import deque
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional

import joblib
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import paho.mqtt.client as mqtt

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("GridGuard")

# ---------------------------------------------------------
# CONSTANTS & CONFIGURATION
# ---------------------------------------------------------
MODEL_PATH = os.getenv("GRIDGUARD_MODEL_PATH", "gridguard_rf_model_combined.pkl")
MQTT_BROKER = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
MQTT_KEEPALIVE = 60

# IEEE 1159 Disturbance Classes (labels 0-7 in exact specified order)
CLASS_NAMES = [
    "Normal",                # 0
    "Voltage Sag",           # 1
    "Voltage Swell",         # 2
    "Interruption",          # 3
    "Flicker",               # 4
    "Transient Spike",       # 5
    "Harmonic Distortion",   # 6
    "Notching"               # 7
]

# MQTT Topics
TOPIC_LINE_A_FEATURES = "gridguard/line_a/features"
TOPIC_LINE_B_FEATURES = "gridguard/line_b/features"
TOPIC_LINE_A_CLASS = "gridguard/line_a/class"
TOPIC_LINE_B_CLASS = "gridguard/line_b/class"

# In-memory storage (thread-safe deque for last 100 events)
event_log: deque = deque(maxlen=100)

# Global runtime state
model: Any = None
mqtt_client: Optional[mqtt.Client] = None
main_loop: Optional[asyncio.AbstractEventLoop] = None
is_mqtt_connected: bool = False

# ---------------------------------------------------------
# WEBSOCKET CONNECTION MANAGER
# ---------------------------------------------------------
class ConnectionManager:
    """Thread-safe WebSocket manager for real-time dashboard broadcasting."""
    def __init__(self):
        self.active_connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)
        logger.info(f"WebSocket client connected. Active connections: {len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            self.active_connections.discard(websocket)
        logger.info(f"WebSocket client disconnected. Active connections: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast JSON message to all connected clients."""
        async with self._lock:
            recipients = list(self.active_connections)

        if not recipients:
            return

        dead_connections = []
        for connection in recipients:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to client: {e}. Marking for cleanup.")
                dead_connections.append(connection)

        if dead_connections:
            async with self._lock:
                for dead in dead_connections:
                    self.active_connections.discard(dead)

ws_manager = ConnectionManager()

# ---------------------------------------------------------
# BUSINESS LOGIC & INFERENCE
# ---------------------------------------------------------
def determine_severity_and_relay(classification: str) -> tuple[str, str]:
    """
    Applies GridGuard severity and relay actuation rules:
    - Normal -> severity: "normal", relay_action: "HOLD"
    - Voltage Sag, Voltage Swell, Flicker -> severity: "warning", relay_action: "TRIP"
    - Transient Spike, Harmonic Distortion, Interruption, Notching -> severity: "critical", relay_action: "TRIP"
    """
    if classification == "Normal":
        return "normal", "HOLD"
    elif classification in ("Voltage Sag", "Voltage Swell", "Flicker"):
        return "warning", "TRIP"
    elif classification in ("Transient Spike", "Harmonic Distortion", "Interruption", "Notching"):
        return "critical", "TRIP"
    else:
        # Fallback for unexpected classification
        logger.warning(f"Unrecognized class '{classification}', defaulting to critical trip.")
        return "critical", "TRIP"

def run_inference(features: List[float]) -> str:
    """
    Runs model inference on [rms, crest_factor, thd, band_energy]
    and maps the resulting integer label to one of the 8 IEEE 1159 class names.
    """
    global model
    if model is None:
        raise RuntimeError("Model is not loaded.")

    feature_array = np.array(features, dtype=float).reshape(1, -1)
    raw_pred = model.predict(feature_array)[0]

    # Handle numeric label (0-7)
    try:
        label_idx = int(raw_pred)
        if 0 <= label_idx < len(CLASS_NAMES):
            return CLASS_NAMES[label_idx]
    except (ValueError, TypeError):
        pass

    # If the model already returned a string matching our classes
    if str(raw_pred) in CLASS_NAMES:
        return str(raw_pred)

    raise ValueError(f"Inference output '{raw_pred}' cannot be mapped to GridGuard classes.")

def process_feature_vector(line: str, features_list: List[float]) -> Dict[str, Any]:
    """
    Core pipeline:
    1. Validates and unpacks [rms, crest_factor, thd, band_energy]
    2. Runs RF inference
    3. Calculates severity and relay action
    4. Constructs standard event dictionary
    5. Dispatches to WebSocket broadcast, MQTT publish, and in-memory log
    """
    if len(features_list) < 4:
        raise ValueError(f"Feature vector must contain 4 floats, got {len(features_list)}")

    rms, crest_factor, thd, band_energy = [float(v) for v in features_list[:4]]

    # 1. Run inference
    classification = run_inference([rms, crest_factor, thd, band_energy])

    # 2. Compute severity and relay action
    severity, relay_action = determine_severity_and_relay(classification)

    # 3. Format timestamp (e.g. '2026-10-13T19:03:00')
    timestamp = datetime.now().isoformat(timespec="seconds")

    # 4. Construct payload matching exact specification
    event_data = {
        "line": line.upper(),
        "classification": classification,
        "features": {
            "rms": round(rms, 4),
            "crest_factor": round(crest_factor, 4),
            "thd": round(thd, 4),
            "band_energy": round(band_energy, 4)
        },
        "severity": severity,
        "relay_action": relay_action,
        "timestamp": timestamp
    }

    # 5. Append to in-memory event log (capped at 100)
    event_log.append(event_data)

    # 6. Publish classification result back to MQTT
    publish_topic = TOPIC_LINE_A_CLASS if line.upper() == "A" else TOPIC_LINE_B_CLASS
    if mqtt_client is not None and is_mqtt_connected:
        try:
            mqtt_client.publish(publish_topic, json.dumps(event_data), qos=0)
            logger.info(f"Published inference result to {publish_topic}: {classification} ({relay_action})")
        except Exception as e:
            logger.error(f"Failed to publish to MQTT topic {publish_topic}: {e}")

    # 7. Asynchronously broadcast to WebSocket clients
    if main_loop is not None and main_loop.is_running():
        asyncio.run_coroutine_threadsafe(ws_manager.broadcast(event_data), main_loop)

    return event_data

# ---------------------------------------------------------
# MQTT CLIENT CALLBACKS & SETUP
# ---------------------------------------------------------
def on_mqtt_connect(client, userdata, flags, rc, *args):
    """Callback triggered when MQTT broker connects."""
    global is_mqtt_connected
    # Check for success in both paho-mqtt v1 (int) and v2 (ReasonCode)
    is_success = (rc == 0) or (hasattr(rc, "is_failure") and not rc.is_failure)
    if is_success:
        is_mqtt_connected = True
        logger.info(f"Connected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
        # Subscribe to both line features topics
        client.subscribe([(TOPIC_LINE_A_FEATURES, 0), (TOPIC_LINE_B_FEATURES, 0)])
        logger.info(f"Subscribed to topics: {TOPIC_LINE_A_FEATURES}, {TOPIC_LINE_B_FEATURES}")
    else:
        is_mqtt_connected = False
        logger.error(f"MQTT connection failed with reason code: {rc}")

def on_mqtt_disconnect(client, userdata, *args):
    """Callback triggered on disconnect."""
    global is_mqtt_connected
    is_mqtt_connected = False
    logger.warning("Disconnected from MQTT broker. Auto-reconnecting in background...")

def on_mqtt_message(client, userdata, msg):
    """
    Handles incoming MQTT message from ESP32:
    - Topic: gridguard/line_a/features or gridguard/line_b/features
    - Payload: JSON array of 4 floats [rms, crest_factor, thd, band_energy]
    """
    topic = msg.topic
    try:
        payload_str = msg.payload.decode("utf-8").strip()
        data = json.loads(payload_str)

        # Identify line
        if topic == TOPIC_LINE_A_FEATURES or "line_a" in topic:
            line = "A"
        elif topic == TOPIC_LINE_B_FEATURES or "line_b" in topic:
            line = "B"
        else:
            logger.warning(f"Ignored message on unrecognized topic: {topic}")
            return

        # Parse feature vector
        if isinstance(data, list):
            features_list = data
        elif isinstance(data, dict):
            # Fallback in case features are keyed as a dictionary
            features_list = [
                data.get("rms", 0.0),
                data.get("crest_factor", 0.0),
                data.get("thd", 0.0),
                data.get("band_energy", 0.0)
            ]
        else:
            logger.error(f"Unexpected JSON format from {topic}: {data}")
            return

        # Execute classification pipeline
        event = process_feature_vector(line, features_list)
        logger.info(
            f"[MQTT INGEST] Line {event['line']} | {event['classification']} | "
            f"Severity: {event['severity']} | Relay: {event['relay_action']}"
        )

    except Exception as e:
        logger.error(f"Error processing MQTT message on topic {topic}: {e}", exc_info=True)

def setup_mqtt() -> mqtt.Client:
    """Initializes Paho MQTT client supporting both v1 and v2 API versions."""
    try:
        from paho.mqtt.enums import CallbackAPIVersion
        client = mqtt.Client(CallbackAPIVersion.VERSION2)
    except (ImportError, AttributeError):
        client = mqtt.Client()

    client.on_connect = on_mqtt_connect
    client.on_disconnect = on_mqtt_disconnect
    client.on_message = on_mqtt_message
    return client

# ---------------------------------------------------------
# FASTAPI LIFESPAN (STARTUP & SHUTDOWN)
# ---------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global model, mqtt_client, main_loop

    # 1. Capture running asyncio event loop for thread-safe cross-thread scheduling
    main_loop = asyncio.get_running_loop()

    # 2. Load pre-trained Random Forest model
    if os.path.exists(MODEL_PATH):
        try:
            model = joblib.load(MODEL_PATH)
            logger.info(f"Loaded Random Forest model from '{MODEL_PATH}'.")
        except Exception as e:
            logger.error(f"Failed to load model from '{MODEL_PATH}': {e}", exc_info=True)
            raise
    else:
        err_msg = (
            f"Pre-trained model file '{MODEL_PATH}' not found! "
            f"Please ensure '{MODEL_PATH}' exists or run create_dummy_model.py."
        )
        logger.error(err_msg)
        raise FileNotFoundError(err_msg)

    # 3. Start MQTT client background loop
    mqtt_client = setup_mqtt()
    try:
        # connect_async ensures non-blocking startup even if broker is booting
        mqtt_client.connect_async(MQTT_BROKER, MQTT_PORT, keepalive=MQTT_KEEPALIVE)
        mqtt_client.loop_start()
        logger.info(f"MQTT client background thread started (target: {MQTT_BROKER}:{MQTT_PORT}).")
    except Exception as e:
        logger.warning(f"Initial MQTT broker connection attempt failed: {e}. Will retry automatically.")

    yield

    # Shutdown: cleanly terminate MQTT loop
    if mqtt_client is not None:
        logger.info("Stopping MQTT background thread...")
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        logger.info("MQTT client disconnected successfully.")

# ---------------------------------------------------------
# FASTAPI APPLICATION & ROUTES
# ---------------------------------------------------------
app = FastAPI(
    title="GridGuard Power Quality AI Backend",
    description="Backend API & WebSocket server for dual-line power quality disturbance monitoring and load protection.",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for React dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic schemas for simulation / manual testing
class SimulationRequest(BaseModel):
    line: str = Field(default="A", description="Line identifier ('A' or 'B')")
    features: List[float] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="[rms, crest_factor, thd, band_energy]",
        examples=[[0.57, 1.83, 0.06, 0.008]]
    )

@app.get("/")
def root():
    """Health and basic information endpoint."""
    return {
        "project": "GridGuard",
        "description": "AI-Powered Power Quality Monitor & Protector",
        "status": "online",
        "model_loaded": model is not None,
        "mqtt_connected": is_mqtt_connected,
        "active_ws_clients": len(ws_manager.active_connections),
        "total_events_logged": len(event_log)
    }

@app.get("/events")
def get_events():
    """
    Maintains an in-memory event log (last 100 events).
    Returns list of logged events in reverse chronological order (newest first).
    """
    return list(reversed(event_log))

@app.get("/status")
def get_status():
    """Returns detailed system diagnostics for the dashboard."""
    return {
        "model": {
            "path": MODEL_PATH,
            "loaded": model is not None,
            "classes": CLASS_NAMES
        },
        "mqtt": {
            "broker": f"{MQTT_BROKER}:{MQTT_PORT}",
            "connected": is_mqtt_connected,
            "topics": {
                "subscribe": [TOPIC_LINE_A_FEATURES, TOPIC_LINE_B_FEATURES],
                "publish": [TOPIC_LINE_A_CLASS, TOPIC_LINE_B_CLASS]
            }
        },
        "websockets": {
            "active_clients": len(ws_manager.active_connections)
        },
        "events_in_memory": len(event_log)
    }

@app.post("/simulate")
def simulate_inference(req: SimulationRequest):
    """
    Helper endpoint for testing without live MQTT broker or hardware:
    Takes 4 features, runs model, updates event log, and broadcasts to WebSocket clients.
    """
    line = req.line.upper()
    if line not in ("A", "B"):
        raise HTTPException(status_code=400, detail="Line must be 'A' or 'B'")

    try:
        result = process_feature_vector(line, req.features)
        return result
    except Exception as e:
        logger.error(f"Simulation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time live disturbance streaming to the React dashboard.
    Emits JSON events formatted as:
    {
      "line": "A",
      "classification": "Voltage Sag",
      "features": { "rms": 0.57, "crest_factor": 1.83, "thd": 0.06, "band_energy": 0.008 },
      "severity": "warning",
      "relay_action": "TRIP",
      "timestamp": "2026-10-13T19:03:00"
    }
    """
    await ws_manager.connect(websocket)
    try:
        # Keep socket open and accept potential keepalive / messages from frontend
        while True:
            data = await websocket.receive_text()
            # Respond to client ping or commands if needed
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception as e:
        logger.warning(f"WebSocket client error: {e}")
        await ws_manager.disconnect(websocket)

# ---------------------------------------------------------
# MAIN RUNNER
# ---------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    # Run uvicorn server
    uvicorn.run("backend:app", host="0.0.0.0", port=8000, reload=False)
