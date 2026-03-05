"""DB 생성 탭 — PDF→Raw→Canonical→Chunk→임베딩 통합 파이프라인 (V3)."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

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
    QListWidget,
    QListWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QTabWidget,
    QComboBox,
)

import fitz

from src.core.extract_pdf_raw import extract_raw
from src.core.mapper_factory import get_mapper
from src.core.export_jsonl import (
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
from src.core.pdf_to_images import export_pdf_to_images
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


def _find_pdf_for_doc_id(pdf_folder: str | Path, doc_id: str) -> Path | None:
    """원본 PDF 폴더에서 doc_id에 해당하는 PDF 파일 경로 반환."""
    folder = Path(pdf_folder)
    if not folder.is_dir() or not doc_id:
        return None
    cand = folder / f"{doc_id}.pdf"
    if cand.is_file():
        return cand
    name_with_spaces = doc_id.replace("_", " ")
    cand2 = folder / f"{name_with_spaces}.pdf"
    if cand2.is_file():
        return cand2
    for p in folder.glob("*.pdf"):
        if _doc_id_from_path(str(p)) == doc_id:
            return p
    return None


def _try_export_pdf_images(pdf_path: Path | str, doc_id: str, label: QLabel) -> None:
    """DB 생성 후 PDF 페이지 이미지 export. 실패 시 라벨에 경고만 표시."""
    pdf_path = Path(pdf_path)
    if not pdf_path.is_file() or not doc_id:
        return
    try:
        out_dir = _project_root() / "storage" / "pdf_images"
        out_dir.mkdir(parents=True, exist_ok=True)
        export_pdf_to_images(pdf_path, doc_id, out_dir)
        label.setText(label.text() + " (PDF 이미지 export 완료)")
    except Exception as e:
        label.setText(label.text() + f" (이미지 export 경고: {e})")


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
    """검수 창 — Raw / Canonical 탭, PDF + bbox 하이라이트 (V3)."""

    def __init__(
        self,
        pdf_path: str,
        raw_blocks: list[dict],
        canonical_records: list,
        jsonl_path: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._pdf_path = pdf_path
        self._raw_blocks = raw_blocks
        self._canonical_records = canonical_records
        self._jsonl_path = jsonl_path
        self._current_raw_index = 0
        self._current_canonical_index = 0
        self._current_pixmap: QPixmap | None = None

        self.setWindowTitle("검수 — Raw / Canonical (V3)")
        self.setMinimumSize(1100, 700)
        self.resize(1400, 800)

        layout = QVBoxLayout(self)
        self._tab_widget = QTabWidget()
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

        # Raw 검수 탭
        raw_tab = QWidget()
        raw_layout = QVBoxLayout(raw_tab)
        splitter_raw = QSplitter(Qt.Horizontal)
        left_raw = QWidget()
        left_raw_lay = QVBoxLayout(left_raw)
        left_raw_lay.setContentsMargins(0, 0, 0, 0)
        self._scroll_pdf = QScrollArea()
        self._scroll_pdf.setWidgetResizable(True)
        self._scroll_pdf.setFrameShape(QFrame.NoFrame)
        self._label_pdf_view = QLabel()
        self._label_pdf_view.setAlignment(Qt.AlignCenter)
        self._label_pdf_view.setMinimumSize(400, 500)
        self._label_pdf_view.setStyleSheet("background-color: #f0f0f0; color: #666;")
        self._label_pdf_view.setText("PDF 페이지")
        self._scroll_pdf.setWidget(self._label_pdf_view)
        self._scroll_pdf.viewport().installEventFilter(self)
        left_raw_lay.addWidget(self._scroll_pdf)
        splitter_raw.addWidget(left_raw)

        right_raw = QWidget()
        right_raw_lay = QVBoxLayout(right_raw)
        right_raw_lay.addWidget(QLabel("Raw 블록 목록"))
        self._list_raw = QListWidget()
        self._list_raw.setMinimumHeight(200)
        self._list_raw.currentRowChanged.connect(self._on_raw_row_changed)
        right_raw_lay.addWidget(self._list_raw)
        form_raw = QFormLayout()
        self._field_raw_block_id = QLineEdit()
        self._field_raw_block_id.setReadOnly(True)
        self._field_raw_page = QLineEdit()
        self._field_raw_page.setReadOnly(True)
        self._field_raw_block_type = QLineEdit()
        self._field_raw_block_type.setReadOnly(True)
        self._field_raw_text = QPlainTextEdit()
        self._field_raw_text.setMinimumHeight(120)
        self._field_raw_text.setReadOnly(True)
        form_raw.addRow("block_id:", self._field_raw_block_id)
        form_raw.addRow("page:", self._field_raw_page)
        form_raw.addRow("block_type:", self._field_raw_block_type)
        form_raw.addRow("text:", self._field_raw_text)
        right_raw_lay.addLayout(form_raw)
        splitter_raw.addWidget(right_raw)
        splitter_raw.setSizes([550, 450])
        raw_layout.addWidget(splitter_raw)
        self._tab_widget.addTab(raw_tab, "Raw")

        # Canonical 검수 탭
        canon_tab = QWidget()
        canon_layout = QVBoxLayout(canon_tab)
        splitter_canon = QSplitter(Qt.Horizontal)
        left_canon = QWidget()
        left_canon_lay = QVBoxLayout(left_canon)
        left_canon_lay.addWidget(QLabel("Canonical 계층 구조"))
        self._tree_canonical = QTreeWidget()
        self._tree_canonical.setHeaderLabels(["구조", "텍스트 미리보기"])
        self._tree_canonical.setMinimumHeight(300)
        self._tree_canonical.itemSelectionChanged.connect(self._on_canonical_item_changed)
        left_canon_lay.addWidget(self._tree_canonical)
        splitter_canon.addWidget(left_canon)

        right_canon = QWidget()
        right_canon_lay = QVBoxLayout(right_canon)
        right_canon_lay.addWidget(QLabel("선택 항목 상세"))
        form_canon = QFormLayout()
        self._field_canon_structure_path = QLineEdit()
        self._field_canon_structure_path.setReadOnly(True)
        self._field_canon_page = QLineEdit()
        self._field_canon_page.setReadOnly(True)
        self._field_canon_text = QPlainTextEdit()
        self._field_canon_text.setMinimumHeight(150)
        self._field_canon_text.setReadOnly(True)
        form_canon.addRow("structure_path:", self._field_canon_structure_path)
        form_canon.addRow("physical_page:", self._field_canon_page)
        form_canon.addRow("content.text:", self._field_canon_text)
        right_canon_lay.addLayout(form_canon)
        splitter_canon.addWidget(right_canon)
        splitter_canon.setSizes([450, 450])
        canon_layout.addWidget(splitter_canon)
        self._tab_widget.addTab(canon_tab, "Canonical")

        layout.addWidget(self._tab_widget, 1)

        btn_row = QHBoxLayout()
        self._btn_save_close = QPushButton("저장 후 닫기")
        self._btn_save_close.clicked.connect(self._on_save_and_close)
        btn_row.addWidget(self._btn_save_close)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._populate_raw_list()
        self._populate_canonical_tree()
        if self._raw_blocks:
            self._list_raw.setCurrentRow(0)
        if self._canonical_records:
            self._tree_canonical.setCurrentItem(self._tree_canonical.topLevelItem(0))
        self._refresh_all()
        self._update_nav_state()

    def _populate_raw_list(self) -> None:
        self._list_raw.clear()
        for i, blk in enumerate(self._raw_blocks):
            page = blk.get("page", "")
            btype = blk.get("block_type", "text")
            text = (blk.get("text") or "")[:80]
            if len((blk.get("text") or "")) > 80:
                text += "..."
            item = QListWidgetItem(f"[{i+1}] p.{page} {btype}: {text}")
            item.setData(Qt.ItemDataRole.UserRole, i)
            self._list_raw.addItem(item)

    def _populate_canonical_tree(self) -> None:
        self._tree_canonical.clear()
        from src.rag.citation_formatter import format_citation
        for i, rec in enumerate(self._canonical_records):
            d = rec.to_dict() if hasattr(rec, "to_dict") else rec
            structure = d.get("structure") or []
            content = d.get("content") or {}
            text = (content.get("text") or "")[:60]
            if len((content.get("text") or "")) > 60:
                text += "..."
            labels = [s.get("label", "") for s in structure if isinstance(s, dict)]
            path_str = " > ".join(labels) if labels else "(없음)"
            item = QTreeWidgetItem([path_str or f"레코드 {i+1}", text])
            item.setData(0, Qt.ItemDataRole.UserRole, i)
            self._tree_canonical.addTopLevelItem(item)

    def _on_raw_row_changed(self, row: int) -> None:
        if row >= 0 and row < len(self._raw_blocks):
            self._current_raw_index = row
            self._tab_widget.setCurrentIndex(0)
            self._refresh_pdf_view()
            self._refresh_raw_panel()

    def _on_canonical_item_changed(self) -> None:
        items = self._tree_canonical.selectedItems()
        if items:
            idx = items[0].data(0, Qt.ItemDataRole.UserRole)
            if idx is not None and 0 <= idx < len(self._canonical_records):
                self._current_canonical_index = idx
                self._refresh_canonical_panel()

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
        if self._tab_widget.currentIndex() != 0 or not self._raw_blocks:
            return
        if not (0 <= self._current_raw_index < len(self._raw_blocks)):
            page_no = 1
        else:
            page_no = self._raw_blocks[self._current_raw_index].get("page") or 1
        pix = _render_page_to_pixmap(self._pdf_path, page_no)
        if pix is not None:
            if 0 <= self._current_raw_index < len(self._raw_blocks):
                bbox = self._raw_blocks[self._current_raw_index].get("bbox")
                if isinstance(bbox, list) and len(bbox) >= 4:
                    _draw_bbox_on_pixmap(pix, bbox, dpi_scale=2.0)
            self._current_pixmap = pix
            self._scale_and_show_pdf()
        else:
            self._current_pixmap = None
            self._label_pdf_view.setText(f"페이지 {page_no} 로드 불가")

    def _refresh_raw_panel(self) -> None:
        if not (0 <= self._current_raw_index < len(self._raw_blocks)):
            return
        blk = self._raw_blocks[self._current_raw_index]
        self._field_raw_block_id.setText(str(blk.get("block_id", "")))
        self._field_raw_page.setText(str(blk.get("page", "")))
        self._field_raw_block_type.setText(str(blk.get("block_type", "text")))
        self._field_raw_text.setPlainText(str(blk.get("text", "")))

    def _refresh_canonical_panel(self) -> None:
        if not (0 <= self._current_canonical_index < len(self._canonical_records)):
            return
        rec = self._canonical_records[self._current_canonical_index]
        d = rec.to_dict() if hasattr(rec, "to_dict") else rec
        structure = d.get("structure") or []
        content = d.get("content") or {}
        labels = [s.get("label", "") for s in structure if isinstance(s, dict)]
        self._field_canon_structure_path.setText(" > ".join(labels))
        loc = d.get("location") or {}
        self._field_canon_page.setText(str(loc.get("physical_page", "")))
        self._field_canon_text.setPlainText(content.get("text", ""))

    def _refresh_all(self) -> None:
        self._refresh_pdf_view()
        self._refresh_raw_panel()
        self._refresh_canonical_panel()

    def _go_prev(self) -> None:
        tab = self._tab_widget.currentIndex()
        if tab == 0:
            if self._current_raw_index <= 0:
                return
            self._current_raw_index -= 1
            self._list_raw.setCurrentRow(self._current_raw_index)
        else:
            if self._current_canonical_index <= 0:
                return
            self._current_canonical_index -= 1
            self._tree_canonical.setCurrentItem(self._tree_canonical.topLevelItem(self._current_canonical_index))
        self._refresh_all()
        self._update_nav_state()

    def _go_next(self) -> None:
        tab = self._tab_widget.currentIndex()
        if tab == 0:
            if not self._raw_blocks or self._current_raw_index >= len(self._raw_blocks) - 1:
                return
            self._current_raw_index += 1
            self._list_raw.setCurrentRow(self._current_raw_index)
        else:
            if not self._canonical_records or self._current_canonical_index >= len(self._canonical_records) - 1:
                return
            self._current_canonical_index += 1
            self._tree_canonical.setCurrentItem(self._tree_canonical.topLevelItem(self._current_canonical_index))
        self._refresh_all()
        self._update_nav_state()

    def _update_nav_state(self) -> None:
        tab = self._tab_widget.currentIndex()
        if tab == 0:
            total = len(self._raw_blocks)
            idx = self._current_raw_index
        else:
            total = len(self._canonical_records)
            idx = self._current_canonical_index
        if total == 0:
            self._label_progress.setText("— / —")
            self._btn_prev.setEnabled(False)
            self._btn_next.setEnabled(False)
            return
        self._label_progress.setText(f"{idx + 1} / {total}")
        self._btn_prev.setEnabled(idx > 0)
        self._btn_next.setEnabled(idx < total - 1)

    def _on_save_and_close(self) -> None:
        records = [r.to_dict() if hasattr(r, "to_dict") else r for r in self._canonical_records]
        if not records:
            QMessageBox.information(self, "저장", "저장할 레코드가 없습니다.")
            return
        try:
            n = write_records_jsonl(records, self._jsonl_path)
            QMessageBox.information(self, "저장", f"저장했습니다. ({n}개 Canonical 레코드)")
        except Exception as e:
            QMessageBox.critical(self, "저장 실패", str(e))
            return
        self.accept()


class ExtractWorker(QObject):
    progress = Signal(int, int)
    finished = Signal(list)
    error = Signal(str)

    def __init__(
        self,
        pdf_path: str,
        doc_id: str,
        after_toc: bool,
        exclude_header_footer: bool,
        table_caption_only: bool,
        figure_caption_only: bool,
        exclude_equation: bool,
        *,
        new_section_pattern=None,
        parent=None,
    ):
        super().__init__(parent)
        self._pdf_path = pdf_path
        self._doc_id = doc_id
        self._after_toc = after_toc
        self._exclude_header_footer = exclude_header_footer
        self._table_caption_only = table_caption_only
        self._figure_caption_only = figure_caption_only
        self._exclude_equation = exclude_equation
        self._new_section_pattern = new_section_pattern

    def run(self) -> None:
        try:
            blocks = extract_raw(
                self._pdf_path,
                doc_id=self._doc_id or "",
                after_toc=self._after_toc,
                exclude_header_footer=self._exclude_header_footer,
                table_caption_only=self._table_caption_only,
                figure_caption_only=self._figure_caption_only,
                exclude_equation=self._exclude_equation,
                new_section_pattern=self._new_section_pattern,
                progress_callback=lambda c, t: self.progress.emit(c, t),
            )
            self.finished.emit(blocks)
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
    """DB 생성 탭 — Import → Raw 추출 → Canonical 변환 → 검수 → Chunk → 임베딩 (V3)."""

    def __init__(self, app_state: dict | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = app_state or {}
        self._jsonl_path: str = ""
        self._raw_blocks: list[dict] = []
        self._canonical_records: list = []
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
        row_doc_type = QHBoxLayout()
        row_doc_type.addWidget(QLabel("문서 타입:"))
        self._combo_doc_type = QComboBox()
        self._combo_doc_type.addItem("해양규칙 (marine)", "marine")
        self._combo_doc_type.addItem("법령 (statute)", "statute")
        self._combo_doc_type.setToolTip("해양규칙: 101. 형식 / 법령: 제 N조 형식")
        self._combo_doc_type.currentIndexChanged.connect(self._on_doc_type_changed)
        self._state["doc_type"] = self._combo_doc_type.currentData() or "marine"
        row_doc_type.addWidget(self._combo_doc_type)
        row_doc_type.addStretch()
        imp_layout.addLayout(row_doc_type)
        layout.addWidget(group_import)

        # 2. Raw 추출
        group_extract = QGroupBox("2. Raw 추출 — PDF → Raw JSONL")
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
        ext_layout.addWidget(QLabel("Raw 미리보기 (block_id, page, block_type, text):"))
        self._list_raw_preview = QListWidget()
        self._list_raw_preview.setMaximumHeight(150)
        ext_layout.addWidget(self._list_raw_preview)
        layout.addWidget(group_extract)

        # 3. Canonical 변환
        group_parse = QGroupBox("3. Canonical 변환 — Raw → Canonical")
        parse_layout = QVBoxLayout(group_parse)
        row_parse_btn = QHBoxLayout()
        self._btn_parse = QPushButton("변환 실행")
        self._btn_parse.clicked.connect(self._on_parse)
        self._label_parse = QLabel("Raw 추출 후 실행하세요.")
        self._label_parse.setStyleSheet("color: #666;")
        row_parse_btn.addWidget(self._btn_parse)
        row_parse_btn.addWidget(self._label_parse, 1)
        parse_layout.addLayout(row_parse_btn)
        parse_layout.addWidget(QLabel("Canonical 미리보기 (선택 시 우측에 상세 표시):"))
        parse_split = QSplitter(Qt.Horizontal)
        self._tree_canonical_preview = QTreeWidget()
        self._tree_canonical_preview.setHeaderLabels(["구조", "텍스트 미리보기"])
        self._tree_canonical_preview.setMinimumHeight(120)
        self._tree_canonical_preview.itemSelectionChanged.connect(self._on_canonical_preview_selected)
        parse_split.addWidget(self._tree_canonical_preview)
        self._field_canonical_detail = QPlainTextEdit()
        self._field_canonical_detail.setMinimumHeight(120)
        self._field_canonical_detail.setReadOnly(True)
        self._field_canonical_detail.setPlaceholderText("선택 항목: structure_path, physical_page, content.text")
        parse_split.addWidget(self._field_canonical_detail)
        parse_split.setSizes([300, 250])
        parse_layout.addWidget(parse_split)
        layout.addWidget(group_parse)

        # 4. Export + 검수
        group_export = QGroupBox("4. Export & 검수")
        exp_layout = QVBoxLayout(group_export)
        row_exp = QHBoxLayout()
        self._btn_export = QPushButton("Canonical JSONL 저장")
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
        self._label_export = QLabel("Canonical 변환 후 JSONL 저장하세요.")
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
        raw_blocks = self._state.get("raw_blocks", [])
        canonical = self._state.get("canonical_records", [])
        self._btn_extract.setEnabled(bool(paths))
        self._btn_parse.setEnabled(bool(raw_blocks))
        self._btn_export.setEnabled(bool(canonical))

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

        # Phase 6: 추출 직전 Dry-run (5페이지만) → check_compatibility
        try:
            dry_blocks = extract_raw(
                paths[0],
                doc_id=self._edit_doc_id.text().strip() or _doc_id_from_path(paths[0]) or "",
                after_toc=self._check_after_toc.isChecked(),
                exclude_header_footer=self._check_header_footer.isChecked(),
                table_caption_only=self._check_table.isChecked(),
                figure_caption_only=self._check_figure.isChecked(),
                exclude_equation=self._check_equation.isChecked(),
                max_pages=5,
            )
        except Exception as e:
            self._label_extract.setText(f"Dry-run 실패: {e}")
            return
        doc_type = self._state.get("doc_type", "marine")
        mapper = get_mapper(doc_type)
        compatible, count = mapper.check_compatibility(dry_blocks, max_pages=5)
        if not compatible:
            logger.warning("매퍼 호환성 검사: %s, 불일치, 패턴 %d건 발견", doc_type, count)
            box = QMessageBox(self)
            box.setWindowTitle("매퍼 불일치")
            box.setText(
                "선택한 문서 타입과 실제 문서 형식이 맞지 않을 수 있습니다.\n\n"
                "해양규칙: 101., 202. 형식\n"
                "법령: 제 1조, 제 2조 형식\n\n"
                "강제 진행하시겠습니까?"
            )
            box.setIcon(QMessageBox.Icon.Warning)
            box.setStandardButtons(QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Ok)
            box.button(QMessageBox.StandardButton.Ok).setText("강제 진행")
            box.button(QMessageBox.StandardButton.Cancel).setText("중단")
            if box.exec() != QMessageBox.StandardButton.Ok:
                self._label_extract.setText("추출 중단 — 매퍼 불일치.")
                return
        else:
            logger.info("매퍼 호환성 검사: %s, 호환됨, 패턴 %d건 발견", doc_type, count)

        self._btn_extract.setEnabled(False)
        self._progress_extract.setVisible(True)
        self._progress_extract.setRange(0, 0)
        self._label_extract.setText("추출 중…")

        doc_id = self._edit_doc_id.text().strip() or _doc_id_from_path(paths[0])
        section_pattern = mapper.get_section_pattern()
        self._extract_worker = ExtractWorker(
            paths[0],
            doc_id,
            self._state["after_toc"],
            self._check_header_footer.isChecked(),
            self._check_table.isChecked(),
            self._check_figure.isChecked(),
            self._check_equation.isChecked(),
            new_section_pattern=section_pattern,
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

    def _on_extract_finished(self, blocks: list) -> None:
        self._state["raw_blocks"] = blocks
        self._raw_blocks = blocks
        self._btn_extract.setEnabled(True)
        self._progress_extract.setVisible(False)
        n = len(blocks)
        self._label_extract.setText(f"완료: {n}개 Raw 블록 추출됨.")
        self._list_raw_preview.clear()
        for i, blk in enumerate(blocks[:100]):  # 최대 100개 미리보기
            page = blk.get("page", "")
            btype = blk.get("block_type", "text")
            text = (blk.get("text") or "")[:50]
            if len((blk.get("text") or "")) > 50:
                text += "..."
            self._list_raw_preview.addItem(QListWidgetItem(f"[{i+1}] p.{page} {btype}: {text}"))
        if len(blocks) > 100:
            self._list_raw_preview.addItem(QListWidgetItem(f"... 외 {len(blocks)-100}개"))
        self._update_step_states()

    def _on_extract_error(self, msg: str) -> None:
        self._btn_extract.setEnabled(True)
        self._progress_extract.setVisible(False)
        self._label_extract.setText(f"오류: {msg}")

    def _on_doc_type_changed(self) -> None:
        val = self._combo_doc_type.currentData()
        if val is not None:
            self._state["doc_type"] = val

    def _run_mapper_compatibility_check(self) -> bool:
        """
        매퍼 호환성 검사. raw_blocks가 있으면 check_compatibility 실행.
        불일치 시 QMessageBox로 [중단]/[강제 진행] 선택.
        Returns: True=진행, False=중단
        """
        raw_blocks = self._state.get("raw_blocks", [])
        if not raw_blocks:
            return True
        doc_type = self._state.get("doc_type", "marine")
        mapper = get_mapper(doc_type)
        compatible, count = mapper.check_compatibility(raw_blocks, max_pages=5)
        if compatible:
            logger.info("매퍼 호환성 검사: %s, 호환됨, 패턴 %d건 발견", doc_type, count)
            return True
        logger.warning("매퍼 호환성 검사: %s, 불일치, 패턴 %d건 발견", doc_type, count)
        box = QMessageBox(self)
        box.setWindowTitle("매퍼 불일치")
        box.setText(
            "선택한 문서 타입과 실제 문서 형식이 맞지 않을 수 있습니다.\n\n"
            "해양규칙: 101., 202. 형식\n"
            "법령: 제 1조, 제 2조 형식\n\n"
            "강제 진행하시겠습니까?"
        )
        box.setIcon(QMessageBox.Icon.Warning)
        box.setStandardButtons(QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Ok)
        box.button(QMessageBox.StandardButton.Ok).setText("강제 진행")
        box.button(QMessageBox.StandardButton.Cancel).setText("중단")
        ret = box.exec()
        return ret == QMessageBox.StandardButton.Ok

    def _on_parse(self) -> None:
        raw_blocks = self._state.get("raw_blocks", [])
        if not raw_blocks:
            self._label_parse.setText("Raw 추출을 먼저 실행하세요.")
            return
        doc_type = self._state.get("doc_type", "marine")
        pdf_paths = self._state.get("pdf_paths", [])
        source_file = Path(pdf_paths[0]).name if pdf_paths else "unknown.pdf"
        source_meta = {"file_name": source_file}
        mapper = get_mapper(doc_type)
        canonical = mapper.map_to_canonical(raw_blocks, source_meta, doc_type=doc_type)
        self._state["canonical_records"] = canonical
        self._canonical_records = canonical
        self._label_parse.setText(f"완료: {len(canonical)}개 Canonical 레코드 변환.")
        self._tree_canonical_preview.clear()
        for i, rec in enumerate(canonical[:80]):
            d = rec.to_dict()
            structure = d.get("structure") or []
            content = d.get("content") or {}
            text = (content.get("text") or "")[:40]
            if len((content.get("text") or "")) > 40:
                text += "..."
            labels = [s.get("label", "") for s in structure if isinstance(s, dict)]
            path_str = " > ".join(labels) if labels else "(없음)"
            item = QTreeWidgetItem([path_str or f"레코드 {i+1}", text])
            item.setData(0, Qt.ItemDataRole.UserRole, i)
            self._tree_canonical_preview.addTopLevelItem(item)
        if len(canonical) > 80:
            self._tree_canonical_preview.addTopLevelItem(QTreeWidgetItem([f"... 외 {len(canonical)-80}개", ""]))
        self._update_step_states()

    def _on_canonical_preview_selected(self) -> None:
        items = self._tree_canonical_preview.selectedItems()
        if not items or not self._canonical_records:
            self._field_canonical_detail.clear()
            return
        idx = items[0].data(0, Qt.ItemDataRole.UserRole)
        if idx is None or not (0 <= idx < len(self._canonical_records)):
            return
        rec = self._canonical_records[idx]
        d = rec.to_dict()
        structure = d.get("structure") or []
        content = d.get("content") or {}
        loc = d.get("location") or {}
        labels = [s.get("label", "") for s in structure]
        lines = [
            "structure_path: " + (" > ".join(labels) if labels else "(없음)"),
            "physical_page: " + str(loc.get("physical_page", "")),
            "content.text: " + (content.get("text", "")[:200] or ""),
        ]
        if len(content.get("text", "")) > 200:
            lines[-1] += "..."
        self._field_canonical_detail.setPlainText("\n".join(lines))

    def _on_export(self) -> None:
        canonical = self._state.get("canonical_records", [])
        if not canonical:
            self._label_export.setText("Canonical 변환을 먼저 실행하세요.")
            return
        doc_id = (self._state.get("doc_id") or "").strip() or "export"
        output_dir = Path(self._edit_output.text().strip() or _default_output_dir(self._state))
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / f"{doc_id}.jsonl"
        try:
            records = [r.to_dict() if hasattr(r, "to_dict") else r for r in canonical]
            count = write_records_jsonl(records, out_path)
            self._jsonl_path = str(out_path)
            self._label_export.setText(f"저장 완료: {out_path} ({count}개 Canonical 레코드)")
            self._edit_chunk_input.setText(self._jsonl_path)
        except Exception as e:
            self._label_export.setText(f"저장 실패: {e}")
            return

    def _on_open_review(self) -> None:
        """검수 창 열기 — Raw/Canonical 탭, bbox 하이라이트."""
        raw_blocks = self._state.get("raw_blocks", [])
        canonical = self._state.get("canonical_records", [])
        pdf_paths = self._state.get("pdf_paths", [])
        if not pdf_paths or not Path(pdf_paths[0]).exists():
            QMessageBox.warning(self, "검수", "PDF를 먼저 선택하세요.")
            return
        pdf_path = pdf_paths[0]
        if not raw_blocks or not canonical:
            QMessageBox.warning(self, "검수", "Raw 추출 및 Canonical 변환을 먼저 실행하세요.")
            return
        jsonl_path = self._jsonl_path or str(
            Path(self._edit_output.text().strip() or _default_output_dir(self._state))
            / f"{(self._state.get('doc_id') or 'export').strip() or 'export'}.jsonl"
        )
        dlg = ReviewDialog(
            pdf_path=pdf_path,
            raw_blocks=raw_blocks,
            canonical_records=canonical,
            jsonl_path=jsonl_path,
            parent=self,
        )
        if dlg.exec():
            self._canonical_records = [r for r in canonical]  # 검수에서 수정 가능 시 반영
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
        if not self._run_mapper_compatibility_check():
            return
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
        if not self._run_mapper_compatibility_check():
            return
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

        # Phase 5: DB 생성 시점에 PDF 페이지 이미지 export (웹 뷰어용)
        chunk_path = self._edit_chunk_emb.text().strip()
        doc_id = (self._state.get("doc_id") or "").strip()
        if not doc_id and chunk_path:
            stem = Path(chunk_path).stem
            if stem.endswith("_chunks"):
                doc_id = stem[: -len("_chunks")]
            else:
                chunks = load_jsonl(chunk_path)
                if chunks and isinstance(chunks[0], dict):
                    doc_id = chunks[0].get("doc_id") or ""
                if not doc_id:
                    doc_id = stem
        pdf_path = None
        if self._state.get("pdf_paths"):
            p = Path(self._state["pdf_paths"][0])
            if p.is_file():
                pdf_path = p
        if not pdf_path and doc_id:
            for folder in [_project_root() / "data", Path(idx_path).parent.parent]:
                pdf_path = _find_pdf_for_doc_id(folder, doc_id)
                if pdf_path:
                    break
        if pdf_path and doc_id:
            _try_export_pdf_images(pdf_path, doc_id, self._label_embedding)

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
