"""사용 탭 — RAG 실행 전용. (Phase 4~6에서 상세 구현)"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QSplitter,
    QLabel,
)
from PySide6.QtCore import Qt


class TabUsage(QWidget):
    """사용 탭 스켈레톤 — 모델 관리, 질문/검색, 검색 결과, 답변, 출처."""

    def __init__(self, app_state: dict | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = app_state or {}

        layout = QVBoxLayout(self)

        # 모델 관리 영역 (Phase 4)
        group_model = QGroupBox("모델 관리")
        model_layout = QHBoxLayout(group_model)
        model_layout.addWidget(QLabel("(Phase 4에서 구현)"))
        model_layout.addStretch()
        layout.addWidget(group_model)

        # 질문 & 검색 영역 (Phase 4)
        group_query = QGroupBox("질문 & 검색")
        query_layout = QVBoxLayout(group_query)
        query_layout.addWidget(QLabel("(Phase 4에서 구현)"))
        layout.addWidget(group_query)

        # 좌: 검색 결과 / 우: 조합 컨텍스트 + 답변 (Phase 5)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        group_results = QGroupBox("검색 결과")
        results_layout = QVBoxLayout(group_results)
        results_layout.addWidget(QLabel("(Phase 5에서 구현)"))
        splitter.addWidget(group_results)

        group_context_answer = QGroupBox("조합 컨텍스트 / 답변")
        ctx_layout = QVBoxLayout(group_context_answer)
        ctx_layout.addWidget(QLabel("(Phase 5에서 구현)"))
        splitter.addWidget(group_context_answer)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

        # 출처 영역 (Phase 6)
        group_sources = QGroupBox("출처 (PDF 뷰어 연동)")
        sources_layout = QVBoxLayout(group_sources)
        sources_layout.addWidget(QLabel("(Phase 6에서 구현)"))
        layout.addWidget(group_sources)
