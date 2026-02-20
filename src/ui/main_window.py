"""메인 윈도우 — QMainWindow + QTabWidget."""

import os

from PySide6.QtWidgets import (
    QMainWindow,
    QTabWidget,
    QWidget,
    QVBoxLayout,
)
from PySide6.QtCore import Qt

from src.ui.tabs.tab_usage import TabUsage
from src.ui.tabs.tab_db_create import TabDBCreate


def _default_output_dir() -> str:
    """프로젝트 루트 기준 output 디렉터리 경로."""
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "output")


class MainWindow(QMainWindow):
    """메인 윈도우 — V2 탭 2개(사용 탭, DB 생성 탭)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("RAG 워크벤치")
        self.setMinimumSize(640, 480)
        self.resize(800, 600)

        # 탭 간 공유 상태
        self.app_state: dict = {
            "pdf_paths": [],           # 선택된 PDF 파일 경로 리스트
            "doc_id": "",              # 문서 ID (자동 생성/수정 가능)
            "output_dir": _default_output_dir(),
            "after_toc": True,         # 차례 이후부터 처리 (기본 ON)
            "toc_preview": None,       # (toc_page, toc_ln, body_page, body_ln) 미리보기
            "extract_lines": [],       # 추출 결과 라인 리스트
            "parsed_lines": [],        # path가 붙은 파싱 결과 라인 리스트
        }

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.tabs = QTabWidget()
        self.tabs.addTab(TabUsage(self.app_state), "사용 탭")
        self.tabs.addTab(TabDBCreate(self.app_state), "DB 생성 탭")
        layout.addWidget(self.tabs)
