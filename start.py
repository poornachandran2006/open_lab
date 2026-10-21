"""
GridGuard Master Orchestrator (start.py)
Starts all 3 system services concurrently:
1. FastAPI Backend (uvicorn backend:app on port 8000)
2. React Dashboard (npm run dev on port 3000)
3. Disturbance Injector (python injector.py)

Automatically opens your browser to http://localhost:3000.
Handles graceful shutdown of all services on Ctrl+C.
"""

import os
import sys
import time
import socket
import subprocess
import webbrowser
import signal

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

def is_port_open(port: int, host: str = "localhost") -> bool:
    """Checks whether a TCP port is currently listening."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        return s.connect_ex((host, port)) == 0

def wait_for_port(port: int, service_name: str, timeout: int = 15) -> bool:
    """Waits until a port starts listening."""
    print(f"Waiting for {service_name} on port {port}...", end="", flush=True)
    start_time = time.time()
    while time.time() - start_time < timeout:
        if is_port_open(port):
            print(" [OK]")
            return True
        print(".", end="", flush=True)
        time.sleep(0.5)
    print(" [TIMEOUT]")
    return False

def main():
    print("=" * 60)
    print("        GridGuard Master Service Orchestrator")
    print("=" * 60)
    print()

    # 1. Check MQTT broker
    if is_port_open(1883):
        print("[MQTT] Mosquitto broker is ACTIVE on localhost:1883 [OK]")
    else:
        print("[WARNING] No broker detected on port 1883.")
        print("          Please ensure Mosquitto is running for live MQTT streaming.\n")

    processes = []

    try:
        # 2. Launch FastAPI Backend
        print("[1/3] Launching FastAPI Backend...")
        backend_proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "backend:app", "--host", "0.0.0.0", "--port", "8000"],
            cwd=PROJECT_DIR
        )
        processes.append(("Backend", backend_proc))

        # Wait until port 8000 responds
        wait_for_port(8000, "FastAPI Backend", timeout=12)

        # 3. Launch React Frontend
        print("[2/3] Launching React Dashboard (Vite)...")
        # On Windows, npm is npm.cmd
        npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
        frontend_proc = subprocess.Popen(
            [npm_cmd, "run", "dev"],
            cwd=PROJECT_DIR
        )
        processes.append(("Frontend", frontend_proc))

        # Wait until port 3000 responds
        wait_for_port(3000, "React Dashboard", timeout=15)

        # 4. Launch Disturbance Injector
        print("[3/3] Launching Disturbance Injector (ESP32 Simulator)...")
        injector_proc = subprocess.Popen(
            [sys.executable, "injector.py"],
            cwd=PROJECT_DIR
        )
        processes.append(("Injector", injector_proc))

        print()
        print("=" * 60)
        print(" All GridGuard components are running!")
        print(" - React Dashboard: http://localhost:3000")
        print(" - FastAPI Backend: http://localhost:8000")
        print(" - WebSocket Stream: ws://localhost:8000/ws")
        print(" - Press Ctrl+C in this terminal to stop everything cleanly")
        print("=" * 60)
        print()

        # Open Dashboard in default web browser
        time.sleep(1)
        webbrowser.open("http://localhost:3000")

        # Keep running and monitor processes
        while True:
            for name, proc in processes:
                poll = proc.poll()
                if poll is not None:
                    print(f"Notice: {name} process exited with code {poll}")
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n\nShutting down all GridGuard services...")
    finally:
        for name, proc in processes:
            print(f"Stopping {name} (PID {proc.pid})...")
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        print("All GridGuard services stopped cleanly.")

if __name__ == "__main__":
    main()
