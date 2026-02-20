"""사용 탭 — RAG 실행 전용. (Phase 4~6에서 상세 구현)"""

import os
import re
import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QSplitter,
    QLabel,
    QPushButton,
    QComboBox,
    QPlainTextEdit,
    QTextEdit,
    QListWidget,
    QListWidgetItem,
    QSpinBox,
    QLineEdit,
    QFileDialog,
    QScrollArea,
    QSizePolicy,
)
from PySide6.QtCore import QThread, Signal, QObject, Qt, QEvent
from PySide6.QtGui import QPixmap

from src.core.embedding_bge import encode_query, preload_model, BGE_MODEL_PATH
from src.core.faiss_index import (
    load_index,
    search,
    _index_path_from_base,
    _meta_path_from_base,
)
from src.llm.ollama_client import OllamaClient
from src.rag.rag_pipeline import RAGPipeline, RAGResult
from src.rag.rag_config import FAISS_TOP_K, DEFAULT_OLLAMA_MODEL

# PDF 뷰어용 (tab_review와 동일한 렌더링)
from src.ui.tabs.tab_review import _render_page_to_pixmap


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_output_dir(state: dict | None = None) -> str:
    if state and state.get("output_dir"):
        return str(state["output_dir"])
    return str(_project_root() / "output")


def _doc_id_from_path(path: str) -> str:
    """파일 경로에서 doc_id 후보. 확장자 제거, 공백→_."""
    name = os.path.splitext(os.path.basename(path))[0]
    return name.replace(" ", "_").replace(".", "_")


def _find_pdf_for_doc_id(pdf_folder: str | Path, doc_id: str) -> Path | None:
    """원본 PDF 폴더에서 doc_id에 해당하는 PDF 파일 경로 반환."""
    folder = Path(pdf_folder)
    if not folder.is_dir() or not doc_id:
        return None
    # 1) doc_id.pdf (doc_id에 _ 포함)
    cand = folder / f"{doc_id}.pdf"
    if cand.is_file():
        return cand
    # 2) doc_id를 공백으로 치환한 파일명
    name_with_spaces = doc_id.replace("_", " ")
    cand2 = folder / f"{name_with_spaces}.pdf"
    if cand2.is_file():
        return cand2
    # 3) 폴더 내 PDF 스캔하여 doc_id 매칭
    for p in folder.glob("*.pdf"):
        if _doc_id_from_path(str(p)) == doc_id:
            return p
    return None


def _extract_cited_sources(answer: str, max_sources: int) -> list[int]:
    """답변에서 인용된 출처 번호 추출 (1-based)."""
    if max_sources <= 0:
        return []
    found: set[int] = set()
    for m in re.finditer(r"\[(\d+)\]", answer):
        n = int(m.group(1))
        if 1 <= n <= max_sources:
            found.add(n)
    return sorted(found)


def _format_search_result(rank: int, idx: int, score: float, meta: dict) -> str:
    """검색 결과 한 건 포맷 (점수, section, article, page, chunk 미리보기)."""
    doc_id = meta.get("doc_id") or ""
    page = meta.get("page", "")
    section = meta.get("section") or ""
    article = meta.get("article") or ""
    chunk_id = meta.get("chunk_id", str(idx))
    text_preview = (meta.get("text") or meta.get("full_text") or "")[:120]
    parts = [f"[{rank}] score={score:.4f}", f"p.{page}"]
    if section:
        parts.append(section)
    if article:
        parts.append(article)
    header = " | ".join(parts)
    return f"{header}\n{text_preview}..."


class BgeDownloadWorker(QObject):
    """bge-m3 다운로드 스크립트 실행."""

    finished = Signal(str)
    error = Signal(str)

    def run(self) -> None:
        try:
            import subprocess
            script = Path(__file__).resolve().parents[3] / "scripts" / "download_bge_m3.py"
            result = subprocess.run(
                [sys.executable, str(script)],
                capture_output=True,
                text=True,
                timeout=600,
                cwd=str(Path(__file__).resolve().parents[3]),
            )
            if result.returncode == 0:
                self.finished.emit("다운로드 완료")
            else:
                self.error.emit(result.stderr or result.stdout or f"exit {result.returncode}")
        except Exception as e:
            self.error.emit(str(e))


class ModelsListWorker(QObject):
    """Ollama 모델 목록 조회."""

    finished = Signal(list)
    error = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

    def run(self) -> None:
        try:
            client = OllamaClient()
            models = client.list_models()
            self.finished.emit(models)
        except Exception as e:
            self.error.emit(str(e))


class ModelLoadWorker(QObject):
    """bge-m3, Ollama 모델 사전 로드."""

    finished = Signal(str)
    error = Signal(str)

    def __init__(self, ollama_model: str = DEFAULT_OLLAMA_MODEL, parent: QObject | None = None) -> None:
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
    """FAISS 검색 수행."""

    finished = Signal(list)
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
    """RAG 전체 파이프라인 수행."""

    finished = Signal(object)
    error = Signal(str)

    def __init__(
        self,
        pipeline: RAGPipeline,
        question: str,
        top_k: int,
        model: str = DEFAULT_OLLAMA_MODEL,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._pipeline = pipeline
        self._question = question
        self._top_k = top_k
        self._model = model

    def run(self) -> None:
        try:
            result = self._pipeline.run_query(
                self._question, top_k=self._top_k, model=self._model
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class TabUsage(QWidget):
    """사용 탭 — 모델 관리, 질문/검색, 검색 결과, 답변, 출처."""

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
        self._models_list_worker: ModelsListWorker | None = None
        self._models_list_thread: QThread | None = None
        self._models_loaded = False
        self._last_search_results: list = []
        self._last_sources_meta: list = []
        self._current_pdf_pixmap: QPixmap | None = None
        self._bge_download_thread: QThread | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # === 단분리: 좌(상단+하단) | 우(출처+PDF) ===
        splitter_main = QSplitter(Qt.Orientation.Horizontal)
        splitter_main.setChildrenCollapsible(False)

        # === 좌측: 상단(모델/FAISS/질문) + 하단(검색/컨텍스트/답변) ===
        left_widget = QWidget()
        left_widget.setMinimumWidth(400)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        group_model = QGroupBox("모델 관리")
        model_layout = QHBoxLayout(group_model)
        model_layout.addWidget(QLabel("bge-m3:"))
        self._label_bge_status = QLabel("확인 중…")
        self._label_bge_status.setStyleSheet("color: #666;")
        model_layout.addWidget(self._label_bge_status)
        self._btn_download_bge = QPushButton("다운로드")
        self._btn_download_bge.clicked.connect(self._on_download_bge)
        self._btn_download_bge.setVisible(False)
        model_layout.addWidget(self._btn_download_bge)
        model_layout.addWidget(QLabel("Ollama:"))
        self._combo_model = QComboBox()
        self._combo_model.setEditable(True)
        self._combo_model.setMinimumWidth(200)
        self._combo_model.lineEdit().setPlaceholderText(DEFAULT_OLLAMA_MODEL)
        model_layout.addWidget(self._combo_model)
        self._btn_refresh_models = QPushButton("목록 새로고침")
        self._btn_refresh_models.clicked.connect(self._on_refresh_models)
        self._btn_refresh_models.setToolTip("Ollama에 설치된 모델 목록을 조회합니다.")
        model_layout.addWidget(self._btn_refresh_models)
        self._btn_load_models = QPushButton("모델 사전 로드")
        self._btn_load_models.clicked.connect(self._on_load_models)
        self._btn_load_models.setToolTip("bge-m3(임베딩)과 Ollama LLM을 미리 로드합니다.")
        model_layout.addWidget(self._btn_load_models)
        self._label_model_status = QLabel("미로드 (첫 질문 시 로드됨)")
        self._label_model_status.setStyleSheet("color: #666;")
        model_layout.addWidget(self._label_model_status)
        model_layout.addStretch()
        left_layout.addWidget(group_model)

        # 인덱스 경로 + 원본 PDF 폴더
        group_index = QGroupBox("FAISS 인덱스")
        idx_layout = QVBoxLayout(group_index)
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("인덱스 디렉터리:"))
        self._edit_index_dir = QLineEdit()
        self._edit_index_dir.setPlaceholderText("output/ 또는 rules.index가 있는 폴더")
        default_out = _default_output_dir(self._state)
        if Path(default_out).exists():
            self._edit_index_dir.setText(default_out)
        row1.addWidget(self._edit_index_dir)
        self._btn_browse_index = QPushButton("찾아보기")
        self._btn_browse_index.clicked.connect(self._on_browse_index)
        row1.addWidget(self._btn_browse_index)
        idx_layout.addLayout(row1)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("원본 PDF 폴더:"))
        self._edit_pdf_dir = QLineEdit()
        self._edit_pdf_dir.setPlaceholderText("doc_id에 해당하는 PDF가 있는 폴더 (예: data/)")
        default_data = str(_project_root() / "data")
        if Path(default_data).exists():
            self._edit_pdf_dir.setText(default_data)
        row2.addWidget(self._edit_pdf_dir)
        self._btn_browse_pdf = QPushButton("찾아보기")
        self._btn_browse_pdf.clicked.connect(self._on_browse_pdf)
        row2.addWidget(self._btn_browse_pdf)
        idx_layout.addLayout(row2)
        left_layout.addWidget(group_index)

        # 질문 & 검색 영역
        group_query = QGroupBox("질문 & 검색")
        query_layout = QVBoxLayout(group_query)
        self._edit_question = QPlainTextEdit()
        self._edit_question.setPlaceholderText("규격문서에 대해 질문하세요. 예: 제10조 검사 주기는?")
        self._edit_question.setFixedHeight(70)
        query_layout.addWidget(self._edit_question)
        row_btn = QHBoxLayout()
        row_btn.addWidget(QLabel("Top-k:"))
        self._spin_topk = QSpinBox()
        self._spin_topk.setRange(1, 30)
        self._spin_topk.setValue(FAISS_TOP_K)
        row_btn.addWidget(self._spin_topk)
        self._btn_search = QPushButton("검색")
        self._btn_search.clicked.connect(self._on_search)
        self._btn_search.setEnabled(False)
        row_btn.addWidget(self._btn_search)
        self._btn_answer = QPushButton("답변 생성")
        self._btn_answer.clicked.connect(self._on_answer)
        self._btn_answer.setEnabled(False)
        row_btn.addWidget(self._btn_answer)
        row_btn.addStretch()
        self._label_status = QLabel("질문을 입력하고 검색 또는 답변 생성을 실행하세요.")
        self._label_status.setStyleSheet("color: #666;")
        row_btn.addWidget(self._label_status)
        query_layout.addLayout(row_btn)
        left_layout.addWidget(group_query)

        # 검색 결과 + 조합 컨텍스트 + 답변
        group_results = QGroupBox("검색 결과")
        results_layout = QVBoxLayout(group_results)
        self._list_results = QListWidget()
        self._list_results.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._list_results.setMinimumHeight(60)
        self._list_results.itemSelectionChanged.connect(self._on_result_selected)
        results_layout.addWidget(self._list_results)
        results_layout.addWidget(QLabel("선택 항목 상세:"))
        self._edit_result_detail = QPlainTextEdit()
        self._edit_result_detail.setReadOnly(True)
        self._edit_result_detail.setMaximumHeight(90)
        self._edit_result_detail.setPlaceholderText("항목 선택 시 전체 텍스트 표시")
        results_layout.addWidget(self._edit_result_detail)
        left_layout.addWidget(group_results)

        group_context = QGroupBox("조합 컨텍스트 (LLM 전달 내용)")
        ctx_layout = QVBoxLayout(group_context)
        self._label_context_info = QLabel("문자 수: - | 그룹: -")
        self._label_context_info.setStyleSheet("color: #666; font-size: 11px;")
        ctx_layout.addWidget(self._label_context_info)
        scroll_ctx = QScrollArea()
        scroll_ctx.setWidgetResizable(True)
        scroll_ctx.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_ctx.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._edit_context = QPlainTextEdit()
        self._edit_context.setReadOnly(True)
        self._edit_context.setPlaceholderText("답변 생성 후 LLM에 전달된 컨텍스트")
        scroll_ctx.setWidget(self._edit_context)
        ctx_layout.addWidget(scroll_ctx)
        left_layout.addWidget(group_context)

        group_answer = QGroupBox("답변")
        answer_layout = QVBoxLayout(group_answer)
        scroll_answer = QScrollArea()
        scroll_answer.setWidgetResizable(True)
        scroll_answer.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_answer.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._edit_answer = QTextEdit()
        self._edit_answer.setReadOnly(True)
        self._edit_answer.setPlaceholderText("답변 생성 결과")
        scroll_answer.setWidget(self._edit_answer)
        answer_layout.addWidget(scroll_answer)
        left_layout.addWidget(group_answer)

        splitter_main.addWidget(left_widget)

        # === 우: 출처 + PDF 뷰어 (우측 전체) ===
        right_widget = QWidget()
        right_widget.setMinimumWidth(450)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        group_sources = QGroupBox("출처 (선택 시 PDF 뷰어에 페이지 표시)")
        sources_layout = QHBoxLayout(group_sources)
        sources_layout.addWidget(QLabel("출처:"))
        self._combo_sources = QComboBox()
        self._combo_sources.setMinimumWidth(300)
        self._combo_sources.currentIndexChanged.connect(self._on_source_selected)
        sources_layout.addWidget(self._combo_sources)
        sources_layout.addStretch()
        right_layout.addWidget(group_sources)

        group_pdf = QGroupBox("PDF 뷰어 (너비 맞춤, 세로 스크롤)")
        pdf_layout = QVBoxLayout(group_pdf)
        self._label_pdf_info = QLabel("출처를 선택하면 해당 페이지가 표시됩니다.")
        self._label_pdf_info.setStyleSheet("color: #666; font-size: 11px;")
        pdf_layout.addWidget(self._label_pdf_info)
        self._scroll_pdf = QScrollArea()
        self._scroll_pdf.setWidgetResizable(False)
        self._scroll_pdf.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._scroll_pdf.setMinimumHeight(400)
        self._label_pdf_page = QLabel()
        self._label_pdf_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label_pdf_page.setStyleSheet("QLabel { background-color: #2b2b2b; color: #888; }")
        self._label_pdf_page.setText("출처에서 항목 선택")
        self._scroll_pdf.setWidget(self._label_pdf_page)
        self._scroll_pdf.viewport().installEventFilter(self)
        pdf_layout.addWidget(self._scroll_pdf)
        right_layout.addWidget(group_pdf)

        splitter_main.addWidget(right_widget)

        # 비율: 좌 1 : 우 1 (우측 출처+PDF가 전체)
        splitter_main.setStretchFactor(0, 10)
        splitter_main.setStretchFactor(1, 12)
        splitter_main.setSizes([600, 700])  # 초기 비율 고정
        layout.addWidget(splitter_main, stretch=1)

        # 초기: Ollama 모델 목록, bge-m3 확인
        self._on_refresh_models()
        self._on_check_bge()

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """뷰포트 리사이즈 시 PDF 스케일 갱신."""
        if obj is self._scroll_pdf.viewport() and event.type() == QEvent.Type.Resize:
            self._display_pdf_fit_width()
        return super().eventFilter(obj, event)

    def _on_check_bge(self) -> None:
        """bge-m3 모델 존재 여부 확인."""
        exists = Path(BGE_MODEL_PATH).exists()
        if exists:
            self._label_bge_status.setText("있음")
            self._label_bge_status.setStyleSheet("color: #060;")
            self._btn_download_bge.setVisible(False)
        else:
            self._label_bge_status.setText("없음")
            self._label_bge_status.setStyleSheet("color: #c00;")
            self._btn_download_bge.setVisible(True)

    def _on_download_bge(self) -> None:
        """bge-m3 다운로드 스크립트 실행 (백그라운드)."""
        self._btn_download_bge.setEnabled(False)
        self._label_bge_status.setText("다운로드 중…")
        worker = BgeDownloadWorker()
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_bge_download_finished)
        worker.error.connect(self._on_bge_download_error)
        self._bge_download_thread = thread
        thread.start()

    def _on_bge_download_finished(self, msg: str) -> None:
        if self._bge_download_thread:
            self._bge_download_thread.quit()
            self._bge_download_thread.wait()
        self._btn_download_bge.setEnabled(True)
        self._label_bge_status.setText("다운로드 완료")
        self._label_bge_status.setStyleSheet("color: #060;")
        self._btn_download_bge.setVisible(False)

    def _on_bge_download_error(self, msg: str) -> None:
        if self._bge_download_thread:
            self._bge_download_thread.quit()
            self._bge_download_thread.wait()
        self._btn_download_bge.setEnabled(True)
        self._label_bge_status.setText(f"실패: {msg[:30]}…")
        self._label_bge_status.setStyleSheet("color: #c00;")

    def _on_refresh_models(self) -> None:
        """Ollama 모델 목록 조회 (백그라운드)."""
        self._btn_refresh_models.setEnabled(False)
        self._models_list_worker = ModelsListWorker()
        self._models_list_thread = QThread()
        self._models_list_worker.moveToThread(self._models_list_thread)
        self._models_list_thread.started.connect(self._models_list_worker.run)
        self._models_list_worker.finished.connect(self._on_models_list_finished)
        self._models_list_worker.error.connect(self._on_models_list_error)
        self._models_list_thread.start()

    def _on_models_list_finished(self, models: list[str]) -> None:
        self._models_list_thread.quit()
        self._models_list_thread.wait()
        self._btn_refresh_models.setEnabled(True)
        current = self._combo_model.currentText().strip()
        self._combo_model.clear()
        if models:
            self._combo_model.addItems(models)
            if current and current in models:
                self._combo_model.setCurrentText(current)
            elif models:
                self._combo_model.setCurrentIndex(0)
        if not self._combo_model.currentText():
            self._combo_model.setCurrentText(DEFAULT_OLLAMA_MODEL)

    def _on_models_list_error(self, msg: str) -> None:
        if self._models_list_thread:
            self._models_list_thread.quit()
            self._models_list_thread.wait()
        self._btn_refresh_models.setEnabled(True)
        self._label_model_status.setText(f"모델 목록 조회 실패: {msg[:40]}…")
        self._label_model_status.setStyleSheet("color: #c00;")

    def _on_load_models(self) -> None:
        """bge-m3, Ollama 모델 사전 로드 (백그라운드)."""
        self._btn_load_models.setEnabled(False)
        self._label_model_status.setText("로드 중… (bge-m3, Ollama)")
        self._label_model_status.setStyleSheet("color: #f60;")
        model = self._combo_model.currentText().strip() or DEFAULT_OLLAMA_MODEL
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
        self._btn_search.setEnabled(True)
        self._btn_answer.setEnabled(True)

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

    def _on_browse_pdf(self) -> None:
        start = self._edit_pdf_dir.text().strip() or str(_project_root() / "data")
        path = QFileDialog.getExistingDirectory(self, "원본 PDF 폴더 선택", start)
        if path:
            self._edit_pdf_dir.setText(path)

    def _ensure_index_loaded(self) -> bool:
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
        self._label_status.setText("인덱스가 없습니다. DB 생성 탭에서 먼저 FAISS를 생성하세요.")
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
        self._search_worker = SearchWorker(self._index, self._meta_list, question, top_k)
        self._search_thread = QThread()
        self._search_worker.moveToThread(self._search_thread)
        self._search_thread.started.connect(self._search_worker.run)
        self._search_worker.finished.connect(self._on_search_finished)
        self._search_worker.error.connect(self._on_search_error)
        self._search_thread.start()

    def _on_search_finished(self, results: list) -> None:
        self._search_thread.quit()
        self._search_thread.wait()
        self._btn_search.setEnabled(self._models_loaded)
        self._btn_answer.setEnabled(self._models_loaded)
        self._label_status.setText(f"검색 완료: {len(results)}건")
        self._last_search_results = results
        self._last_sources_meta = []
        self._list_results.clear()
        self._combo_sources.blockSignals(True)
        self._combo_sources.clear()
        self._combo_sources.blockSignals(False)
        self._edit_result_detail.clear()
        self._edit_context.clear()
        self._label_context_info.setText("문자 수: - | 그룹: -")
        self._current_pdf_pixmap = None
        self._label_pdf_page.clear()
        self._label_pdf_page.setFixedSize(400, 500)
        self._label_pdf_page.setText("출처에서 항목 선택")
        for rank, (idx, score, meta) in enumerate(results, 1):
            text = _format_search_result(rank, idx, score, meta)
            self._list_results.addItem(QListWidgetItem(text))

    def _on_result_selected(self) -> None:
        """검색 결과 선택 시 상세(전체 텍스트) 표시."""
        row = self._list_results.currentRow()
        if row < 0 or row >= len(self._last_search_results):
            self._edit_result_detail.clear()
            return
        _, score, meta = self._last_search_results[row]
        full_text = meta.get("full_text") or meta.get("text") or "(텍스트 없음)"
        self._edit_result_detail.setPlainText(full_text)

    def _on_source_selected(self, index: int = -1) -> None:
        """출처 선택 시 PDF 뷰어에 해당 페이지 표시 (할당 공간에 fit)."""
        if index < 0:
            index = self._combo_sources.currentIndex()
        if index < 0 or index >= len(self._last_sources_meta):
            self._current_pdf_pixmap = None
            self._label_pdf_page.clear()
            self._label_pdf_page.setFixedSize(400, 500)
            self._label_pdf_page.setText("출처에서 항목 선택")
            self._label_pdf_info.setText("출처를 선택하면 해당 페이지가 표시됩니다.")
            return
        meta = self._last_sources_meta[index]
        doc_id = meta.get("doc_id") or ""
        page = meta.get("page")
        if page is None:
            chunk_meta = meta.get("meta") or {}
            pages = chunk_meta.get("pages") or []
            page = pages[0] if pages else 1
        try:
            page_no = int(page) if page is not None else 1
        except (TypeError, ValueError):
            page_no = 1

        pdf_dir = self._edit_pdf_dir.text().strip() or str(_project_root() / "data")
        pdf_path = _find_pdf_for_doc_id(pdf_dir, doc_id)
        if not pdf_path:
            self._current_pdf_pixmap = None
            self._label_pdf_page.clear()
            self._label_pdf_page.setText(f"PDF를 찾을 수 없음\n(doc_id={doc_id})\n원본 PDF 폴더를 확인하세요.")
            self._label_pdf_info.setText(f"doc_id={doc_id}, page={page} — PDF 미발견")
            return
        pix = _render_page_to_pixmap(str(pdf_path), page_no, dpi_scale=2.0)
        if pix:
            self._current_pdf_pixmap = pix
            self._label_pdf_info.setText(f"doc_id={doc_id} | p.{page_no} | {pdf_path.name}")
            self._display_pdf_fit_width()
        else:
            self._current_pdf_pixmap = None
            self._label_pdf_page.setText(f"페이지 렌더링 실패 (p.{page_no})")
            self._label_pdf_info.setText(f"doc_id={doc_id}, page={page_no}")

    def _display_pdf_fit_width(self) -> None:
        """PDF를 뷰포트 너비에 맞춰 표시. 상단 좌우 전체 보이고 아래는 스크롤로 확인."""
        if not self._current_pdf_pixmap:
            return
        vp = self._scroll_pdf.viewport()
        vp_w = max(100, vp.width() - 4)
        vp_h = max(100, vp.height() - 4)
        w = self._current_pdf_pixmap.width()
        h = self._current_pdf_pixmap.height()
        scale = vp_w / w
        new_w = int(w * scale)
        new_h = int(h * scale)
        scaled = self._current_pdf_pixmap.scaled(
            new_w, new_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._label_pdf_page.setPixmap(scaled)
        self._label_pdf_page.setFixedSize(new_w, new_h)

    def _on_search_error(self, msg: str) -> None:
        if self._search_thread:
            self._search_thread.quit()
            self._search_thread.wait()
        self._btn_search.setEnabled(self._models_loaded)
        self._btn_answer.setEnabled(self._models_loaded)
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
        self._combo_sources.blockSignals(True)
        self._combo_sources.clear()
        self._combo_sources.blockSignals(False)
        self._last_sources_meta = []
        self._edit_context.clear()
        self._label_context_info.setText("문자 수: - | 그룹: -")
        pipeline = RAGPipeline(self._index, self._meta_list)
        top_k = self._spin_topk.value()
        model = self._combo_model.currentText().strip() or DEFAULT_OLLAMA_MODEL
        self._rag_worker = RAGWorker(pipeline, question, top_k, model=model)
        self._rag_thread = QThread()
        self._rag_worker.moveToThread(self._rag_thread)
        self._rag_thread.started.connect(self._rag_worker.run)
        self._rag_worker.finished.connect(self._on_rag_finished)
        self._rag_worker.error.connect(self._on_rag_error)
        self._rag_thread.start()

    def _on_rag_finished(self, result: RAGResult) -> None:
        self._rag_thread.quit()
        self._rag_thread.wait()
        self._btn_search.setEnabled(self._models_loaded)
        self._btn_answer.setEnabled(self._models_loaded)
        self._label_status.setText("답변 생성 완료")

        # 검색 결과 리스트 (retrieved_chunks → last_search_results)
        self._last_search_results = result.retrieved_chunks
        self._list_results.clear()
        for rank, (idx, score, meta) in enumerate(result.retrieved_chunks, 1):
            text = _format_search_result(rank, idx, score, meta)
            self._list_results.addItem(QListWidgetItem(text))

        # 조합 컨텍스트 영역 (길이, 그룹, assembled_context)
        ctx = result.assembled_context or ""
        self._edit_context.setPlainText(ctx)
        groups = result.debug_info.get("selected_groups", [])
        total_chunks = result.debug_info.get("total_chunks_selected", 0)
        groups_str = ", ".join(groups) if groups else "-"
        self._label_context_info.setText(
            f"문자 수: {len(ctx):,} | 선택 chunks: {total_chunks} | 그룹: {groups_str}"
        )

        # 답변 영역
        self._edit_answer.setPlainText(result.answer)

        # 출처 드롭다운 — 답변에 인용된 출처만 표시
        all_sources = result.sources or []
        all_meta = getattr(result, "sources_meta", [])
        cited = _extract_cited_sources(result.answer, len(all_sources))
        if cited:
            filtered_sources = [all_sources[i - 1] for i in cited]
            filtered_meta = [all_meta[i - 1] for i in cited]
        else:
            filtered_sources = all_sources
            filtered_meta = all_meta
        self._last_sources_meta = filtered_meta
        self._combo_sources.blockSignals(True)
        self._combo_sources.clear()
        for s in filtered_sources:
            self._combo_sources.addItem(s)
        self._combo_sources.blockSignals(False)
        if self._combo_sources.count() > 0:
            self._combo_sources.setCurrentIndex(0)
            self._on_source_selected(0)

    def _on_rag_error(self, msg: str) -> None:
        if self._rag_thread:
            self._rag_thread.quit()
            self._rag_thread.wait()
        self._btn_search.setEnabled(self._models_loaded)
        self._btn_answer.setEnabled(self._models_loaded)
        self._label_status.setText(f"오류: {msg}")
