"""
GridGuard - Standalone MQTT Publisher / Testing Utility
Simulates the ESP32 publishing 4-element feature vectors [rms, crest_factor, thd, band_energy]
to 'gridguard/line_a/features' and 'gridguard/line_b/features', and monitors the returned
classification topics 'gridguard/line_a/class' and 'gridguard/line_b/class'.

Usage:
    python simulate_mqtt_publish.py
"""

import time
import json
import random
import paho.mqtt.client as mqtt

MQTT_BROKER = "localhost"
MQTT_PORT = 1883

TOPIC_A_FEAT = "gridguard/line_a/features"
TOPIC_B_FEAT = "gridguard/line_b/features"
TOPIC_A_CLASS = "gridguard/line_a/class"
TOPIC_B_CLASS = "gridguard/line_b/class"

# Sample disturbance feature vectors
DISTURBANCE_SAMPLES = [
    ("Normal", [1.00, 1.41, 0.02, 0.002]),
    ("Voltage Sag", [0.55, 1.40, 0.03, 0.005]),
    ("Voltage Swell", [1.35, 1.42, 0.03, 0.006]),
    ("Interruption", [0.05, 0.90, 0.04, 0.001]),
    ("Flicker", [1.02, 1.39, 0.04, 0.045]),
    ("Transient Spike", [1.15, 3.40, 0.08, 0.070]),
    ("Harmonic Distortion", [1.01, 1.41, 0.18, 0.025]),
    ("Notching", [0.96, 1.85, 0.12, 0.035]),
]

def on_connect(client, userdata, flags, rc, *args):
    print(f"[TEST CLIENT] Connected to broker at {MQTT_BROKER}:{MQTT_PORT}")
    client.subscribe([(TOPIC_A_CLASS, 0), (TOPIC_B_CLASS, 0)])
    print(f"[TEST CLIENT] Subscribed to {TOPIC_A_CLASS} and {TOPIC_B_CLASS}")

def on_message(client, userdata, msg):
    payload = msg.payload.decode("utf-8")
    print(f"\n<<< [ESP32 RECEIVED ON {msg.topic}]:\n{json.dumps(json.loads(payload), indent=2)}")

def main():
    try:
        from paho.mqtt.enums import CallbackAPIVersion
        client = mqtt.Client(CallbackAPIVersion.VERSION2)
    except Exception:
        client = mqtt.Client()

    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
    except Exception as e:
        print(f"Could not connect to MQTT broker at {MQTT_BROKER}:{MQTT_PORT} ({e}).")
        print("Please ensure Mosquitto or an MQTT broker is running on localhost:1883.")
        return

    client.loop_start()

    print("\n--- Publishing test disturbance vectors ---")
    try:
        for expected_class, vector in DISTURBANCE_SAMPLES:
            target_topic = TOPIC_B_FEAT if expected_class != "Normal" else TOPIC_A_FEAT
            line_label = "Line B" if target_topic == TOPIC_B_FEAT else "Line A"
            
            print(f"\n>>> Publishing {expected_class} simulation to {line_label} ({target_topic}): {vector}")
            client.publish(target_topic, json.dumps(vector))
            time.sleep(1.5)
    except KeyboardInterrupt:
        print("\nSimulation stopped.")
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()
