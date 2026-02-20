"""메인 윈도우 — QMainWindow + QTabWidget."""

import os

from PySide6.QtWidgets import (
    QMainWindow,
    QTabWidget,
    QWidget,
    QVBoxLayout,
)
from PySide6.QtCore import Qt

from src.ui.tabs.tab_import import TabImport
from src.ui.tabs.tab_extract import TabExtract
from src.ui.tabs.tab_parse import TabParse
from src.ui.tabs.tab_export import TabExport
from src.ui.tabs.tab_review import TabReview
from src.ui.tabs.tab_chunk import TabChunk
from src.ui.tabs.tab_embedding import TabEmbedding
from src.ui.tabs.tab_rag import TabRAG


def _default_output_dir() -> str:
    """프로젝트 루트 기준 output 디렉터리 경로."""
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "output")


class MainWindow(QMainWindow):
    """메인 윈도우 — 6개 탭(Import, Extract, Parse, Export, 검수, Chunk)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("PDF 규격문서 텍스트 추출")
        self.setMinimumSize(640, 480)
        self.resize(800, 600)

        # 탭 간 공유 상태
        self.app_state: dict = {
            "pdf_paths": [],           # 선택된 PDF 파일 경로 리스트
            "doc_id": "",              # 문서 ID (자동 생성/수정 가능)
            "output_dir": _default_output_dir(),
            "after_toc": True,         # 차례 이후부터 처리 (기본 ON)
            "toc_preview": None,       # Phase 4: (toc_page, toc_ln, body_page, body_ln) 미리보기
            "extract_lines": [],       # Phase 3: 추출 결과 라인 리스트
            "parsed_lines": [],        # Phase 5: path가 붙은 파싱 결과 라인 리스트
        }

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.tabs = QTabWidget()
        self.tabs.addTab(TabImport(self.app_state), "Import")
        self.tabs.addTab(TabExtract(self.app_state), "Extract")
        self.tabs.addTab(TabParse(self.app_state), "Parse")
        self.tabs.addTab(TabExport(self.app_state), "Export")
        self.tabs.addTab(TabReview(), "검수")
        self.tabs.addTab(TabChunk(self.app_state), "Chunk")
        self.tabs.addTab(TabEmbedding(self.app_state), "임베딩")
        self.tabs.addTab(TabRAG(self.app_state), "RAG")
        layout.addWidget(self.tabs)
