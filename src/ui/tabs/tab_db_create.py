"""DB 생성 탭 — PDF→텍스트→Chunk→임베딩 통합 파이프라인."""

from __future__ import annotations

import json
import os
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QObject, QEvent
from PySide6.QtGui import QImage, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QLineEdit,
    QCheckBox,
    QFileDialog,
    QScrollArea,
    QProgressBar,
    QSplitter,
    QFormLayout,
    QPlainTextEdit,
    QFrame,
    QMessageBox,
    QSpinBox,
    QDialog,
)

import fitz

from src.core.extract_pymupdf import extract_lines
from src.core.line_rebuild import rebuild_lines
from src.core.normalize import normalize_lines
from src.core.table_figure_filter import apply_table_figure_filter
from src.core.equation_filter import apply_equation_filter
from src.core.parse_state_machine import parse_lines
from src.core.export_jsonl import (
    write_jsonl,
    write_records_jsonl,
    load_jsonl,
)
from src.core.chunk_builder import (
    build_chunks,
    write_chunk_jsonl,
    TARGET_LEN,
    MAX_LEN,
    MIN_CHUNK_LEN,
)
from src.core.faiss_index import build_index_from_chunks
from src.ui.tabs.tab_review import _draw_bbox_on_pixmap


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_data_dir() -> str:
    return str(_project_root() / "data")


def _default_output_dir(state: dict | None) -> str:
    if state and state.get("output_dir"):
        return str(state["output_dir"])
    return str(_project_root() / "output")


def _doc_id_from_path(path: str) -> str:
    name = os.path.splitext(os.path.basename(path))[0]
    return name.replace(" ", "_").replace(".", "_")


def _render_page_to_pixmap(pdf_path: str | Path, page_no: int, dpi_scale: float = 2.0) -> QPixmap | None:
    pdf_path = Path(pdf_path)
    if not pdf_path.is_file() or page_no < 1:
        return None
    try:
        doc = fitz.open(pdf_path)
        try:
            page = doc[page_no - 1]
            mat = fitz.Matrix(dpi_scale, dpi_scale)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()
            return QPixmap.fromImage(img)
        finally:
            doc.close()
    except Exception:
        return None
    return None


class ReviewDialog(QDialog):
    """검수 창 — PDF·JSONL 뷰, 수정·저장 후 닫기."""

    def __init__(
        self,
        pdf_path: str,
        jsonl_path: str,
        records: list[dict],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._pdf_path = pdf_path
        self._jsonl_path = jsonl_path
        self._records = records
        self._current_index = 0
        self._current_pixmap: QPixmap | None = None

        self.setWindowTitle("검수 — PDF·JSONL")
        self.setMinimumSize(900, 600)
        self.resize(1100, 700)

        layout = QVBoxLayout(self)
        nav_layout = QHBoxLayout()
        self._label_progress = QLabel("— / —")
        self._label_progress.setStyleSheet("font-weight: bold; min-width: 100px;")
        self._btn_prev = QPushButton("◀ 이전")
        self._btn_prev.clicked.connect(self._go_prev)
        self._btn_next = QPushButton("다음 ▶")
        self._btn_next.clicked.connect(self._go_next)
        nav_layout.addWidget(self._label_progress)
        nav_layout.addWidget(self._btn_prev)
        nav_layout.addWidget(self._btn_next)
        nav_layout.addStretch()
        layout.addLayout(nav_layout)
        QShortcut(QKeySequence(Qt.Key_Left), self, self._go_prev, context=Qt.WidgetWithChildrenShortcut)
        QShortcut(QKeySequence(Qt.Key_Right), self, self._go_next, context=Qt.WidgetWithChildrenShortcut)

        splitter = QSplitter(Qt.Horizontal)
        left_w = QWidget()
        left_lay = QVBoxLayout(left_w)
        left_lay.setContentsMargins(0, 0, 0, 0)
        self._scroll_pdf = QScrollArea()
        self._scroll_pdf.setWidgetResizable(True)
        self._scroll_pdf.setFrameShape(QFrame.NoFrame)
        self._label_pdf_view = QLabel()
        self._label_pdf_view.setAlignment(Qt.AlignCenter)
        self._label_pdf_view.setMinimumSize(320, 450)
        self._label_pdf_view.setStyleSheet("background-color: #f0f0f0; color: #666;")
        self._label_pdf_view.setText("PDF 페이지")
        self._scroll_pdf.setWidget(self._label_pdf_view)
        self._scroll_pdf.viewport().installEventFilter(self)
        left_lay.addWidget(self._scroll_pdf)
        splitter.addWidget(left_w)

        right_w = QWidget()
        right_lay = QVBoxLayout(right_w)
        right_lay.addWidget(QLabel("현재 라인 (편집 가능)"))
        form = QFormLayout()
        self._field_doc_id = QLineEdit()
        self._field_doc_id.setReadOnly(True)
        self._field_content_page = QLineEdit()
        self._field_content_page.setReadOnly(True)
        self._field_page = QLineEdit()
        self._field_page.setReadOnly(True)
        self._field_path = QPlainTextEdit()
        self._field_path.setMinimumHeight(100)
        self._field_text = QPlainTextEdit()
        self._field_text.setMinimumHeight(150)
        form.addRow("doc_id:", self._field_doc_id)
        form.addRow("page (문서):", self._field_content_page)
        form.addRow("  PDF 물리:", self._field_page)
        form.addRow("path:", self._field_path)
        form.addRow("text:", self._field_text)
        right_lay.addLayout(form)
        btn_row = QHBoxLayout()
        self._btn_save_close = QPushButton("저장 후 닫기")
        self._btn_save_close.clicked.connect(self._on_save_and_close)
        btn_row.addWidget(self._btn_save_close)
        btn_row.addStretch()
        right_lay.addLayout(btn_row)
        splitter.addWidget(right_w)
        splitter.setSizes([500, 450])
        layout.addWidget(splitter, 1)

        self._refresh_all()
        self._update_nav_state()

    def eventFilter(self, obj: QWidget, event: QEvent) -> bool:
        if obj is self._scroll_pdf.viewport() and event.type() == QEvent.Type.Resize:
            self._scale_and_show_pdf()
        return super().eventFilter(obj, event)

    def _scale_and_show_pdf(self) -> None:
        if self._current_pixmap is None or self._current_pixmap.isNull():
            return
        vp = self._scroll_pdf.viewport()
        size = vp.size()
        if size.width() <= 0 or size.height() <= 0:
            return
        scaled = self._current_pixmap.scaled(
            size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        self._label_pdf_view.setPixmap(scaled)
        self._label_pdf_view.setText("")

    def _refresh_pdf_view(self) -> None:
        if not self._records or not (0 <= self._current_index < len(self._records)):
            page_no = 1
        else:
            page_no = self._records[self._current_index].get("page") or 1
        pix = _render_page_to_pixmap(self._pdf_path, page_no)
        if pix is not None:
            if self._records and 0 <= self._current_index < len(self._records):
                bbox = self._records[self._current_index].get("bbox")
                if isinstance(bbox, list) and len(bbox) >= 4:
                    _draw_bbox_on_pixmap(pix, bbox, dpi_scale=2.0)
            self._current_pixmap = pix
            self._scale_and_show_pdf()
        else:
            self._current_pixmap = None
            self._label_pdf_view.setText(f"페이지 {page_no} 로드 불가")

    def _refresh_right_panel(self) -> None:
        if not self._records or not (0 <= self._current_index < len(self._records)):
            self._field_doc_id.clear()
            self._field_content_page.clear()
            self._field_page.clear()
            self._field_path.clear()
            self._field_text.clear()
            return
        rec = self._records[self._current_index]
        self._field_doc_id.setText(str(rec.get("doc_id", "")))
        cp = rec.get("content_page", rec.get("page", ""))
        self._field_content_page.setText(str(cp))
        self._field_page.setText(str(rec.get("page", "")))
        self._field_path.setPlainText(json.dumps(rec.get("path") or {}, ensure_ascii=False, indent=2))
        self._field_text.setPlainText(str(rec.get("text", "")))

    def _refresh_all(self) -> None:
        self._refresh_pdf_view()
        self._refresh_right_panel()

    def _flush_current_to_record(self) -> None:
        if not self._records or not (0 <= self._current_index < len(self._records)):
            return
        rec = self._records[self._current_index]
        rec["text"] = self._field_text.toPlainText()
        try:
            path_text = self._field_path.toPlainText().strip()
            if path_text:
                rec["path"] = json.loads(path_text)
        except json.JSONDecodeError:
            pass

    def _go_prev(self) -> None:
        self._flush_current_to_record()
        if self._current_index <= 0:
            return
        self._current_index -= 1
        self._refresh_all()
        self._update_nav_state()

    def _go_next(self) -> None:
        self._flush_current_to_record()
        if not self._records or self._current_index >= len(self._records) - 1:
            return
        self._current_index += 1
        self._refresh_all()
        self._update_nav_state()

    def _update_nav_state(self) -> None:
        total = len(self._records)
        if total == 0:
            self._label_progress.setText("— / —")
            self._btn_prev.setEnabled(False)
            self._btn_next.setEnabled(False)
            return
        self._label_progress.setText(f"{self._current_index + 1} / {total}")
        self._btn_prev.setEnabled(self._current_index > 0)
        self._btn_next.setEnabled(self._current_index < total - 1)

    def _on_save_and_close(self) -> None:
        self._flush_current_to_record()
        if not self._records:
            QMessageBox.information(self, "저장", "저장할 레코드가 없습니다.")
            return
        try:
            n = write_records_jsonl(self._records, self._jsonl_path)
            QMessageBox.information(self, "저장", f"저장했습니다. ({n}개 레코드)")
        except Exception as e:
            QMessageBox.critical(self, "저장 실패", str(e))
            return
        self.accept()


class ExtractWorker(QObject):
    progress = Signal(int, int)
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, pdf_path: str, after_toc: bool, exclude_header_footer: bool,
                 y_tolerance: float, hyphen_merge: bool, table_caption_only: bool,
                 figure_caption_only: bool, exclude_equation: bool, parent=None):
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
            rebuilt = rebuild_lines(raw, y_tolerance=self._y_tolerance, hyphen_merge=self._hyphen_merge)
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


class EmbeddingWorker(QObject):
    progress = Signal(int, int)
    finished = Signal(str, str)
    error = Signal(str)

    def __init__(self, chunk_path: str, output_dir: str, stem: str = "rules", parent=None):
        super().__init__(parent)
        self._chunk_path = chunk_path
        self._output_dir = output_dir
        self._stem = stem

    def run(self) -> None:
        try:
            chunks = load_jsonl(self._chunk_path)
            if not chunks:
                self.error.emit("Chunk JSONL에 레코드가 없습니다.")
                return

            def on_progress(c: int, t: int) -> None:
                self.progress.emit(c, t)

            idx_path, meta_path = build_index_from_chunks(
                chunks,
                output_dir=self._output_dir,
                stem=self._stem,
                progress_callback=on_progress,
            )
            self.finished.emit(str(idx_path), str(meta_path))
        except Exception as e:
            self.error.emit(str(e))


class AppendWorker(QObject):
    """기존 FAISS 인덱스에 새 chunk를 증분 추가하는 비동기 Worker."""

    progress = Signal(int, int)
    finished = Signal(str, str)
    error = Signal(str)

    def __init__(self, chunk_path: str, index_path: str, meta_path: str, parent=None):
        super().__init__(parent)
        self._chunk_path = chunk_path
        self._index_path = index_path
        self._meta_path = meta_path

    def run(self) -> None:
        from src.db.db_manager import append_chunks

        try:
            chunks = load_jsonl(self._chunk_path)
            if not chunks:
                self.error.emit("Chunk JSONL에 레코드가 없습니다.")
                return

            idx_path, meta_path = append_chunks(
                chunks,
                index_path=self._index_path,
                meta_path=self._meta_path or None,
                progress_callback=lambda c, t: self.progress.emit(c, t),
            )
            self.finished.emit(str(idx_path), str(meta_path))
        except Exception as e:
            self.error.emit(str(e))


def _save_docs_meta(output_dir: str | Path, doc_id: str, content_start_pdf_page: int | None) -> None:
    """docs_meta.json에 doc_id → content_start_pdf_page 저장 (Phase 10 매핑용)."""
    output_dir = Path(output_dir)
    meta_path = output_dir / "docs_meta.json"
    data: list[dict] = []
    if meta_path.exists():
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                data = []
        except Exception:
            data = []
    # 기존 항목 업데이트 또는 추가
    found = False
    for item in data:
        if item.get("doc_id") == doc_id:
            item["content_start_pdf_page"] = content_start_pdf_page
            found = True
            break
    if not found:
        data.append({"doc_id": doc_id, "content_start_pdf_page": content_start_pdf_page})
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class TabDBCreate(QWidget):
    """DB 생성 탭 — Import → Extract → Parse → 검수 → Chunk → 임베딩 통합 파이프라인."""

    def __init__(self, app_state: dict | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = app_state or {}
        self._jsonl_path: str = ""
        self._records: list[dict] = []
        self._extract_thread: QThread | None = None
        self._extract_worker: ExtractWorker | None = None
        self._embedding_thread: QThread | None = None
        self._embedding_worker: EmbeddingWorker | None = None
        self._append_thread: QThread | None = None
        self._append_worker: AppendWorker | None = None

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        layout = QVBoxLayout(content)

        # ========== 1. PDF → 텍스트 추출 ==========
        group_import = QGroupBox("1. Import — PDF 선택")
        imp_layout = QVBoxLayout(group_import)
        row_files = QHBoxLayout()
        self._btn_pdf = QPushButton("PDF 선택")
        self._btn_pdf.clicked.connect(self._on_select_pdf)
        self._label_pdf = QLabel("선택된 파일 없음")
        self._label_pdf.setStyleSheet("color: #666;")
        row_files.addWidget(self._btn_pdf)
        row_files.addWidget(self._label_pdf, 1)
        imp_layout.addLayout(row_files)
        row_doc = QHBoxLayout()
        row_doc.addWidget(QLabel("doc_id:"))
        self._edit_doc_id = QLineEdit()
        self._edit_doc_id.setPlaceholderText("자동 생성")
        self._edit_doc_id.textChanged.connect(lambda t: self._state.update({"doc_id": t.strip()}))
        row_doc.addWidget(self._edit_doc_id)
        row_doc.addWidget(QLabel("출력 디렉터리:"))
        self._edit_output = QLineEdit()
        self._edit_output.setText(self._state.get("output_dir") or _default_output_dir(self._state))
        self._edit_output.textChanged.connect(lambda t: self._state.update({"output_dir": t.strip() or _default_output_dir(self._state)}))
        row_doc.addWidget(self._edit_output)
        btn_out = QPushButton("찾아보기")
        btn_out.clicked.connect(self._on_browse_output)
        row_doc.addWidget(btn_out)
        imp_layout.addLayout(row_doc)
        self._check_after_toc = QCheckBox("차례 이후부터")
        self._check_after_toc.setChecked(self._state.get("after_toc", True))
        imp_layout.addWidget(self._check_after_toc)
        layout.addWidget(group_import)

        # 2. Extract
        group_extract = QGroupBox("2. Extract — 텍스트 추출")
        ext_layout = QVBoxLayout(group_extract)
        row_opts = QHBoxLayout()
        self._check_header_footer = QCheckBox("머릿말/꼬리말 제외")
        self._check_header_footer.setChecked(True)
        self._check_table = QCheckBox("표제목만")
        self._check_table.setChecked(True)
        self._check_figure = QCheckBox("그림제목만")
        self._check_figure.setChecked(True)
        self._check_equation = QCheckBox("수식 제외")
        self._check_equation.setChecked(True)
        row_opts.addWidget(self._check_header_footer)
        row_opts.addWidget(self._check_table)
        row_opts.addWidget(self._check_figure)
        row_opts.addWidget(self._check_equation)
        row_opts.addStretch()
        ext_layout.addLayout(row_opts)
        row_btn = QHBoxLayout()
        self._btn_extract = QPushButton("실행")
        self._btn_extract.clicked.connect(self._on_extract)
        self._label_extract = QLabel("Import 후 실행하세요.")
        self._label_extract.setStyleSheet("color: #666;")
        row_btn.addWidget(self._btn_extract)
        row_btn.addWidget(self._label_extract, 1)
        ext_layout.addLayout(row_btn)
        self._progress_extract = QProgressBar()
        self._progress_extract.setVisible(False)
        ext_layout.addWidget(self._progress_extract)
        layout.addWidget(group_extract)

        # 3. Parse
        group_parse = QGroupBox("3. Parse — 구조 태깅")
        parse_layout = QHBoxLayout(group_parse)
        self._btn_parse = QPushButton("Path 태깅 실행")
        self._btn_parse.clicked.connect(self._on_parse)
        self._label_parse = QLabel("Extract 후 실행하세요.")
        self._label_parse.setStyleSheet("color: #666;")
        parse_layout.addWidget(self._btn_parse)
        parse_layout.addWidget(self._label_parse, 1)
        layout.addWidget(group_parse)

        # 4. Export + 검수
        group_export = QGroupBox("4. Export & 검수")
        exp_layout = QVBoxLayout(group_export)
        row_exp = QHBoxLayout()
        self._check_merge_para = QCheckBox("Paragraph 단위 합치기")
        self._check_merge_para.setChecked(True)
        row_exp.addWidget(self._check_merge_para)
        self._btn_export = QPushButton("JSONL 저장")
        self._btn_export.clicked.connect(self._on_export)
        row_exp.addWidget(self._btn_export)
        self._btn_open_review = QPushButton("검수 열기")
        self._btn_open_review.clicked.connect(self._on_open_review)
        self._btn_open_review.setToolTip(
            "저장된 JSONL을 열어 검수. 창 닫았다가 다시 열어도 이어서 가능."
        )
        row_exp.addWidget(self._btn_open_review)
        row_exp.addStretch()
        exp_layout.addLayout(row_exp)
        self._label_export = QLabel("Parse 후 JSONL 저장하세요.")
        self._label_export.setStyleSheet("color: #666;")
        exp_layout.addWidget(self._label_export)
        layout.addWidget(group_export)

        # 5. Chunk
        group_chunk = QGroupBox("5. Chunk 생성")
        chunk_layout = QVBoxLayout(group_chunk)
        row_chunk = QHBoxLayout()
        row_chunk.addWidget(QLabel("원본 JSONL:"))
        self._edit_chunk_input = QLineEdit()
        self._edit_chunk_input.setPlaceholderText("Export에서 저장한 파일")
        row_chunk.addWidget(self._edit_chunk_input)
        self._btn_browse_chunk = QPushButton("찾아보기")
        self._btn_browse_chunk.clicked.connect(self._on_browse_chunk_input)
        row_chunk.addWidget(self._btn_browse_chunk)
        chunk_layout.addLayout(row_chunk)
        row_opts_chunk = QHBoxLayout()
        row_opts_chunk.addWidget(QLabel("목표:"))
        self._spin_target = QSpinBox()
        self._spin_target.setRange(100, 2000)
        self._spin_target.setValue(TARGET_LEN)
        self._spin_target.setSuffix("자")
        row_opts_chunk.addWidget(self._spin_target)
        row_opts_chunk.addWidget(QLabel("최대:"))
        self._spin_max = QSpinBox()
        self._spin_max.setRange(200, 3000)
        self._spin_max.setValue(MAX_LEN)
        self._spin_max.setSuffix("자")
        row_opts_chunk.addWidget(self._spin_max)
        row_opts_chunk.addStretch()
        chunk_layout.addLayout(row_opts_chunk)
        row_btn_chunk = QHBoxLayout()
        self._btn_chunk = QPushButton("Chunk 생성")
        self._btn_chunk.clicked.connect(self._on_chunk)
        self._label_chunk = QLabel("원본 JSONL 선택 후 실행.")
        self._label_chunk.setStyleSheet("color: #666;")
        row_btn_chunk.addWidget(self._btn_chunk)
        row_btn_chunk.addWidget(self._label_chunk, 1)
        chunk_layout.addLayout(row_btn_chunk)
        layout.addWidget(group_chunk)

        # 6. 임베딩
        group_embedding = QGroupBox("6. 임베딩 생성")
        emb_layout = QVBoxLayout(group_embedding)
        row_emb = QHBoxLayout()
        row_emb.addWidget(QLabel("Chunk JSONL:"))
        self._edit_chunk_emb = QLineEdit()
        self._edit_chunk_emb.setPlaceholderText("Chunk 생성 결과 파일")
        row_emb.addWidget(self._edit_chunk_emb)
        self._btn_browse_emb = QPushButton("찾아보기")
        self._btn_browse_emb.clicked.connect(self._on_browse_chunk_emb)
        row_emb.addWidget(self._btn_browse_emb)
        emb_layout.addLayout(row_emb)
        row_emb_out = QHBoxLayout()
        row_emb_out.addWidget(QLabel("출력 디렉터리:"))
        self._edit_emb_output = QLineEdit()
        row_emb_out.addWidget(self._edit_emb_output)
        self._btn_browse_emb_out = QPushButton("찾아보기")
        self._btn_browse_emb_out.clicked.connect(self._on_browse_emb_output)
        row_emb_out.addWidget(self._btn_browse_emb_out)
        emb_layout.addLayout(row_emb_out)
        row_btn_emb = QHBoxLayout()
        self._btn_embedding = QPushButton("임베딩 & FAISS 저장")
        self._btn_embedding.clicked.connect(self._on_embedding)
        self._label_embedding = QLabel("Chunk JSONL 선택 후 실행.")
        self._label_embedding.setStyleSheet("color: #666;")
        row_btn_emb.addWidget(self._btn_embedding)
        row_btn_emb.addWidget(self._label_embedding, 1)
        emb_layout.addLayout(row_btn_emb)
        self._progress_embedding = QProgressBar()
        self._progress_embedding.setVisible(False)
        emb_layout.addWidget(self._progress_embedding)
        layout.addWidget(group_embedding)

        # 7. 기존 인덱스에 추가 (증분 임베딩)
        group_append = QGroupBox("7. 기존 인덱스에 추가 (증분 임베딩)")
        app_layout = QVBoxLayout(group_append)

        row_app_chunk = QHBoxLayout()
        row_app_chunk.addWidget(QLabel("추가할 Chunk JSONL:"))
        self._edit_append_chunk = QLineEdit()
        self._edit_append_chunk.setPlaceholderText("추가할 chunk_XXXX.jsonl")
        row_app_chunk.addWidget(self._edit_append_chunk)
        btn_browse_app_chunk = QPushButton("찾아보기")
        btn_browse_app_chunk.clicked.connect(self._on_browse_append_chunk)
        row_app_chunk.addWidget(btn_browse_app_chunk)
        app_layout.addLayout(row_app_chunk)

        row_app_idx = QHBoxLayout()
        row_app_idx.addWidget(QLabel("기존 인덱스 (.index):"))
        self._edit_append_index = QLineEdit()
        self._edit_append_index.setPlaceholderText("기존 rules.index 경로")
        row_app_idx.addWidget(self._edit_append_index)
        btn_browse_app_idx = QPushButton("찾아보기")
        btn_browse_app_idx.clicked.connect(self._on_browse_append_index)
        row_app_idx.addWidget(btn_browse_app_idx)
        app_layout.addLayout(row_app_idx)

        row_app_meta = QHBoxLayout()
        row_app_meta.addWidget(QLabel("기존 Meta JSONL:"))
        self._edit_append_meta = QLineEdit()
        self._edit_append_meta.setPlaceholderText("비워두면 인덱스 경로에서 자동 추론")
        row_app_meta.addWidget(self._edit_append_meta)
        btn_browse_app_meta = QPushButton("찾아보기")
        btn_browse_app_meta.clicked.connect(self._on_browse_append_meta)
        row_app_meta.addWidget(btn_browse_app_meta)
        app_layout.addLayout(row_app_meta)

        row_btn_app = QHBoxLayout()
        self._btn_append = QPushButton("추가")
        self._btn_append.clicked.connect(self._on_append)
        self._label_append = QLabel("Chunk JSONL과 기존 인덱스를 선택 후 실행하세요.")
        self._label_append.setStyleSheet("color: #666;")
        row_btn_app.addWidget(self._btn_append)
        row_btn_app.addWidget(self._label_append, 1)
        app_layout.addLayout(row_btn_app)
        self._progress_append = QProgressBar()
        self._progress_append.setVisible(False)
        app_layout.addWidget(self._progress_append)
        layout.addWidget(group_append)

        layout.addStretch()
        scroll.setWidget(content)
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scroll)

        self._sync_from_state()
        self._update_step_states()

    def _sync_from_state(self) -> None:
        paths = self._state.get("pdf_paths", [])
        if paths:
            self._label_pdf.setText(f"선택: {len(paths)}개 — {Path(paths[0]).name}")
            if not self._edit_doc_id.text().strip():
                self._edit_doc_id.setText(self._state.get("doc_id") or _doc_id_from_path(paths[0]))
        else:
            self._label_pdf.setText("선택된 파일 없음")
        self._edit_output.setText(self._state.get("output_dir") or _default_output_dir(self._state))

    def _update_step_states(self) -> None:
        paths = self._state.get("pdf_paths", [])
        extract_lines_list = self._state.get("extract_lines", [])
        parsed = self._state.get("parsed_lines", [])
        self._btn_extract.setEnabled(bool(paths))
        self._btn_parse.setEnabled(bool(extract_lines_list))
        self._btn_export.setEnabled(bool(parsed))

    def _on_select_pdf(self) -> None:
        start = _default_data_dir()
        paths, _ = QFileDialog.getOpenFileNames(
            self, "PDF 선택", start, "PDF (*.pdf);;모든 파일 (*)",
        )
        if paths:
            self._state["pdf_paths"] = list(paths)
            self._state["doc_id"] = _doc_id_from_path(paths[0])
            self._sync_from_state()
            self._update_step_states()

    def _on_browse_output(self) -> None:
        start = self._edit_output.text().strip() or _default_output_dir(self._state)
        path = QFileDialog.getExistingDirectory(self, "출력 디렉터리", start)
        if path:
            self._edit_output.setText(path)
            self._state["output_dir"] = path

    def _on_extract(self) -> None:
        paths = self._state.get("pdf_paths", [])
        if not paths:
            self._label_extract.setText("PDF를 먼저 선택하세요.")
            return
        self._state["output_dir"] = self._edit_output.text().strip() or _default_output_dir(self._state)
        self._state["doc_id"] = self._edit_doc_id.text().strip() or _doc_id_from_path(paths[0])
        self._state["after_toc"] = self._check_after_toc.isChecked()

        self._btn_extract.setEnabled(False)
        self._progress_extract.setVisible(True)
        self._progress_extract.setRange(0, 0)
        self._label_extract.setText("추출 중…")

        self._extract_worker = ExtractWorker(
            paths[0],
            self._state["after_toc"],
            self._check_header_footer.isChecked(),
            2.0,
            False,
            self._check_table.isChecked(),
            self._check_figure.isChecked(),
            self._check_equation.isChecked(),
        )
        self._extract_thread = QThread()
        self._extract_worker.moveToThread(self._extract_thread)
        self._extract_thread.started.connect(self._extract_worker.run)
        self._extract_worker.progress.connect(self._on_extract_progress)
        self._extract_worker.finished.connect(self._on_extract_finished)
        self._extract_worker.error.connect(self._on_extract_error)
        self._extract_worker.finished.connect(self._extract_thread.quit)
        self._extract_worker.error.connect(self._extract_thread.quit)
        self._extract_thread.start()

    def _on_extract_progress(self, cur: int, tot: int) -> None:
        if tot > 0:
            self._progress_extract.setMaximum(tot)
            self._progress_extract.setValue(cur)

    def _on_extract_finished(self, lines: list) -> None:
        self._state["extract_lines"] = lines
        self._btn_extract.setEnabled(True)
        self._progress_extract.setVisible(False)
        n = len(lines)
        self._label_extract.setText(f"완료: {n}줄 추출됨.")
        self._update_step_states()

    def _on_extract_error(self, msg: str) -> None:
        self._btn_extract.setEnabled(True)
        self._progress_extract.setVisible(False)
        self._label_extract.setText(f"오류: {msg}")

    def _on_parse(self) -> None:
        lines = self._state.get("extract_lines", [])
        if not lines:
            self._label_parse.setText("Extract를 먼저 실행하세요.")
            return
        parsed = parse_lines(lines)
        self._state["parsed_lines"] = parsed
        self._label_parse.setText(f"완료: {len(parsed)}개 라인 path 부여.")
        self._update_step_states()

    def _on_export(self) -> None:
        parsed = self._state.get("parsed_lines", [])
        if not parsed:
            self._label_export.setText("Parse를 먼저 실행하세요.")
            return
        doc_id = (self._state.get("doc_id") or "").strip() or "export"
        output_dir = Path(self._edit_output.text().strip() or _default_output_dir(self._state))
        output_dir.mkdir(parents=True, exist_ok=True)
        pdf_paths = self._state.get("pdf_paths", [])
        source_file = Path(pdf_paths[0]).name if pdf_paths else "unknown.pdf"
        out_path = output_dir / f"{doc_id}.jsonl"
        try:
            count = write_jsonl(
                parsed,
                out_path,
                doc_id=doc_id,
                source_file=source_file,
                merge_by_paragraph=self._check_merge_para.isChecked(),
            )
            self._jsonl_path = str(out_path)
            self._records = load_jsonl(out_path)
            self._current_index = 0
            self._label_export.setText(f"저장 완료: {out_path} ({count}행)")
            self._edit_chunk_input.setText(self._jsonl_path)
        except Exception as e:
            self._label_export.setText(f"저장 실패: {e}")
            return

    def _on_open_review(self) -> None:
        """검수 창 열기. JSONL·PDF 선택 → 언제든 이어서 검수 가능."""
        out_dir = self._edit_output.text().strip() or _default_output_dir(self._state)
        jsonl_default = self._jsonl_path or out_dir
        jsonl_path, _ = QFileDialog.getOpenFileName(
            self,
            "JSONL 파일 선택 (검수용)",
            jsonl_default,
            "JSONL (*.jsonl);;모든 파일 (*)",
        )
        if not jsonl_path:
            return
        data_dir = _default_data_dir()
        pdf_paths = self._state.get("pdf_paths") or []
        pdf_start = str(Path(pdf_paths[0]).parent) if pdf_paths and Path(pdf_paths[0]).exists() else data_dir
        pdf_path, _ = QFileDialog.getOpenFileName(
            self,
            "PDF 파일 선택 (해당 원본)",
            pdf_start,
            "PDF (*.pdf);;모든 파일 (*)",
        )
        if not pdf_path:
            return
        records = load_jsonl(jsonl_path)
        if not records:
            QMessageBox.warning(self, "검수", "JSONL에 레코드가 없습니다.")
            return
        dlg = ReviewDialog(
            pdf_path=pdf_path,
            jsonl_path=jsonl_path,
            records=records,
            parent=self,
        )
        dlg.exec()
        # 검수 후 파이프라인 상태 동기화 (이어서 Chunk 등 진행 시)
        self._jsonl_path = jsonl_path
        self._records = records
        if not self._edit_chunk_input.text().strip():
            self._edit_chunk_input.setText(jsonl_path)

    def _on_browse_chunk_input(self) -> None:
        start = self._edit_chunk_input.text().strip() or _default_output_dir(self._state)
        path, _ = QFileDialog.getOpenFileName(
            self, "원본 JSONL", start, "JSONL (*.jsonl);;모든 파일 (*)",
        )
        if path:
            self._edit_chunk_input.setText(path)

    def _on_chunk(self) -> None:
        input_path = self._edit_chunk_input.text().strip()
        if not input_path:
            self._label_chunk.setText("원본 JSONL을 선택하세요.")
            return
        records = load_jsonl(input_path)
        if not records:
            self._label_chunk.setText("JSONL에서 레코드를 읽지 못했습니다.")
            return
        target_len = self._spin_target.value()
        max_len = self._spin_max.value()
        if max_len < target_len:
            max_len = target_len
        try:
            chunks = build_chunks(
                records,
                target_len=target_len,
                max_len=max_len,
                min_chunk_len=MIN_CHUNK_LEN,
            )
        except Exception as e:
            self._label_chunk.setText(f"Chunk 생성 실패: {e}")
            return
        out_path = Path(input_path).parent / f"{Path(input_path).stem}_chunks.jsonl"
        if Path(input_path).stem.endswith("_chunks"):
            out_path = Path(input_path)
        try:
            count = write_chunk_jsonl(chunks, str(out_path))
            self._label_chunk.setText(f"저장 완료: {out_path} ({count}개 chunk)")
            self._edit_chunk_emb.setText(str(out_path))
            if not self._edit_emb_output.text().strip():
                self._edit_emb_output.setText(str(out_path.parent))
        except Exception as e:
            self._label_chunk.setText(f"저장 실패: {e}")

    def _on_browse_chunk_emb(self) -> None:
        start = self._edit_chunk_emb.text().strip() or _default_output_dir(self._state)
        path, _ = QFileDialog.getOpenFileName(
            self, "Chunk JSONL", start, "JSONL (*.jsonl);;모든 파일 (*)",
        )
        if path:
            self._edit_chunk_emb.setText(path)
            if not self._edit_emb_output.text().strip():
                self._edit_emb_output.setText(str(Path(path).parent))

    def _on_browse_emb_output(self) -> None:
        start = self._edit_emb_output.text().strip() or _default_output_dir(self._state)
        path = QFileDialog.getExistingDirectory(self, "출력 디렉터리", start)
        if path:
            self._edit_emb_output.setText(path)

    def _on_embedding(self) -> None:
        chunk_path = self._edit_chunk_emb.text().strip()
        output_dir = self._edit_emb_output.text().strip() or _default_output_dir(self._state)
        if not chunk_path:
            self._label_embedding.setText("Chunk JSONL을 선택하세요.")
            return
        self._btn_embedding.setEnabled(False)
        self._progress_embedding.setVisible(True)
        self._progress_embedding.setRange(0, 0)
        self._label_embedding.setText("임베딩 생성 중…")

        self._embedding_worker = EmbeddingWorker(chunk_path, output_dir)
        self._embedding_thread = QThread()
        self._embedding_worker.moveToThread(self._embedding_thread)
        self._embedding_thread.started.connect(self._embedding_worker.run)
        self._embedding_worker.progress.connect(self._on_emb_progress)
        self._embedding_worker.finished.connect(self._on_emb_finished)
        self._embedding_worker.error.connect(self._on_emb_error)
        self._embedding_worker.finished.connect(self._embedding_thread.quit)
        self._embedding_worker.error.connect(self._embedding_thread.quit)
        self._embedding_thread.start()

    def _on_emb_progress(self, cur: int, tot: int) -> None:
        self._progress_embedding.setMaximum(tot)
        self._progress_embedding.setValue(cur)
        self._label_embedding.setText(f"임베딩 중… {cur}/{tot}")

    def _on_emb_finished(self, idx_path: str, meta_path: str) -> None:
        self._btn_embedding.setEnabled(True)
        self._progress_embedding.setVisible(False)
        self._label_embedding.setText(f"저장 완료: {idx_path}, {meta_path}")

    def _on_emb_error(self, msg: str) -> None:
        self._btn_embedding.setEnabled(True)
        self._progress_embedding.setVisible(False)
        self._label_embedding.setText(f"오류: {msg}")

    # ---- 7. 증분 추가 ----

    def _on_browse_append_chunk(self) -> None:
        start = self._edit_append_chunk.text().strip() or _default_output_dir(self._state)
        path, _ = QFileDialog.getOpenFileName(
            self, "추가할 Chunk JSONL", start, "JSONL (*.jsonl);;모든 파일 (*)",
        )
        if path:
            self._edit_append_chunk.setText(path)

    def _on_browse_append_index(self) -> None:
        start = self._edit_append_index.text().strip() or _default_output_dir(self._state)
        path, _ = QFileDialog.getOpenFileName(
            self, "기존 인덱스 파일", start, "Index (*.index);;모든 파일 (*)",
        )
        if path:
            self._edit_append_index.setText(path)
            if not self._edit_append_meta.text().strip():
                meta_guess = str(Path(path).parent / f"{Path(path).stem}_meta.jsonl")
                self._edit_append_meta.setText(meta_guess)

    def _on_browse_append_meta(self) -> None:
        start = self._edit_append_meta.text().strip() or _default_output_dir(self._state)
        path, _ = QFileDialog.getOpenFileName(
            self, "기존 Meta JSONL", start, "JSONL (*.jsonl);;모든 파일 (*)",
        )
        if path:
            self._edit_append_meta.setText(path)

    def _on_append(self) -> None:
        chunk_path = self._edit_append_chunk.text().strip()
        index_path = self._edit_append_index.text().strip()
        meta_path = self._edit_append_meta.text().strip()

        if not chunk_path:
            self._label_append.setText("추가할 Chunk JSONL을 선택하세요.")
            return
        if not index_path:
            self._label_append.setText("기존 인덱스(.index) 파일을 선택하세요.")
            return

        self._btn_append.setEnabled(False)
        self._progress_append.setVisible(True)
        self._progress_append.setRange(0, 0)
        self._label_append.setText("증분 추가 중…")

        self._append_worker = AppendWorker(chunk_path, index_path, meta_path)
        self._append_thread = QThread()
        self._append_worker.moveToThread(self._append_thread)
        self._append_thread.started.connect(self._append_worker.run)
        self._append_worker.progress.connect(self._on_append_progress)
        self._append_worker.finished.connect(self._on_append_finished)
        self._append_worker.error.connect(self._on_append_error)
        self._append_worker.finished.connect(self._append_thread.quit)
        self._append_worker.error.connect(self._append_thread.quit)
        self._append_thread.start()

    def _on_append_progress(self, cur: int, tot: int) -> None:
        if tot > 0:
            self._progress_append.setMaximum(tot)
            self._progress_append.setValue(cur)
        self._label_append.setText(f"증분 추가 중… {cur}/{tot}")

    def _on_append_finished(self, idx_path: str, meta_path: str) -> None:
        self._btn_append.setEnabled(True)
        self._progress_append.setVisible(False)
        self._label_append.setText(f"추가 완료: {idx_path}, {meta_path}")

    def _on_append_error(self, msg: str) -> None:
        self._btn_append.setEnabled(True)
        self._progress_append.setVisible(False)
        self._label_append.setText(f"오류: {msg}")
