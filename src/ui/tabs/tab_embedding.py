"""임베딩 탭 — Chunk JSONL 임베딩, FAISS 저장, 검색 테스트."""

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QPushButton,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QFileDialog,
    QProgressBar,
    QSpinBox,
)
from PySide6.QtCore import QThread, Signal, QObject

from src.core.export_jsonl import load_jsonl
from src.core.faiss_index import (
    build_index_from_chunks,
    load_index,
    search,
    _index_path_from_base,
    _meta_path_from_base,
)
from src.core.embedding_bge import encode_query


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_output_dir(state: dict | None = None) -> str:
    if state and state.get("output_dir"):
        return str(state["output_dir"])
    return str(_project_root() / "output")


class EmbeddingWorker(QObject):
    """백그라운드에서 임베딩 & FAISS 저장 수행."""

    progress = Signal(int, int)  # current, total
    finished = Signal(str, str)  # index_path, meta_path
    error = Signal(str)

    def __init__(
        self,
        chunk_path: str,
        output_dir: str,
        stem: str = "rules",
        parent: QObject | None = None,
    ) -> None:
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

            def on_progress(current: int, total: int) -> None:
                self.progress.emit(current, total)

            idx_path, meta_path = build_index_from_chunks(
                chunks,
                output_dir=self._output_dir,
                stem=self._stem,
                progress_callback=on_progress,
            )
            self.finished.emit(str(idx_path), str(meta_path))
        except Exception as e:
            self.error.emit(str(e))


class TabEmbedding(QWidget):
    """임베딩 탭 — Chunk JSONL 선택, 임베딩 & FAISS 저장, 검색 테스트."""

    def __init__(self, app_state: dict | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = app_state or {}
        self._index = None
        self._meta_list: list = []
        self._index_path: str | None = None
        self._meta_path: str | None = None
        self._worker: EmbeddingWorker | None = None
        self._thread: QThread | None = None

        layout = QVBoxLayout(self)

        # 입력
        group_input = QGroupBox("입력")
        input_layout = QVBoxLayout(group_input)
        row_in = QHBoxLayout()
        row_in.addWidget(QLabel("Chunk JSONL:"))
        self._edit_chunk = QLineEdit()
        self._edit_chunk.setPlaceholderText("Phase 13에서 생성한 *_chunks.jsonl")
        row_in.addWidget(self._edit_chunk)
        self._btn_browse_chunk = QPushButton("찾아보기")
        self._btn_browse_chunk.clicked.connect(self._on_browse_chunk)
        row_in.addWidget(self._btn_browse_chunk)
        input_layout.addLayout(row_in)
        row_out = QHBoxLayout()
        row_out.addWidget(QLabel("출력 디렉터리:"))
        self._edit_output = QLineEdit()
        self._edit_output.setPlaceholderText("기본: output/ 또는 index/")
        row_out.addWidget(self._edit_output)
        self._btn_browse_out = QPushButton("찾아보기")
        self._btn_browse_out.clicked.connect(self._on_browse_output)
        row_out.addWidget(self._btn_browse_out)
        input_layout.addLayout(row_out)
        layout.addWidget(group_input)

        # 실행
        group_run = QGroupBox("실행")
        run_layout = QVBoxLayout(group_run)
        row_btn = QHBoxLayout()
        self._btn_run = QPushButton("임베딩 & FAISS 저장")
        self._btn_run.clicked.connect(self._on_run)
        row_btn.addWidget(self._btn_run)
        row_btn.addStretch()
        run_layout.addLayout(row_btn)
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        run_layout.addWidget(self._progress)
        self._label_status = QLabel("Chunk JSONL을 선택하고 실행하세요.")
        self._label_status.setStyleSheet("color: #666;")
        run_layout.addWidget(self._label_status)
        layout.addWidget(group_run)

        # 테스트
        group_test = QGroupBox("검색 테스트")
        test_layout = QVBoxLayout(group_test)
        row_query = QHBoxLayout()
        row_query.addWidget(QLabel("테스트 쿼리:"))
        self._edit_query = QLineEdit()
        self._edit_query.setPlaceholderText("예: 제10조 검사 주기, 안전장치 요구사항")
        row_query.addWidget(self._edit_query)
        row_query.addWidget(QLabel("top_k:"))
        self._spin_topk = QSpinBox()
        self._spin_topk.setRange(1, 20)
        self._spin_topk.setValue(5)
        row_query.addWidget(self._spin_topk)
        self._btn_search = QPushButton("검색 테스트")
        self._btn_search.clicked.connect(self._on_search)
        row_query.addWidget(self._btn_search)
        test_layout.addLayout(row_query)
        self._edit_results = QPlainTextEdit()
        self._edit_results.setReadOnly(True)
        self._edit_results.setPlaceholderText("검색 결과 (chunk_id, 점수, 텍스트 미리보기)")
        self._edit_results.setMaximumHeight(200)
        test_layout.addWidget(self._edit_results)
        layout.addWidget(group_test)
        layout.addStretch()

    def _on_browse_chunk(self) -> None:
        start = self._edit_chunk.text().strip() or _default_output_dir(self._state)
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Chunk JSONL 선택",
            start,
            "JSONL (*.jsonl);;모든 파일 (*)",
        )
        if path:
            self._edit_chunk.setText(path)
            if not self._edit_output.text().strip():
                self._edit_output.setText(str(Path(path).parent))

    def _on_browse_output(self) -> None:
        start = self._edit_output.text().strip() or _default_output_dir(self._state)
        path = QFileDialog.getExistingDirectory(self, "출력 디렉터리 선택", start)
        if path:
            self._edit_output.setText(path)

    def _on_run(self) -> None:
        chunk_path = self._edit_chunk.text().strip()
        output_dir = self._edit_output.text().strip() or _default_output_dir(self._state)
        if not chunk_path:
            self._label_status.setText("Chunk JSONL 파일을 선택하세요.")
            return

        self._btn_run.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setRange(0, 0)  # indeterminate initially
        self._label_status.setText("임베딩 생성 중...")

        self._worker = EmbeddingWorker(chunk_path, output_dir)
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._thread.start()

    def _on_progress(self, current: int, total: int) -> None:
        self._progress.setRange(0, total)
        self._progress.setValue(current)
        self._label_status.setText(f"임베딩 중... {current}/{total}")

    def _on_finished(self, index_path: str, meta_path: str) -> None:
        self._thread.quit()
        self._thread.wait()
        self._btn_run.setEnabled(True)
        self._progress.setVisible(False)
        self._label_status.setText(f"저장 완료: {index_path}, {meta_path}")
        self._index_path = index_path
        self._meta_path = meta_path
        try:
            self._index, self._meta_list = load_index(index_path, meta_path)
        except Exception:
            pass

    def _on_error(self, msg: str) -> None:
        if self._thread:
            self._thread.quit()
            self._thread.wait()
        self._btn_run.setEnabled(True)
        self._progress.setVisible(False)
        self._label_status.setText(f"오류: {msg}")

    def _on_search(self) -> None:
        query = self._edit_query.text().strip()
        if not query:
            self._edit_results.setPlainText("테스트 쿼리를 입력하세요.")
            return

        # 인덱스 미로드 시 자동 로드 시도
        if self._index is None and self._index_path and self._meta_path:
            try:
                self._index, self._meta_list = load_index(self._index_path, self._meta_path)
            except Exception as e:
                self._edit_results.setPlainText(f"인덱스 로드 실패: {e}\n먼저 '임베딩 & FAISS 저장'을 실행하세요.")
                return
        elif self._index is None:
            output_dir = self._edit_output.text().strip() or _default_output_dir(self._state)
            idx_path = _index_path_from_base(output_dir)
            meta_path = _meta_path_from_base(output_dir)
            if idx_path.exists() and meta_path.exists():
                try:
                    self._index, self._meta_list = load_index(str(idx_path), str(meta_path))
                    self._index_path = str(idx_path)
                    self._meta_path = str(meta_path)
                except Exception as e:
                    self._edit_results.setPlainText(f"인덱스 로드 실패: {e}")
                    return
            else:
                self._edit_results.setPlainText(
                    "인덱스가 없습니다. 먼저 '임베딩 & FAISS 저장'을 실행하세요."
                )
                return

        top_k = self._spin_topk.value()
        try:
            q_emb = encode_query(query)
            results = search(self._index, q_emb, self._meta_list, top_k=top_k)
        except Exception as e:
            self._edit_results.setPlainText(f"검색 오류: {e}")
            return

        lines = []
        for rank, (idx, score, meta) in enumerate(results, 1):
            chunk_id = meta.get("chunk_id", str(idx))
            text_preview = (meta.get("text") or "")[:200]
            lines.append(f"[{rank}] {chunk_id} (점수: {score:.4f})\n{text_preview}...")
        self._edit_results.setPlainText("\n\n".join(lines) if lines else "결과 없음.")
