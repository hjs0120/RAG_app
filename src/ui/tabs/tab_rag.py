"""RAG 탭 — 질문/검색/답변, Top-k 디버깅, 비동기 처리."""

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
    QTextEdit,
    QFileDialog,
    QListWidget,
    QListWidgetItem,
    QSpinBox,
    QSplitter,
)
from PySide6.QtCore import QThread, Signal, QObject
from PySide6.QtCore import Qt

from src.core.embedding_bge import encode_query, preload_model
from src.core.faiss_index import (
    load_index,
    search,
    _index_path_from_base,
    _meta_path_from_base,
)
from src.llm.ollama_client import OllamaClient
from src.rag.rag_pipeline import RAGPipeline, RAGResult
from src.rag.rag_config import FAISS_TOP_K, DEFAULT_OLLAMA_MODEL


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_output_dir(state: dict | None = None) -> str:
    if state and state.get("output_dir"):
        return str(state["output_dir"])
    return str(_project_root() / "output")


def _format_search_result(rank: int, idx: int, score: float, meta: dict) -> str:
    """검색 결과 한 건 포맷."""
    doc_id = meta.get("doc_id") or ""
    page = meta.get("page", "")
    section = meta.get("section") or ""
    chunk_id = meta.get("chunk_id", str(idx))
    text_preview = (meta.get("text") or meta.get("full_text") or "")[:150]
    return f"[{rank}] score={score:.4f} | {doc_id} p.{page} {section} | {chunk_id}\n{text_preview}..."


class ModelLoadWorker(QObject):
    """bge-m3, Ollama 모델 사전 로드."""

    finished = Signal(str)  # 성공 시 "완료"
    error = Signal(str)

    def __init__(self, ollama_model: str = DEFAULT_OLLAMA_MODEL, parent=None):
        super().__init__(parent)
        self._ollama_model = ollama_model

    def run(self) -> None:
        try:
            preload_model()
            client = OllamaClient()
            client.load_model(self._ollama_model)
            self.finished.emit("완료")
        except Exception as e:
            self.error.emit(str(e))


class SearchWorker(QObject):
    """FAISS 검색만 수행 (Top-k 디버깅용)."""

    finished = Signal(list)  # list of (idx, score, meta)
    error = Signal(str)

    def __init__(
        self,
        index,
        meta_list: list,
        query: str,
        top_k: int,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._index = index
        self._meta_list = meta_list
        self._query = query
        self._top_k = top_k

    def run(self) -> None:
        try:
            q_emb = encode_query(self._query)
            results = search(self._index, q_emb, self._meta_list, top_k=self._top_k)
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class RAGWorker(QObject):
    """RAG 전체 파이프라인 수행 (검색 → 재조합 → Ollama 답변)."""

    finished = Signal(object)  # RAGResult
    error = Signal(str)

    def __init__(
        self,
        pipeline: RAGPipeline,
        question: str,
        top_k: int,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._pipeline = pipeline
        self._question = question
        self._top_k = top_k

    def run(self) -> None:
        try:
            result = self._pipeline.run_query(
                self._question,
                top_k=self._top_k,
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class TabRAG(QWidget):
    """RAG 탭 — 질문 입력, 검색, 답변 생성, Top-k 디버깅."""

    def __init__(self, app_state: dict | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = app_state or {}
        self._index = None
        self._meta_list: list = []
        self._index_path: str | None = None
        self._meta_path: str | None = None
        self._search_worker: SearchWorker | None = None
        self._search_thread: QThread | None = None
        self._rag_worker: RAGWorker | None = None
        self._rag_thread: QThread | None = None
        self._model_load_worker: ModelLoadWorker | None = None
        self._model_load_thread: QThread | None = None
        self._models_loaded = False

        layout = QVBoxLayout(self)

        # 모델 사전 로드
        group_model = QGroupBox("모델")
        model_layout = QHBoxLayout(group_model)
        self._btn_load_models = QPushButton("모델 사전 로드")
        self._btn_load_models.clicked.connect(self._on_load_models)
        self._btn_load_models.setToolTip("bge-m3(임베딩)과 Ollama LLM을 미리 로드하여 첫 질문 지연을 줄입니다.")
        model_layout.addWidget(self._btn_load_models)
        model_layout.addWidget(QLabel("Ollama 모델:"))
        self._edit_ollama_model = QLineEdit()
        self._edit_ollama_model.setText(DEFAULT_OLLAMA_MODEL)
        self._edit_ollama_model.setPlaceholderText("예: qwen2.5:7b-instruct")
        model_layout.addWidget(self._edit_ollama_model)
        self._label_model_status = QLabel("미로드 (첫 질문 시 로드됨)")
        self._label_model_status.setStyleSheet("color: #666;")
        model_layout.addWidget(self._label_model_status)
        model_layout.addStretch()
        layout.addWidget(group_model)

        # 인덱스 경로
        group_index = QGroupBox("FAISS 인덱스")
        idx_layout = QHBoxLayout(group_index)
        idx_layout.addWidget(QLabel("인덱스 디렉터리:"))
        self._edit_index_dir = QLineEdit()
        self._edit_index_dir.setPlaceholderText("output/ 또는 rules.index가 있는 폴더")
        idx_layout.addWidget(self._edit_index_dir)
        self._btn_browse_index = QPushButton("찾아보기")
        self._btn_browse_index.clicked.connect(self._on_browse_index)
        idx_layout.addWidget(self._btn_browse_index)
        layout.addWidget(group_index)

        # 질문 & 버튼
        group_query = QGroupBox("질문")
        query_layout = QVBoxLayout(group_query)
        self._edit_question = QPlainTextEdit()
        self._edit_question.setPlaceholderText("규격문서에 대해 질문하세요. 예: 제10조 검사 주기는?")
        self._edit_question.setMaximumHeight(80)
        query_layout.addWidget(self._edit_question)
        row_btn = QHBoxLayout()
        row_btn.addWidget(QLabel("top_k:"))
        self._spin_topk = QSpinBox()
        self._spin_topk.setRange(1, 30)
        self._spin_topk.setValue(FAISS_TOP_K)
        row_btn.addWidget(self._spin_topk)
        self._btn_search = QPushButton("검색")
        self._btn_search.clicked.connect(self._on_search)
        row_btn.addWidget(self._btn_search)
        self._btn_answer = QPushButton("답변 생성")
        self._btn_answer.clicked.connect(self._on_answer)
        row_btn.addWidget(self._btn_answer)
        row_btn.addStretch()
        self._label_status = QLabel("질문을 입력하고 검색 또는 답변 생성을 실행하세요.")
        self._label_status.setStyleSheet("color: #666;")
        row_btn.addWidget(self._label_status)
        query_layout.addLayout(row_btn)
        layout.addWidget(group_query)

        # 검색 결과 / 답변 분할
        splitter = QSplitter(Qt.Orientation.Vertical)

        # 검색 결과 (Top-k)
        group_results = QGroupBox("검색 결과 (Top-k)")
        results_layout = QVBoxLayout(group_results)
        self._list_results = QListWidget()
        self._list_results.setMinimumHeight(120)
        results_layout.addWidget(self._list_results)
        splitter.addWidget(group_results)

        # 답변
        group_answer = QGroupBox("답변")
        answer_layout = QVBoxLayout(group_answer)
        self._edit_answer = QTextEdit()
        self._edit_answer.setReadOnly(True)
        self._edit_answer.setPlaceholderText("답변 생성 결과가 여기에 표시됩니다.")
        answer_layout.addWidget(self._edit_answer)
        splitter.addWidget(group_answer)

        # 출처
        group_sources = QGroupBox("출처")
        sources_layout = QVBoxLayout(group_sources)
        self._edit_sources = QPlainTextEdit()
        self._edit_sources.setReadOnly(True)
        self._edit_sources.setMaximumHeight(80)
        sources_layout.addWidget(self._edit_sources)
        splitter.addWidget(group_sources)

        splitter.setStretchFactor(0, 1)  # 검색 결과
        splitter.setStretchFactor(1, 2)  # 답변
        splitter.setStretchFactor(2, 0)  # 출처 (고정 높이)
        layout.addWidget(splitter)

    def _on_load_models(self) -> None:
        """bge-m3, Ollama 모델 사전 로드 (백그라운드)."""
        self._btn_load_models.setEnabled(False)
        self._label_model_status.setText("로드 중… (bge-m3, Ollama)")
        self._label_model_status.setStyleSheet("color: #f60;")

        model = self._edit_ollama_model.text().strip() or DEFAULT_OLLAMA_MODEL
        self._model_load_worker = ModelLoadWorker(model)
        self._model_load_thread = QThread()
        self._model_load_worker.moveToThread(self._model_load_thread)
        self._model_load_thread.started.connect(self._model_load_worker.run)
        self._model_load_worker.finished.connect(self._on_model_load_finished)
        self._model_load_worker.error.connect(self._on_model_load_error)
        self._model_load_thread.start()

    def _on_model_load_finished(self, _msg: str) -> None:
        self._model_load_thread.quit()
        self._model_load_thread.wait()
        self._btn_load_models.setEnabled(True)
        self._models_loaded = True
        self._label_model_status.setText("로드 완료 (bge-m3, Ollama)")
        self._label_model_status.setStyleSheet("color: #060;")

    def _on_model_load_error(self, msg: str) -> None:
        if self._model_load_thread:
            self._model_load_thread.quit()
            self._model_load_thread.wait()
        self._btn_load_models.setEnabled(True)
        self._label_model_status.setText(f"로드 실패: {msg[:50]}…")
        self._label_model_status.setStyleSheet("color: #c00;")

    def _on_browse_index(self) -> None:
        start = self._edit_index_dir.text().strip() or _default_output_dir(self._state)
        path = QFileDialog.getExistingDirectory(self, "인덱스 디렉터리 선택", start)
        if path:
            self._edit_index_dir.setText(path)

    def _ensure_index_loaded(self) -> bool:
        """인덱스 로드. 없으면 output/rules.index 시도."""
        if self._index is not None:
            return True

        index_dir = self._edit_index_dir.text().strip() or _default_output_dir(self._state)
        idx_path = _index_path_from_base(index_dir)
        meta_path = _meta_path_from_base(index_dir)

        if idx_path.exists() and meta_path.exists():
            try:
                self._index, self._meta_list = load_index(str(idx_path), str(meta_path))
                self._index_path = str(idx_path)
                self._meta_path = str(meta_path)
                return True
            except Exception as e:
                self._label_status.setText(f"인덱스 로드 실패: {e}")
                return False

        self._label_status.setText("인덱스가 없습니다. 임베딩 탭에서 먼저 FAISS를 생성하세요.")
        return False

    def _on_search(self) -> None:
        question = self._edit_question.toPlainText().strip()
        if not question:
            self._label_status.setText("질문을 입력하세요.")
            return

        if not self._ensure_index_loaded():
            return

        self._btn_search.setEnabled(False)
        self._btn_answer.setEnabled(False)
        self._label_status.setText("검색중…")

        top_k = self._spin_topk.value()
        self._search_worker = SearchWorker(
            self._index, self._meta_list, question, top_k
        )
        self._search_thread = QThread()
        self._search_worker.moveToThread(self._search_thread)
        self._search_thread.started.connect(self._search_worker.run)
        self._search_worker.finished.connect(self._on_search_finished)
        self._search_worker.error.connect(self._on_search_error)
        self._search_thread.start()

    def _on_search_finished(self, results: list) -> None:
        self._search_thread.quit()
        self._search_thread.wait()
        self._btn_search.setEnabled(True)
        self._btn_answer.setEnabled(True)
        self._label_status.setText(f"검색 완료: {len(results)}건")

        self._list_results.clear()
        for rank, (idx, score, meta) in enumerate(results, 1):
            text = _format_search_result(rank, idx, score, meta)
            item = QListWidgetItem(text)
            self._list_results.addItem(item)

    def _on_search_error(self, msg: str) -> None:
        if self._search_thread:
            self._search_thread.quit()
            self._search_thread.wait()
        self._btn_search.setEnabled(True)
        self._btn_answer.setEnabled(True)
        self._label_status.setText(f"검색 오류: {msg}")

    def _on_answer(self) -> None:
        question = self._edit_question.toPlainText().strip()
        if not question:
            self._label_status.setText("질문을 입력하세요.")
            return

        if not self._ensure_index_loaded():
            return

        self._btn_search.setEnabled(False)
        self._btn_answer.setEnabled(False)
        self._label_status.setText("답변 생성중…")
        self._edit_answer.clear()
        self._edit_sources.clear()

        pipeline = RAGPipeline(self._index, self._meta_list)
        top_k = self._spin_topk.value()
        self._rag_worker = RAGWorker(pipeline, question, top_k)
        self._rag_thread = QThread()
        self._rag_worker.moveToThread(self._rag_thread)
        self._rag_thread.started.connect(self._rag_worker.run)
        self._rag_worker.finished.connect(self._on_rag_finished)
        self._rag_worker.error.connect(self._on_rag_error)
        self._rag_thread.start()

    def _on_rag_finished(self, result: RAGResult) -> None:
        self._rag_thread.quit()
        self._rag_thread.wait()
        self._btn_search.setEnabled(True)
        self._btn_answer.setEnabled(True)
        self._label_status.setText("답변 생성 완료")

        self._edit_answer.setPlainText(result.answer)
        self._edit_sources.setPlainText("\n".join(result.sources))

        # 검색 결과도 갱신
        self._list_results.clear()
        for rank, (idx, score, meta) in enumerate(result.retrieved_chunks, 1):
            text = _format_search_result(rank, idx, score, meta)
            self._list_results.addItem(QListWidgetItem(text))

    def _on_rag_error(self, msg: str) -> None:
        if self._rag_thread:
            self._rag_thread.quit()
            self._rag_thread.wait()
        self._btn_search.setEnabled(True)
        self._btn_answer.setEnabled(True)
        self._label_status.setText(f"오류: {msg}")
