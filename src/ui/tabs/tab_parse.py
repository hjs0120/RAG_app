"""Parse 탭 — 구조화/Path 태깅."""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QPushButton,
    QLineEdit,
    QLabel,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
)
from PySide6.QtCore import Qt

from src.core.rules import classify_line
from src.core.parse_state_machine import parse_lines


class TabParse(QWidget):
    """Parse 탭 — 규칙 테스트, Path 미리보기."""

    def __init__(self, app_state: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = app_state
        layout = QVBoxLayout(self)

        # Group: 규칙(Rules) — 샘플 라인 테스트
        group_rules = QGroupBox("규칙(Rules)")
        rules_layout = QVBoxLayout(group_rules)
        row = QHBoxLayout()
        row.addWidget(QLabel("샘플 라인:"))
        self._sample_input = QLineEdit()
        self._sample_input.setPlaceholderText("예: 제 1 장 총칙, 제 1 절 일반사항, 101. 적용, 1. 이 규칙은...")
        self._sample_input.returnPressed.connect(self._on_test_sample)
        row.addWidget(self._sample_input)
        self._btn_test = QPushButton("테스트")
        self._btn_test.clicked.connect(self._on_test_sample)
        row.addWidget(self._btn_test)
        rules_layout.addLayout(row)
        self._sample_result = QLabel("결과: (위에 라인 입력 후 테스트)")
        self._sample_result.setWordWrap(True)
        self._sample_result.setStyleSheet("color: #333; padding: 4px;")
        rules_layout.addWidget(self._sample_result)
        layout.addWidget(group_rules)

        # 실행 버튼 — 추출 결과에 Path 태깅 적용
        row_run = QHBoxLayout()
        self._btn_run = QPushButton("Path 태깅 실행")
        self._btn_run.clicked.connect(self._on_run_parse)
        row_run.addWidget(self._btn_run)
        self._label_parse_status = QLabel("Extract 탭에서 먼저 추출을 실행하세요.")
        self._label_parse_status.setStyleSheet("color: #666;")
        row_run.addWidget(self._label_parse_status)
        row_run.addStretch()
        layout.addLayout(row_run)

        # Group: Path 미리보기
        group_preview = QGroupBox("Path 미리보기")
        preview_layout = QVBoxLayout(group_preview)
        row_page = QHBoxLayout()
        row_page.addWidget(QLabel("페이지:"))
        self._combo_page = QComboBox()
        self._combo_page.currentIndexChanged.connect(self._on_page_changed)
        row_page.addWidget(self._combo_page)
        row_page.addStretch()
        preview_layout.addLayout(row_page)

        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["라인", "텍스트", "구분", "path"])
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        preview_layout.addWidget(self._table)

        layout.addWidget(group_preview)
        layout.addStretch()

    def _on_test_sample(self) -> None:
        text = self._sample_input.text().strip()
        if not text:
            self._sample_result.setText("결과: (라인을 입력하세요)")
            return
        r = classify_line(text)
        if r:
            self._sample_result.setText(f"결과: {r.kind} → value=\"{r.value}\"")
        else:
            self._sample_result.setText("결과: (일치하는 규칙 없음 — 일반 본문)")

    def _on_run_parse(self) -> None:
        lines = self._state.get("extract_lines", [])
        if not lines:
            self._label_parse_status.setText("Extract 탭에서 먼저 추출을 실행하세요.")
            return
        parsed = parse_lines(lines)
        self._state["parsed_lines"] = parsed
        self._label_parse_status.setText(f"완료: {len(parsed)}개 라인에 path 부여됨.")
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        """parsed_lines 기준으로 페이지 콤보와 테이블 갱신."""
        parsed = self._state.get("parsed_lines", [])
        self._combo_page.clear()
        if not parsed:
            self._table.setRowCount(0)
            return
        pages = sorted({ln.get("page") for ln in parsed if ln.get("page") is not None})
        for p in pages:
            self._combo_page.addItem(f"{p}페이지", p)
        if pages:
            self._combo_page.setCurrentIndex(0)
            self._on_page_changed()

    def _on_page_changed(self) -> None:
        page = self._combo_page.currentData()
        if page is None:
            return
        parsed = self._state.get("parsed_lines", [])
        page_lines = [ln for ln in parsed if ln.get("page") == page]
        self._table.setRowCount(len(page_lines))
        for i, ln in enumerate(page_lines):
            self._table.setItem(i, 0, QTableWidgetItem(str(ln.get("line_no", ""))))
            text = (ln.get("text") or "")[:80]
            if len(ln.get("text") or "") > 80:
                text += "…"
            self._table.setItem(i, 1, QTableWidgetItem(text))
            path = ln.get("path") or {}
            kind = ""
            if path.get("chapter"):
                kind = "장"
            if path.get("section"):
                kind = "절"
            if path.get("article"):
                kind = "조"
            if path.get("paragraph"):
                kind = "항/호/목" if not kind else kind
            if not kind:
                kind = "—"
            self._table.setItem(i, 2, QTableWidgetItem(kind))
            path_str = " | ".join(
                f"{k}={v}" for k, v in path.items()
                if v is not None and k != "part"
            )
            self._table.setItem(i, 3, QTableWidgetItem(path_str or "—"))
        self._table.resizeRowsToContents()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # 탭 전환 시 추출 결과는 이미 있으면 파싱만 안 된 상태일 수 있음
        if self._state.get("parsed_lines"):
            self._refresh_preview()
        elif self._state.get("extract_lines") and not self._state.get("parsed_lines"):
            self._label_parse_status.setText("'Path 태깅 실행'을 눌러 주세요.")
