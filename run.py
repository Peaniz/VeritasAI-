#!/usr/bin/env python
"""
Start all backend microservices.

    cd backend/
    uv run python run.py
"""
import os
import signal
import subprocess
import sys
import threading
from pathlib import Path

# Fix Windows terminal Unicode encoding
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

BASE = Path(__file__).parent / "services"

SERVICES = [
    {"name": "auth-service",      "port": 8001, "color": "\033[94m"},   # blue
    {"name": "ai-service",        "port": 8002, "color": "\033[92m"},   # green
    {"name": "document-service",  "port": 8003, "color": "\033[93m"},   # yellow
    {"name": "analytics-service", "port": 8004, "color": "\033[95m"},   # magenta
]
RESET = "\033[0m"
BOLD  = "\033[1m"

processes: list[subprocess.Popen] = []


def load_dotenv(path: Path) -> dict[str, str]:
    """Parse a .env file into a dict (no external dependency needed)."""
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        result[key.strip()] = value.strip()
    return result


def free_port(port: int) -> None:
    """Kill any process holding the given TCP port (Windows)."""
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True
        )
        for line in result.stdout.splitlines():
            if f":{port} " in line and "LISTENING" in line:
                parts = line.split()
                pid = int(parts[-1])
                if pid > 0:
                    subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                                   capture_output=True)
    except Exception:
        pass


def stream(proc: subprocess.Popen, label: str, color: str) -> None:
    prefix = f"{color}{BOLD}[{label}]{RESET} "
    for line in iter(proc.stdout.readline, b""):
        sys.stdout.write(prefix + line.decode(errors="replace"))
        sys.stdout.flush()


def start_service(svc: dict) -> subprocess.Popen | None:
    svc_dir = BASE / svc["name"]
    if not svc_dir.exists():
        print(f"  ⚠  {svc['name']} directory not found, skipping")
        return None

    env = {**os.environ, **load_dotenv(svc_dir / ".env"), "PYTHONUNBUFFERED": "1"}
    cmd = [
        "uv", "run", "uvicorn", "main:app",
        "--host", "0.0.0.0",
        "--port", str(svc["port"]),
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=svc_dir,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    t = threading.Thread(target=stream, args=(proc, svc["name"], svc["color"]), daemon=True)
    t.start()
    return proc


def shutdown(sig=None, frame=None) -> None:
    print(f"\n{BOLD}Stopping all services...{RESET}")
    for p in processes:
        if p and p.poll() is None:
            p.terminate()
    for p in processes:
        if p:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print(f"{BOLD}Starting Veritas backend services...{RESET}\n")
    for svc in SERVICES:
        print(f"  - {svc['color']}{svc['name']}{RESET}  http://localhost:{svc['port']}")
        free_port(svc["port"])
        proc = start_service(svc)
        if proc:
            processes.append(proc)
    print()

    # Wait — exit if all processes die
    while True:
        alive = [p for p in processes if p.poll() is None]
        if not alive:
            print("All services stopped.")
            break
        threading.Event().wait(1)

