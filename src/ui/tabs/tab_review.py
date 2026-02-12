"""검수 탭 — PDF·JSONL 로드, 좌 PDF / 우 JSON 필드 뷰."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, QEvent, QRectF
from PySide6.QtGui import QColor, QImage, QKeySequence, QPainter, QPen, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QPushButton,
    QLineEdit,
    QLabel,
    QFileDialog,
    QSplitter,
    QScrollArea,
    QFormLayout,
    QPlainTextEdit,
    QFrame,
    QMessageBox,
)

import fitz

from src.core.export_jsonl import load_jsonl, write_records_jsonl


def _project_root() -> Path:
    """프로젝트 루트 디렉터리 (tab_review.py 기준 4단계 상위)."""
    return Path(__file__).resolve().parents[3]


def _default_pdf_dir() -> str:
    """PDF 파일 대화상자 초기 경로: data."""
    return str(_project_root() / "data")


def _default_jsonl_dir() -> str:
    """JSONL 파일 대화상자 초기 경로: output"""
    root = _project_root()
    backup = root / "output"
    if backup.is_dir():
        return str(backup)
    return str(root / "output" / "backup")


def _render_page_to_pixmap(pdf_path: str | Path, page_no: int, dpi_scale: float = 2.0) -> QPixmap | None:
    """PDF의 지정 페이지를 이미지로 렌더링해 QPixmap으로 반환. 1-based page_no."""
    pdf_path = Path(pdf_path)
    if not pdf_path.is_file() or page_no < 1:
        return None
    try:
        doc = fitz.open(pdf_path)
        try:
            page = doc[page_no - 1]
            mat = fitz.Matrix(dpi_scale, dpi_scale)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            fmt = QImage.Format_RGB888
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt).copy()
            return QPixmap.fromImage(img)
        finally:
            doc.close()
    except Exception:
        return None
    return None


def _draw_bbox_on_pixmap(
    pixmap: QPixmap, bbox: list[float], dpi_scale: float = 2.0, margin_pt: float = 3.0
) -> None:
    """PDF 좌표 bbox [x0,y0,x1,y1]를 pixmap 위에 빨간색 굵은 사각형으로 그린다 (in-place). margin_pt만큼 확대."""
    if not bbox or len(bbox) < 4:
        return
    x0, y0, x1, y1 = bbox[0], bbox[1], bbox[2], bbox[3]
    x0 -= margin_pt
    y0 -= margin_pt
    x1 += margin_pt
    y1 += margin_pt
    s = dpi_scale
    r = QRectF(x0 * s, y0 * s, (x1 - x0) * s, (y1 - y0) * s)
    painter = QPainter(pixmap)
    painter.setPen(QPen(QColor("#cc0000"), 5, Qt.PenStyle.SolidLine))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRect(r)
    painter.end()


def _format_path(path: dict | None) -> str:
    """path 딕셔너리를 한 줄 문자열로."""
    if not path:
        return ""
    return json.dumps(path, ensure_ascii=False)


def _format_bbox(bbox: list | None) -> str:
    if bbox is not None and len(bbox) >= 4:
        return f"[{bbox[0]:.2f}, {bbox[1]:.2f}, {bbox[2]:.2f}, {bbox[3]:.2f}]"
    return str(bbox) if bbox else ""


def _format_source(source: dict | None) -> str:
    if not source:
        return ""
    return json.dumps(source, ensure_ascii=False)


class TabReview(QWidget):
    """검수 탭 — PDF·JSONL 선택, 좌측 PDF 페이지, 우측 현재 라인 필드(text/path 편집 가능, 저장 지원)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pdf_path: str = ""
        self._jsonl_path: str = ""
        self._records: list[dict] = []
        self._current_index: int = 0
        self._current_pixmap: QPixmap | None = None  # 현재 페이지 원본(뷰에 맞춰 스케일해 표시)

        layout = QVBoxLayout(self)

        # 파일 선택 그룹
        group_files = QGroupBox("파일")
        file_layout = QVBoxLayout(group_files)

        row_pdf = QHBoxLayout()
        self._btn_pdf = QPushButton("PDF 선택")
        self._btn_pdf.clicked.connect(self._on_select_pdf)
        self._edit_pdf = QLineEdit()
        self._edit_pdf.setPlaceholderText("PDF 파일 경로")
        self._edit_pdf.setReadOnly(True)
        row_pdf.addWidget(self._btn_pdf)
        row_pdf.addWidget(self._edit_pdf, 1)
        file_layout.addLayout(row_pdf)

        row_jsonl = QHBoxLayout()
        self._btn_jsonl = QPushButton("JSONL 선택")
        self._btn_jsonl.clicked.connect(self._on_select_jsonl)
        self._edit_jsonl = QLineEdit()
        self._edit_jsonl.setPlaceholderText("JSONL 파일 경로 (Export로 생성)")
        self._edit_jsonl.setReadOnly(True)
        row_jsonl.addWidget(self._btn_jsonl)
        row_jsonl.addWidget(self._edit_jsonl, 1)
        file_layout.addLayout(row_jsonl)

        layout.addWidget(group_files)

        # 진행도 + 이전/다음 네비게이션
        nav_layout = QHBoxLayout()
        self._label_progress = QLabel("— / —")
        self._label_progress.setStyleSheet("font-weight: bold; min-width: 120px;")
        self._btn_prev = QPushButton("◀ 이전")
        self._btn_prev.clicked.connect(self._go_prev)
        self._btn_next = QPushButton("다음 ▶")
        self._btn_next.clicked.connect(self._go_next)
        nav_layout.addWidget(self._label_progress)
        nav_layout.addWidget(self._btn_prev)
        nav_layout.addWidget(self._btn_next)
        nav_layout.addStretch()
        layout.addLayout(nav_layout)

        # 키보드 좌우 화살표
        QShortcut(QKeySequence(Qt.Key_Left), self, self._go_prev, context=Qt.WidgetWithChildrenShortcut)
        QShortcut(QKeySequence(Qt.Key_Right), self, self._go_next, context=Qt.WidgetWithChildrenShortcut)

        # 좌우 분할: 좌 PDF, 우 필드
        splitter = QSplitter(Qt.Horizontal)

        # 좌측 — PDF 페이지 이미지
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self._scroll_pdf = QScrollArea()
        self._scroll_pdf.setWidgetResizable(True)
        self._scroll_pdf.setFrameShape(QFrame.NoFrame)
        self._label_pdf = QLabel()
        self._label_pdf.setAlignment(Qt.AlignCenter)
        self._label_pdf.setMinimumSize(200, 300)
        self._label_pdf.setStyleSheet("background-color: #f0f0f0; color: #666;")
        self._label_pdf.setText("PDF를 선택하면 해당 페이지가 표시됩니다.")
        self._label_pdf.setScaledContents(False)
        self._scroll_pdf.setWidget(self._label_pdf)
        self._scroll_pdf.viewport().installEventFilter(self)
        left_layout.addWidget(self._scroll_pdf)
        splitter.addWidget(left_widget)

        # 우측 — 현재 라인 필드 (읽기 전용)
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.addWidget(QLabel("현재 라인 (레코드)"))
        form = QFormLayout()
        self._field_doc_id = QLineEdit()
        self._field_doc_id.setReadOnly(True)
        self._field_page = QLineEdit()
        self._field_page.setReadOnly(True)
        self._field_line_no = QLineEdit()
        self._field_line_no.setReadOnly(True)
        self._field_path = QPlainTextEdit()
        self._field_path.setMaximumHeight(120)
        self._field_text = QPlainTextEdit()
        self._field_text.setMinimumHeight(120)
        self._field_bbox = QLineEdit()
        self._field_bbox.setReadOnly(True)
        self._field_source = QLineEdit()
        self._field_source.setReadOnly(True)
        form.addRow("doc_id:", self._field_doc_id)
        form.addRow("page:", self._field_page)
        form.addRow("line_no:", self._field_line_no)
        form.addRow("path:", self._field_path)
        form.addRow("text:", self._field_text)
        form.addRow("bbox:", self._field_bbox)
        form.addRow("source:", self._field_source)
        right_layout.addLayout(form)
        # 저장 버튼
        btn_layout = QHBoxLayout()
        self._btn_save = QPushButton("저장")
        self._btn_save.clicked.connect(self._on_save)
        self._btn_save_as = QPushButton("다른 이름으로 저장")
        self._btn_save_as.clicked.connect(self._on_save_as)
        btn_layout.addWidget(self._btn_save)
        btn_layout.addWidget(self._btn_save_as)
        btn_layout.addStretch()
        right_layout.addLayout(btn_layout)
        splitter.addWidget(right_widget)

        splitter.setSizes([400, 400])
        layout.addWidget(splitter, 1)

        self.setLayout(layout)
        self._update_nav_state()

    def eventFilter(self, obj: QWidget, event: QEvent) -> bool:
        """뷰포트 리사이즈 시 PDF 이미지를 다시 맞춰 그리기."""
        if obj is self._scroll_pdf.viewport() and event.type() == QEvent.Type.Resize:
            self._scale_and_show_pdf()
        return super().eventFilter(obj, event)

    def _scale_and_show_pdf(self) -> None:
        """_current_pixmap을 뷰포트에 맞춰 스케일한 뒤 라벨에 표시 (한 페이지 전체가 보이게)."""
        if self._current_pixmap is None or self._current_pixmap.isNull():
            return
        vp = self._scroll_pdf.viewport()
        size = vp.size()
        if size.width() <= 0 or size.height() <= 0:
            return
        scaled = self._current_pixmap.scaled(
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._label_pdf.setPixmap(scaled)
        self._label_pdf.setText("")

    def _on_select_pdf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "PDF 파일 선택",
            _default_pdf_dir(),
            "PDF (*.pdf);;모든 파일 (*)",
        )
        if path:
            self._pdf_path = path
            self._edit_pdf.setText(path)
            self._refresh_pdf_view()

    def _on_select_jsonl(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "JSONL 파일 선택",
            _default_jsonl_dir(),
            "JSONL (*.jsonl);;모든 파일 (*)",
        )
        if path:
            self._jsonl_path = path
            self._edit_jsonl.setText(path)
            self._records = load_jsonl(path)
            self._current_index = 0
            self._refresh_right_panel()
            self._refresh_pdf_view()
            self._update_nav_state()

    def _update_nav_state(self) -> None:
        """진행도 라벨 갱신, 첫/끝에서 이전/다음 버튼 비활성."""
        total = len(self._records)
        if total == 0:
            self._label_progress.setText("— / —")
            self._btn_prev.setEnabled(False)
            self._btn_next.setEnabled(False)
            return
        # 1-based 표시: "1 / 1592"
        self._label_progress.setText(f"{self._current_index + 1} / {total}")
        self._btn_prev.setEnabled(self._current_index > 0)
        self._btn_next.setEnabled(self._current_index < total - 1)

    def _flush_current_to_record(self) -> None:
        """현재 위젯 값을 _records[_current_index]에 반영 (편집 내용 메모리 유지)."""
        if not self._records or not (0 <= self._current_index < len(self._records)):
            return
        rec = self._records[self._current_index]
        rec["text"] = self._field_text.toPlainText()
        path_text = self._field_path.toPlainText().strip()
        if path_text:
            try:
                rec["path"] = json.loads(path_text)
            except json.JSONDecodeError:
                pass  # 파싱 실패 시 기존 path 유지

    def _go_prev(self) -> None:
        """이전 라인으로 이동."""
        self._flush_current_to_record()
        if self._current_index <= 0:
            return
        self._current_index -= 1
        self._refresh_right_panel()
        self._refresh_pdf_view()
        self._update_nav_state()

    def _go_next(self) -> None:
        """다음 라인으로 이동."""
        self._flush_current_to_record()
        if not self._records or self._current_index >= len(self._records) - 1:
            return
        self._current_index += 1
        self._refresh_right_panel()
        self._refresh_pdf_view()
        self._update_nav_state()

    def _refresh_pdf_view(self) -> None:
        """현재 레코드의 page에 해당하는 PDF 페이지를 좌측에 표시 (한 페이지 전체가 보이게)."""
        if not self._pdf_path:
            self._current_pixmap = None
            self._label_pdf.clear()
            self._label_pdf.setText("PDF를 선택하면 해당 페이지가 표시됩니다.")
            return
        page_no = 1
        if self._records and 0 <= self._current_index < len(self._records):
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
            self._label_pdf.clear()
            self._label_pdf.setText(f"페이지 {page_no}를 불러올 수 없습니다.")

    def _refresh_right_panel(self) -> None:
        """우측 필드를 현재 레코드로 갱신."""
        if not self._records or not (0 <= self._current_index < len(self._records)):
            self._field_doc_id.clear()
            self._field_page.clear()
            self._field_line_no.clear()
            self._field_path.clear()
            self._field_text.clear()
            self._field_bbox.clear()
            self._field_source.clear()
            return
        rec = self._records[self._current_index]
        self._field_doc_id.setText(str(rec.get("doc_id", "")))
        self._field_page.setText(str(rec.get("page", "")))
        self._field_line_no.setText(str(rec.get("line_no", "")))
        self._field_path.setPlainText(_format_path(rec.get("path")))
        self._field_text.setPlainText(str(rec.get("text", "")))
        self._field_bbox.setText(_format_bbox(rec.get("bbox")))
        self._field_source.setText(_format_source(rec.get("source")))

    def _on_save(self) -> None:
        """현재 레코드 리스트를 JSONL 파일에 덮어쓴다."""
        self._flush_current_to_record()
        if not self._records:
            QMessageBox.information(self, "저장", "저장할 레코드가 없습니다.")
            return
        if not self._jsonl_path:
            self._on_save_as()
            return
        try:
            n = write_records_jsonl(self._records, self._jsonl_path)
            QMessageBox.information(self, "저장", f"저장했습니다. ({n}개 레코드)")
        except Exception as e:
            QMessageBox.critical(self, "저장 실패", str(e))

    def _on_save_as(self) -> None:
        """다른 경로에 JSONL로 저장한다."""
        self._flush_current_to_record()
        if not self._records:
            QMessageBox.information(self, "다른 이름으로 저장", "저장할 레코드가 없습니다.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "다른 이름으로 저장",
            _default_jsonl_dir(),
            "JSONL (*.jsonl);;모든 파일 (*)",
        )
        if not path:
            return
        try:
            n = write_records_jsonl(self._records, path)
            self._jsonl_path = path
            self._edit_jsonl.setText(path)
            QMessageBox.information(self, "저장", f"저장했습니다. ({n}개 레코드)")
        except Exception as e:
            QMessageBox.critical(self, "저장 실패", str(e))
