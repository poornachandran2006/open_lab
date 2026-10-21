"""
GridGuard Disturbance Injector (ESP32 Simulator)
Simulates dual-line feature extraction and MQTT publishing:
- Line B: Cycles through all 8 IEEE 1159 disturbance classes with 3s intervals
- Line A: Continuous clean reference (Normal) published alongside Line B

Topics:
- gridguard/line_b/features
- gridguard/line_a/features
Broker: localhost:1883
"""

import sys
import time
import json
import paho.mqtt.client as mqtt

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# MQTT Configuration
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
TOPIC_LINE_A = "gridguard/line_a/features"
TOPIC_LINE_B = "gridguard/line_b/features"

# Normal reference feature vector for Line A
NORMAL_VECTOR = [0.707, 1.414, 0.003, 0.001]

# 8 IEEE 1159 disturbance classes and their representative feature vectors
DISTURBANCES = [
    {"class": "Normal",              "features": [0.707, 1.414, 0.003, 0.001]},
    {"class": "Voltage Sag",         "features": [0.450, 1.850, 0.067, 0.008]},
    {"class": "Voltage Swell",       "features": [0.900, 1.700, 0.033, 0.003]},
    {"class": "Interruption",        "features": [0.050, 2.100, 0.170, 0.027]},
    {"class": "Flicker",             "features": [0.720, 1.650, 0.005, 0.001]},
    {"class": "Transient Spike",     "features": [0.741, 3.100, 0.100, 0.066]},
    {"class": "Harmonic Distortion", "features": [0.740, 1.310, 0.308, 0.017]},
    {"class": "Notching",            "features": [0.692, 1.520, 0.137, 0.018]},
]

def format_vector(features: list) -> str:
    """Formats float list to [x.xxx, y.yyy, z.zzz, w.www] matching spec display."""
    return f"[{features[0]:.3f}, {features[1]:.3f}, {features[2]:.3f}, {features[3]:.3f}]"

def create_mqtt_client() -> mqtt.Client:
    """Creates a paho-mqtt client compatible with both v1 and v2 API versions."""
    try:
        from paho.mqtt.enums import CallbackAPIVersion
        client = mqtt.Client(CallbackAPIVersion.VERSION2)
    except (ImportError, AttributeError):
        client = mqtt.Client()
    return client

def main():
    client = create_mqtt_client()

    print(f"Connecting to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}...")
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    except Exception as e:
        print(f"Error: Could not connect to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}.")
        print(f"Details: {e}")
        print("Please ensure Mosquitto or an MQTT broker is running on localhost:1883.")
        sys.exit(1)

    client.loop_start()
    print("Connected successfully. Starting continuous disturbance injection loop (Ctrl+C to stop)...\n")

    try:
        iteration = 1
        while True:
            for item in DISTURBANCES:
                dist_name = item["class"]
                dist_features = item["features"]

                # 1. Publish Line B (Disturbed line)
                client.publish(TOPIC_LINE_B, json.dumps(dist_features), qos=0)
                print(f"[LINE B] Publishing: {dist_name} \u2192 {format_vector(dist_features)}")

                # 2. Publish Line A (Clean reference)
                client.publish(TOPIC_LINE_A, json.dumps(NORMAL_VECTOR), qos=0)
                print(f"[LINE A] Publishing: Normal \u2192 {format_vector(NORMAL_VECTOR)}")

                # Wait 3 seconds before next disturbance
                time.sleep(3)

            iteration += 1

    except KeyboardInterrupt:
        print("\n\nInjection stopped by user (Ctrl+C). Disconnecting from MQTT broker...")
    finally:
        client.loop_stop()
        client.disconnect()
        print("Disconnected cleanly.")

if __name__ == "__main__":
    main()
