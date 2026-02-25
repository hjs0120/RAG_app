"""서버 서비스 탭 — API 서버 시작/중단, 설정, 실시간 로그."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QLineEdit,
    QSpinBox,
    QPlainTextEdit,
)

from src.server.server_manager import ServerManager


class TabServerService(QWidget):
    """서버 서비스 탭 — 호스트/포트 설정, 시작/중단, LED, 로그."""

    _log_signal = Signal(str)

    def __init__(self, app_state: dict | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._app_state = app_state or {}
        self._manager = ServerManager()
        self._manager.set_log_callback(self._on_log_from_thread)
        self._log_signal.connect(self._append_log)
        self._error_state = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # --- 서버 설정 ---
        group_config = QGroupBox("서버 설정")
        config_layout = QHBoxLayout(group_config)
        config_layout.addWidget(QLabel("호스트:"))
        self._edit_host = QLineEdit()
        self._edit_host.setText("127.0.0.1")
        self._edit_host.setMaximumWidth(150)
        config_layout.addWidget(self._edit_host)
        config_layout.addWidget(QLabel("포트:"))
        self._edit_port = QSpinBox()
        self._edit_port.setRange(1, 65535)
        self._edit_port.setValue(8081)
        self._edit_port.setMinimumWidth(90)
        self._edit_port.setMaximumWidth(100)
        config_layout.addWidget(self._edit_port)
        config_layout.addStretch()
        layout.addWidget(group_config)

        # --- 서버 제어 ---
        group_control = QGroupBox("서버 제어")
        control_layout = QHBoxLayout(group_control)
        self._btn_start = QPushButton("서버 시작")
        self._btn_start.clicked.connect(self._on_start)
        self._btn_start.setMinimumWidth(100)
        control_layout.addWidget(self._btn_start)
        self._btn_stop = QPushButton("서버 중단")
        self._btn_stop.clicked.connect(self._on_stop)
        self._btn_stop.setEnabled(False)
        self._btn_stop.setMinimumWidth(100)
        control_layout.addWidget(self._btn_stop)
        control_layout.addWidget(QLabel("상태:"))
        self._label_led = QLabel("●")
        self._label_led.setStyleSheet("color: #9ca3af; font-size: 14px; font-weight: bold;")
        self._label_led.setToolTip("회색=중지, 녹색=실행, 빨강=에러")
        control_layout.addWidget(self._label_led)
        self._label_status = QLabel("중지됨")
        self._label_status.setStyleSheet("color: #6b7280;")
        control_layout.addWidget(self._label_status)
        control_layout.addStretch()
        layout.addWidget(group_control)

        # --- 실시간 로그 ---
        group_log = QGroupBox("실시간 로그")
        log_layout = QVBoxLayout(group_log)
        self._log_edit = QPlainTextEdit()
        self._log_edit.setReadOnly(True)
        self._log_edit.setPlaceholderText("서버 로그가 여기에 출력됩니다.")
        self._log_edit.setMinimumHeight(200)
        log_layout.addWidget(self._log_edit)
        layout.addWidget(group_log)

    def _on_log_from_thread(self, line: str) -> None:
        """ServerManager 로그 콜백 (백그라운드 스레드). Signal로 메인 스레드에 전달."""
        self._log_signal.emit(line)

    def _append_log(self, line: str) -> None:
        """로그 창에 라인 추가 (앞에 시간 포함), 스크롤 하단 유지."""
        ts = datetime.now().strftime("%H:%M:%S")
        self._log_edit.appendPlainText(f"[{ts}] {line}")
        scrollbar = self._log_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _update_led(self, state: str) -> None:
        """LED 상태 업데이트: stopped | running | error."""
        if state == "running":
            self._label_led.setStyleSheet("color: #22c55e; font-size: 14px; font-weight: bold;")
            self._label_status.setText("실행 중")
        elif state == "error":
            self._label_led.setStyleSheet("color: #ef4444; font-size: 14px; font-weight: bold;")
            self._label_status.setText("에러")
        else:
            self._label_led.setStyleSheet("color: #9ca3af; font-size: 14px; font-weight: bold;")
            self._label_status.setText("중지됨")

    def _update_buttons(self, running: bool) -> None:
        """버튼 활성/비활성 상태."""
        self._btn_start.setEnabled(not running)
        self._edit_host.setEnabled(not running)
        self._edit_port.setEnabled(not running)
        self._btn_stop.setEnabled(running)

    def _on_start(self) -> None:
        host = self._edit_host.text().strip() or "127.0.0.1"
        port = self._edit_port.value()
        self._error_state = False
        self._append_log(f"[INFO] 서버 시작 시도: {host}:{port}")
        ok = self._manager.start(host=host, port=port)
        if ok:
            self._update_led("running")
            self._update_buttons(True)
            url = f"http://{host}:{port}"
            self._append_log(f"[INFO] API 서버 시작: {url}")
            self._app_state["server_running"] = True
            self._app_state["server_url"] = url
        else:
            self._update_led("error")
            self._error_state = True
            self._append_log("[ERROR] 서버가 이미 실행 중이거나 시작에 실패했습니다.")
            self._app_state["server_running"] = False
            self._app_state["server_url"] = None

    def _on_stop(self) -> None:
        self._append_log("[INFO] 서버 중단 중...")
        self._manager.stop()
        self._update_led("stopped")
        self._update_buttons(False)
        self._append_log("[INFO] 서버가 중지되었습니다. (모델 메모리 해제됨)")
        if self._app_state is not None:
            self._app_state["server_running"] = False
            self._app_state["server_url"] = None

    def is_server_running(self) -> bool:
        """서버 실행 여부."""
        return self._manager.is_running()
