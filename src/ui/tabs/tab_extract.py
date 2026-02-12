"""Extract 탭 — PyMuPDF 라인 추출 실행."""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QPushButton,
    QProgressBar,
    QLabel,
    QCheckBox,
)
from PySide6.QtCore import QThread, Signal, QObject

from src.core.extract_pymupdf import extract_lines
from src.core.line_rebuild import rebuild_lines
from src.core.normalize import normalize_lines
from src.core.table_figure_filter import apply_table_figure_filter
from src.core.equation_filter import apply_equation_filter


class ExtractWorker(QObject):
    """백그라운드에서 PDF 라인 추출 수행."""

    progress = Signal(int, int)   # current_page, total_pages
    finished = Signal(list)       # lines
    error = Signal(str)

    def __init__(
        self,
        pdf_path: str,
        after_toc: bool,
        exclude_header_footer: bool,
        y_tolerance: float,
        hyphen_merge: bool,
        table_caption_only: bool,
        figure_caption_only: bool,
        exclude_equation: bool,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._pdf_path = pdf_path
        self._after_toc = after_toc
        self._exclude_header_footer = exclude_header_footer
        self._y_tolerance = y_tolerance
        self._hyphen_merge = hyphen_merge
        self._table_caption_only = table_caption_only
        self._figure_caption_only = figure_caption_only
        self._exclude_equation = exclude_equation

    def run(self) -> None:
        try:
            raw = extract_lines(
                self._pdf_path,
                after_toc=self._after_toc,
                exclude_header_footer=self._exclude_header_footer,
                progress_callback=lambda c, t: self.progress.emit(c, t),
            )
            rebuilt = rebuild_lines(
                raw,
                y_tolerance=self._y_tolerance,
                hyphen_merge=self._hyphen_merge,
            )
            lines = normalize_lines(rebuilt)
            if self._table_caption_only or self._figure_caption_only:
                lines = apply_table_figure_filter(
                    lines,
                    table_caption_only=self._table_caption_only,
                    figure_caption_only=self._figure_caption_only,
                )
            if self._exclude_equation:
                lines = apply_equation_filter(lines, exclude_equation=True)
            self.finished.emit(lines)
        except Exception as e:
            self.error.emit(str(e))


class TabExtract(QWidget):
    """Extract 탭 — 실행 버튼, 진행률, 결과 요약."""

    def __init__(self, app_state: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = app_state
        layout = QVBoxLayout(self)

        # Group: 추출 엔진
        group_engine = QGroupBox("추출 엔진")
        engine_layout = QVBoxLayout(group_engine)
        engine_layout.addWidget(QLabel("Engine: PyMuPDF"))
        layout.addWidget(group_engine)

        # Group: 라인화 옵션
        group_opts = QGroupBox("라인화 옵션")
        opts_layout = QVBoxLayout(group_opts)
        self._check_header_footer = QCheckBox("머릿말/꼬리말 제외 (페이지 상·하단 8% 영역)")
        self._check_header_footer.setChecked(True)
        self._check_header_footer.setToolTip("본문이 아닌 머리글·꼬리글을 제외합니다. 페이지 높이의 상·하 8% 밖의 라인은 추출하지 않습니다.")
        opts_layout.addWidget(self._check_header_footer)
        row_y = QHBoxLayout()
        row_y.addWidget(QLabel("y-merge tolerance:"))
        self._y_tolerance = 2.0
        opts_layout.addLayout(row_y)
        self._check_normalize = QCheckBox("공백 정규화")
        self._check_normalize.setChecked(True)
        opts_layout.addWidget(self._check_normalize)
        self._check_hyphen = QCheckBox("하이픈 줄바꿈 병합")
        self._check_hyphen.setChecked(False)
        opts_layout.addWidget(self._check_hyphen)
        self._check_table_caption_only = QCheckBox("표제목만 추출 (표 내용 제외)")
        self._check_table_caption_only.setChecked(True)
        self._check_table_caption_only.setToolTip("표 제목(표 1, 별표 1 등) 라인만 남기고 표 셀 내용은 제외합니다.")
        opts_layout.addWidget(self._check_table_caption_only)
        self._check_figure_caption_only = QCheckBox("그림제목만 추출 (그림 내용 제외)")
        self._check_figure_caption_only.setChecked(True)
        self._check_figure_caption_only.setToolTip("그림 제목(그림 1, Figure 1 등) 라인만 남기고 그림 설명은 제외합니다.")
        opts_layout.addWidget(self._check_figure_caption_only)
        self._check_exclude_equation = QCheckBox("수식 제외 (들여쓰기 블록·변수 정의 포함)")
        self._check_exclude_equation.setChecked(True)
        self._check_exclude_equation.setToolTip("본문보다 오른쪽(들여쓰기)으로 된 블록(수식, 변수 정의 목록 등)을 제외합니다. 페이지별 기준 왼쪽보다 25pt 이상 들어간 라인이 제외됩니다.")
        opts_layout.addWidget(self._check_exclude_equation)
        layout.addWidget(group_opts)

        # Group: 실행/로그
        group_run = QGroupBox("실행/로그")
        run_layout = QVBoxLayout(group_run)

        row_btn = QHBoxLayout()
        self._btn_run = QPushButton("실행")
        self._btn_run.clicked.connect(self._on_run)
        row_btn.addWidget(self._btn_run)
        row_btn.addStretch()
        run_layout.addLayout(row_btn)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)  # 0 = indeterminate until first progress
        self._progress.setFormat("%v / %m 페이지")
        run_layout.addWidget(self._progress)

        self._label_summary = QLabel("결과 요약: 실행 후 표시됩니다.")
        self._label_summary.setWordWrap(True)
        self._label_summary.setStyleSheet("color: #444;")
        run_layout.addWidget(self._label_summary)

        layout.addWidget(group_run)
        layout.addStretch()

        self._thread: QThread | None = None
        self._worker: ExtractWorker | None = None

    def _on_run(self) -> None:
        paths = self._state.get("pdf_paths", [])
        if not paths:
            self._label_summary.setText("오류: Import 탭에서 PDF 파일을 먼저 선택하세요.")
            return

        pdf_path = paths[0]
        after_toc = self._state.get("after_toc", True)
        exclude_header_footer = self._check_header_footer.isChecked()
        y_tolerance = self._y_tolerance
        hyphen_merge = self._check_hyphen.isChecked()
        table_caption_only = self._check_table_caption_only.isChecked()
        figure_caption_only = self._check_figure_caption_only.isChecked()
        exclude_equation = self._check_exclude_equation.isChecked()

        self._btn_run.setEnabled(False)
        self._progress.setRange(0, 0)
        self._progress.setValue(0)
        self._label_summary.setText("추출 중…")

        self._thread = QThread()
        self._worker = ExtractWorker(
            pdf_path,
            after_toc,
            exclude_header_footer,
            y_tolerance,
            hyphen_merge,
            table_caption_only,
            figure_caption_only,
            exclude_equation,
        )
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)

        self._thread.start()

    def _on_progress(self, current: int, total: int) -> None:
        if total > 0:
            self._progress.setMaximum(total)
            self._progress.setValue(current)

    def _on_finished(self, lines: list) -> None:
        self._state["extract_lines"] = lines
        self._btn_run.setEnabled(True)

        total = len(lines)
        from collections import Counter
        by_page = Counter(ln.get("page", 0) for ln in lines)
        page_parts = [f"{p}장: {n}줄" for p, n in sorted(by_page.items())]
        summary = f"총 라인 수: {total}줄"
        if page_parts:
            summary += "  |  페이지별: " + ", ".join(page_parts[:15])
            if len(page_parts) > 15:
                summary += f" … 외 {len(page_parts)-15}페이지"
        self._label_summary.setText(summary)

    def _on_error(self, message: str) -> None:
        self._btn_run.setEnabled(True)
        self._label_summary.setText(f"오류: {message}")
