"""Phase 2 검증: ServerManager start/stop, log callback."""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.server.server_manager import ServerManager


def main():
    logs = []
    def on_log(line: str):
        logs.append(line)
        print(f"[LOG] {line}")

    mgr = ServerManager()
    mgr.set_log_callback(on_log)

    print("1. start(127.0.0.1, 8081)...")
    ok = mgr.start("127.0.0.1", 8081)
    assert ok, "start should return True"
    print("   OK")

    print("2. is_running()...")
    assert mgr.is_running(), "is_running should be True"
    print("   OK")

    print("3. Waiting for Uvicorn log (5s)...")
    import time
    time.sleep(5)
    has_uvicorn = any("Uvicorn" in l or "Started" in l for l in logs)
    print(f"   Logs received: {len(logs)}, has Uvicorn: {has_uvicorn}")

    print("4. stop()...")
    ok = mgr.stop()
    assert ok, "stop should return True"
    print("   OK")

    print("5. is_running() after stop...")
    assert not mgr.is_running(), "is_running should be False"
    print("   OK")

    print("\nPhase 2 ServerManager 검증 완료.")


if __name__ == "__main__":
    main()
