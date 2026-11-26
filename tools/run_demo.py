"""Launch the minimal HLA-MEM demo and wait until Ctrl+C.

Requires built frontends (`make web-build`) and installed Python packages
(`make install`).  Starts memory-graph, reasoning-orchestrator and one web server that
serves /conversation/ and /admin/; no Docker, model or database is required.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_STOP = False
WEB_MODULES = ("conversation-web", "admin-web")

SERVICES = [
    ("memory-graph", [sys.executable, "tools/run_module.py", "memory-graph"], {}, 8082),
    ("persona-state", [sys.executable, "tools/run_module.py", "persona-state"], {}, 8083),
    ("reasoning-orchestrator", [sys.executable, "tools/run_module.py", "reasoning-orchestrator"], {}, 8081),
    (
        "web",
        ["node", "tools/serve_web.mjs"],
        {
            "PORT": "4173",
            "ORCHESTRATOR_URL": "http://127.0.0.1:8081",
            "PERSONA_URL": "http://127.0.0.1:8083",
        },
        4173,
    ),
]


def _healthy(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/internal/health", timeout=1) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _wait_ready(port: int, timeout: float = 25.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _healthy(port):
            return True
        time.sleep(0.4)
    return False


def _stop(processes: list[subprocess.Popen]) -> None:
    for process in processes:
        if process.poll() is None:
            process.terminate()
    for process in processes:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


def main() -> int:
    missing = [
        module for module in WEB_MODULES if not (ROOT / "modules" / module / "web" / "dist" / "index.html").is_file()
    ]
    if missing:
        print(f"frontend build missing for: {', '.join(missing)}", file=sys.stderr)
        print("run: make web-build", file=sys.stderr)
        return 2

    processes: list[subprocess.Popen] = []
    try:
        for name, command, extra_env, _ in SERVICES:
            env = {**os.environ, **extra_env}
            process = subprocess.Popen(command, cwd=ROOT, env=env)
            processes.append(process)
            print(f"[start] {name} (pid {process.pid})")

        for name, _, _, port in SERVICES:
            if not _wait_ready(port):
                print(f"[fail] {name} did not become healthy on port {port}", file=sys.stderr)
                return 1

        print("")
        print("HLA-MEM minimal demo")
        print("  conversation: http://127.0.0.1:4173/conversation/")
        print("  admin:        http://127.0.0.1:4173/admin/")
        print("  orchestrator: http://127.0.0.1:8081/docs")
        print("  memory:       http://127.0.0.1:8082/docs")
        print("  persona:      http://127.0.0.1:8083/docs")
        print("")
        print("Try: 我最近在喝龙井，喜欢清淡的茶。  ->  我喜欢什么茶？")
        print("Admin -> 模型设置 saves an OpenAI-compatible endpoint; 人格/提案审批 edits persona-state.")
        print("Press Ctrl+C to stop.")
        while not _STOP:
            for process, (name, _, _, _) in zip(processes, SERVICES, strict=True):
                if process.poll() is not None:
                    print(f"[exit] {name} stopped with code {process.returncode}", file=sys.stderr)
                    return 1
            time.sleep(0.5)
        print("\n[stop] shutting down")
        return 0
    finally:
        _stop(processes)


def _handle_stop(signum: int, frame: object) -> None:
    global _STOP
    _STOP = True


if __name__ == "__main__":
    signal.signal(signal.SIGINT, _handle_stop)
    signal.signal(signal.SIGTERM, _handle_stop)
    raise SystemExit(main())
