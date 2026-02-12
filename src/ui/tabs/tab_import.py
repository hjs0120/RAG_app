"""Import 탭 — PDF 파일 선택, doc_id, 출력 경로, 차례 이후 옵션."""

import os

from PySide6.QtCore import QThread, Signal, QObject
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QPushButton,
    QLineEdit,
    QLabel,
    QCheckBox,
    QFileDialog,
    QListWidget,
    QListWidgetItem,
)
from src.core.extract_pymupdf import extract_lines
from src.core.toc_detector import detect_toc_start


class TocPreviewWorker(QObject):
    """백그라운드에서 전체 라인 추출 후 차례/본문 시작점 탐지."""

    progress = Signal(int, int)
    finished = Signal(object)  # (toc_page, toc_ln, body_page, body_ln) or None
    error = Signal(str)

    def __init__(self, pdf_path: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pdf_path = pdf_path

    def run(self) -> None:
        try:
            lines = extract_lines(
                self._pdf_path,
                after_toc=False,
                progress_callback=lambda c, t: self.progress.emit(c, t),
            )
            toc_idx, body_idx = detect_toc_start(lines)
            if toc_idx is not None and body_idx is not None:
                toc_page = lines[toc_idx].get("page", 0)
                toc_ln = lines[toc_idx].get("line_no", 0)
                body_page = lines[body_idx].get("page", 0)
                body_ln = lines[body_idx].get("line_no", 0)
                self.finished.emit((toc_page, toc_ln, body_page, body_ln))
            else:
                self.finished.emit(None)
        except Exception as e:
            self.error.emit(str(e))


def _doc_id_from_path(path: str) -> str:
    """파일 경로에서 doc_id 후보 생성. 확장자 제거, 공백을 _로."""
    name = os.path.splitext(os.path.basename(path))[0]
    return name.replace(" ", "_").replace(".", "_")


class TabImport(QWidget):
    """Import 탭 — 파일 선택, doc_id, 출력 경로, 차례 이후부터 체크."""

    def __init__(self, app_state: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = app_state
        layout = QVBoxLayout(self)

        # Group: 입력
        group_input = QGroupBox("입력")
        input_layout = QVBoxLayout(group_input)

        row_files = QHBoxLayout()
        self._btn_select = QPushButton("파일 선택")
        self._btn_select.clicked.connect(self._on_select_files)
        self._label_paths = QLabel("선택된 파일 없음")
        self._label_paths.setWordWrap(True)
        self._label_paths.setStyleSheet("color: #666;")
        row_files.addWidget(self._btn_select)
        row_files.addWidget(self._label_paths, 1)
        input_layout.addLayout(row_files)

        self._file_list = QListWidget()
        self._file_list.setMaximumHeight(80)
        input_layout.addWidget(self._file_list)

        row_doc_id = QHBoxLayout()
        row_doc_id.addWidget(QLabel("doc_id:"))
        self._edit_doc_id = QLineEdit()
        self._edit_doc_id.setPlaceholderText("자동 생성되거나 수동 입력")
        self._edit_doc_id.textChanged.connect(self._on_doc_id_changed)
        row_doc_id.addWidget(self._edit_doc_id)
        input_layout.addLayout(row_doc_id)

        row_output = QHBoxLayout()
        row_output.addWidget(QLabel("출력 디렉터리:"))
        self._edit_output = QLineEdit()
        self._edit_output.setText(self._state.get("output_dir", "output"))
        self._edit_output.textChanged.connect(self._on_output_changed)
        btn_browse = QPushButton("찾아보기")
        btn_browse.clicked.connect(self._on_browse_output)
        row_output.addWidget(self._edit_output, 1)
        row_output.addWidget(btn_browse)
        input_layout.addLayout(row_output)

        layout.addWidget(group_input)

        # Group: 처리 범위
        group_scope = QGroupBox("처리 범위")
        scope_layout = QVBoxLayout(group_scope)
        self._check_after_toc = QCheckBox("차례 이후부터")
        self._check_after_toc.setChecked(self._state.get("after_toc", True))
        self._check_after_toc.toggled.connect(self._on_after_toc_changed)
        scope_layout.addWidget(self._check_after_toc)
        row_preview = QHBoxLayout()
        self._btn_toc_preview = QPushButton("시작점 미리보기")
        self._btn_toc_preview.clicked.connect(self._on_toc_preview)
        self._label_toc_preview = QLabel("(미리보기 버튼 클릭 시 차례/본문 시작 위치 표시)")
        self._label_toc_preview.setWordWrap(True)
        self._label_toc_preview.setStyleSheet("color: #666;")
        row_preview.addWidget(self._btn_toc_preview)
        row_preview.addWidget(self._label_toc_preview, 1)
        scope_layout.addLayout(row_preview)
        layout.addWidget(group_scope)

        layout.addStretch()

        self._toc_preview_thread: QThread | None = None
        self._toc_preview_worker: TocPreviewWorker | None = None

        # 초기값 동기화
        self._edit_output.setText(self._state.get("output_dir", "output"))
        self._sync_from_state()

    def _sync_from_state(self) -> None:
        """app_state → UI 반영."""
        paths = self._state.get("pdf_paths", [])
        self._file_list.clear()
        for p in paths:
            self._file_list.addItem(QListWidgetItem(p))
        if paths:
            self._label_paths.setText(f"선택됨: {len(paths)}개 파일")
            if not self._edit_doc_id.text().strip():
                self._edit_doc_id.setText(self._state.get("doc_id", "") or _doc_id_from_path(paths[0]))
        else:
            self._label_paths.setText("선택된 파일 없음")
            self._state["doc_id"] = ""
            self._edit_doc_id.clear()

    def _on_select_files(self) -> None:
        """파일 선택 다이얼로그."""
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        data_dir = os.path.join(base, "data")
        start_dir = data_dir if os.path.isdir(data_dir) else base
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "PDF 파일 선택",
            start_dir,
            "PDF 파일 (*.pdf);;모든 파일 (*.*)",
        )
        if not paths:
            return
        self._state["pdf_paths"] = list(paths)
        if paths:
            self._state["doc_id"] = _doc_id_from_path(paths[0])
        self._sync_from_state()

    def _on_doc_id_changed(self, text: str) -> None:
        self._state["doc_id"] = text.strip()

    def _on_output_changed(self, text: str) -> None:
        self._state["output_dir"] = text.strip() or "output"

    def _on_browse_output(self) -> None:
        current = self._edit_output.text().strip() or "output"
        dir_path = QFileDialog.getExistingDirectory(self, "출력 디렉터리 선택", current)
        if dir_path:
            self._edit_output.setText(dir_path)
            self._state["output_dir"] = dir_path

    def _on_after_toc_changed(self) -> None:
        self._state["after_toc"] = self._check_after_toc.isChecked()

    def _on_toc_preview(self) -> None:
        paths = self._state.get("pdf_paths", [])
        if not paths:
            self._label_toc_preview.setText("오류: PDF 파일을 먼저 선택하세요.")
            return
        self._btn_toc_preview.setEnabled(False)
        self._label_toc_preview.setText("탐지 중…")
        self._toc_preview_thread = QThread()
        self._toc_preview_worker = TocPreviewWorker(paths[0])
        self._toc_preview_worker.moveToThread(self._toc_preview_thread)
        self._toc_preview_thread.started.connect(self._toc_preview_worker.run)
        self._toc_preview_worker.finished.connect(self._on_toc_preview_finished)
        self._toc_preview_worker.error.connect(self._on_toc_preview_error)
        self._toc_preview_worker.finished.connect(self._toc_preview_thread.quit)
        self._toc_preview_worker.error.connect(self._toc_preview_thread.quit)
        self._toc_preview_thread.start()

    def _on_toc_preview_finished(self, result: object) -> None:
        self._btn_toc_preview.setEnabled(True)
        if result is None:
            self._label_toc_preview.setText("차례 또는 '제 n 장'을 찾지 못했습니다.")
            return
        toc_page, toc_ln, body_page, body_ln = result
        self._state["toc_preview"] = result
        self._label_toc_preview.setText(
            f"차례: {toc_page}페이지 {toc_ln}줄  /  본문 시작: {body_page}페이지 {body_ln}줄"
        )

    def _on_toc_preview_error(self, message: str) -> None:
        self._btn_toc_preview.setEnabled(True)
        self._label_toc_preview.setText(f"오류: {message}")
