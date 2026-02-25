"""Uvicorn 서브프로세스 제어 — 시작/중단, 로그 파이프."""

from __future__ import annotations

import sys
import os
import time
import threading
import subprocess
from pathlib import Path
from typing import Callable

# 프로젝트 루트
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ServerManager:
    """Uvicorn 서버 서브프로세스 제어 및 로그 수신."""

    def __init__(self) -> None:
        self._process: subprocess.Popen | None = None
        self._log_callback: Callable[[str], None] | None = None
        self._reader_thread: threading.Thread | None = None
        self._stop_reader = threading.Event()

    def set_log_callback(self, callback: Callable[[str], None] | None) -> None:
        """로그 수신 콜백 등록. 매 라인(str)이 호출됨."""
        self._log_callback = callback

    def _emit_log(self, line: str) -> None:
        if self._log_callback and line.strip():
            try:
                self._log_callback(line.rstrip())
            except Exception:
                pass

    def _read_stream(self, stream) -> None:
        """서브프로세스 stdout/stderr에서 라인 읽어 콜백 호출."""
        try:
            for line in iter(stream.readline, ""):
                if self._stop_reader.is_set():
                    break
                self._emit_log(line)
        except (ValueError, OSError):
            pass
        finally:
            try:
                stream.close()
            except Exception:
                pass

    def start(self, host: str = "127.0.0.1", port: int = 8081) -> bool:
        """
        Uvicorn 서버 서브프로세스 시작.

        Returns:
            True: 시작 성공, False: 이미 실행 중이거나 시작 실패
        """
        if self._process is not None and self._process.poll() is None:
            return False  # 이미 실행 중

        self._stop_reader.clear()
        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "src.server.api_server:app",
            "--host",
            host,
            "--port",
            str(port),
        ]
        # Windows 한글 환경: 자식 프로세스 출력을 UTF-8로 고정 (한글 깨짐 방지)
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        kwargs: dict = {
            "cwd": str(PROJECT_ROOT),
            "env": env,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
        }
        if sys.platform == "win32" and hasattr(subprocess, "CREATE_NO_WINDOW"):
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        try:
            self._process = subprocess.Popen(cmd, **kwargs)
        except OSError as e:
            self._emit_log(f"[ERROR] 서버 시작 실패: {e}")
            return False
        except Exception as e:
            self._emit_log(f"[ERROR] 서버 시작 실패: {e}")
            return False

        # 포트 충돌 등으로 즉시 종료된 경우
        if self._process.poll() is not None:
            self._emit_log("[ERROR] 서버가 즉시 종료되었습니다. (포트 사용 중일 수 있음)")
            self._process = None
            return False

        # 바인드 실패(10048 등)는 uvicorn 시작 후 수 초 내에 발생 → 잠시 대기 후 재확인
        time.sleep(2.0)
        if self._process.poll() is not None:
            self._emit_log(
                "[ERROR] 서버가 종료되었습니다. 포트가 이미 사용 중인지 확인하세요. (다른 포트 시도 또는 기존 프로세스 종료)"
            )
            self._process = None
            return False

        self._reader_thread = threading.Thread(
            target=self._read_stream,
            args=(self._process.stdout,),
            daemon=True,
        )
        self._reader_thread.start()
        return True

    def stop(self) -> bool:
        """
        서버 서브프로세스 종료.

        Returns:
            True: 종료 성공 또는 이미 중지됨, False: 종료 실패
        """
        if self._process is None:
            return True

        self._stop_reader.set()
        try:
            self._process.terminate()
            self._process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                self._process.kill()
                self._process.wait(timeout=2)
            except Exception:
                pass
        except Exception:
            pass
        finally:
            self._process = None
            self._reader_thread = None

        return True

    def is_running(self) -> bool:
        """서버 실행 여부."""
        if self._process is None:
            return False
        return self._process.poll() is None
