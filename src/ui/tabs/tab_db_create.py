"""DB 생성 탭 — PDF→텍스트→Chunk→임베딩 파이프라인. (Phase 7에서 상세 구현)"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QScrollArea,
)
from PySide6.QtCore import Qt


class TabDBCreate(QWidget):
    """DB 생성 탭 스켈레톤 — Import, Extract, Parse, Chunk, Embedding 구역."""

    def __init__(self, app_state: dict | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = app_state or {}

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        layout = QVBoxLayout(content)

        # 1. PDF → 텍스트 추출
        group_import = QGroupBox("1. Import")
        imp_layout = QHBoxLayout(group_import)
        imp_layout.addWidget(QLabel("(Phase 7에서 구현)"))
        imp_layout.addStretch()
        layout.addWidget(group_import)

        group_extract = QGroupBox("2. Extract")
        ext_layout = QHBoxLayout(group_extract)
        ext_layout.addWidget(QLabel("(Phase 7에서 구현)"))
        ext_layout.addStretch()
        layout.addWidget(group_extract)

        group_parse = QGroupBox("3. Parse")
        parse_layout = QHBoxLayout(group_parse)
        parse_layout.addWidget(QLabel("(Phase 7에서 구현)"))
        parse_layout.addStretch()
        layout.addWidget(group_parse)

        group_review = QGroupBox("4. 검수")
        review_layout = QHBoxLayout(group_review)
        review_layout.addWidget(QLabel("(Phase 7에서 구현)"))
        review_layout.addStretch()
        layout.addWidget(group_review)

        # 2. Chunk 생성
        group_chunk = QGroupBox("5. Chunk 생성")
        chunk_layout = QHBoxLayout(group_chunk)
        chunk_layout.addWidget(QLabel("(Phase 7에서 구현)"))
        chunk_layout.addStretch()
        layout.addWidget(group_chunk)

        # 3. 임베딩 생성
        group_embedding = QGroupBox("6. 임베딩 생성")
        emb_layout = QHBoxLayout(group_embedding)
        emb_layout.addWidget(QLabel("(Phase 7에서 구현)"))
        emb_layout.addStretch()
        layout.addWidget(group_embedding)

        layout.addStretch()
        scroll.setWidget(content)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scroll)
