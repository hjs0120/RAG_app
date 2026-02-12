"""Chunk 생성 탭 — 원본 JSONL → RAG용 Chunk JSONL 생성."""

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QPushButton,
    QLabel,
    QLineEdit,
    QSpinBox,
    QCheckBox,
    QPlainTextEdit,
    QFileDialog,
)
from PySide6.QtCore import Qt

from src.core.export_jsonl import load_jsonl
from src.core.chunk_builder import (
    build_chunks,
    write_chunk_jsonl,
    TARGET_LEN,
    MAX_LEN,
)
from src.core.chunk_validate import validate_chunks, validate_chunk_text_coverage


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_output_dir(state: dict) -> str:
    return str(state.get("output_dir") or _project_root() / "output")


class TabChunk(QWidget):
    """Chunk 생성 탭 — JSONL 입력 → Merge/Split → Chunk JSONL 저장 및 검증."""

    def __init__(self, app_state: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = app_state
        layout = QVBoxLayout(self)

        # 입력
        group_input = QGroupBox("입력")
        input_layout = QVBoxLayout(group_input)
        row_in = QHBoxLayout()
        row_in.addWidget(QLabel("원본 JSONL:"))
        self._edit_input = QLineEdit()
        self._edit_input.setPlaceholderText("JSONL 파일 경로 (Export 탭에서 저장한 파일)")
        row_in.addWidget(self._edit_input)
        self._btn_browse_in = QPushButton("찾아보기")
        self._btn_browse_in.clicked.connect(self._on_browse_input)
        row_in.addWidget(self._btn_browse_in)
        input_layout.addLayout(row_in)
        layout.addWidget(group_input)

        # 옵션
        group_opts = QGroupBox("Chunk 옵션")
        opts_layout = QHBoxLayout(group_opts)
        opts_layout.addWidget(QLabel("목표 길이:"))
        self._spin_target = QSpinBox()
        self._spin_target.setRange(100, 2000)
        self._spin_target.setValue(TARGET_LEN)
        self._spin_target.setSuffix(" 자")
        opts_layout.addWidget(self._spin_target)
        opts_layout.addWidget(QLabel("최대 길이:"))
        self._spin_max = QSpinBox()
        self._spin_max.setRange(200, 3000)
        self._spin_max.setValue(MAX_LEN)
        self._spin_max.setSuffix(" 자")
        opts_layout.addWidget(self._spin_max)
        opts_layout.addStretch()
        layout.addWidget(group_opts)

        # 출력
        group_output = QGroupBox("출력")
        out_layout = QVBoxLayout(group_output)
        row_out = QHBoxLayout()
        row_out.addWidget(QLabel("Chunk JSONL:"))
        self._edit_output = QLineEdit()
        self._edit_output.setPlaceholderText("저장할 Chunk JSONL 경로")
        row_out.addWidget(self._edit_output)
        self._btn_browse_out = QPushButton("찾아보기")
        self._btn_browse_out.clicked.connect(self._on_browse_output)
        row_out.addWidget(self._btn_browse_out)
        out_layout.addLayout(row_out)
        self._check_validate = QCheckBox("생성 후 검증 (text 비어있지 않음, 길이, chunk_index 순차)")
        self._check_validate.setChecked(True)
        out_layout.addWidget(self._check_validate)
        self._check_coverage = QCheckBox("원본 대비 텍스트 누락 검사 (가능하면)")
        self._check_coverage.setChecked(True)
        out_layout.addWidget(self._check_coverage)
        row_btn = QHBoxLayout()
        self._btn_run = QPushButton("Chunk 생성")
        self._btn_run.clicked.connect(self._on_run)
        row_btn.addWidget(self._btn_run)
        row_btn.addStretch()
        out_layout.addLayout(row_btn)
        self._label_status = QLabel("원본 JSONL을 선택하고 Chunk 생성을 실행하세요.")
        self._label_status.setStyleSheet("color: #666;")
        out_layout.addWidget(self._label_status)
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(180)
        self._log.setPlaceholderText("검증 리포트 및 로그")
        out_layout.addWidget(self._log)
        layout.addWidget(group_output)
        layout.addStretch()

    def _on_browse_input(self) -> None:
        start = self._edit_input.text().strip() or _default_output_dir(self._state)
        path, _ = QFileDialog.getOpenFileName(
            self,
            "원본 JSONL 선택",
            start,
            "JSONL (*.jsonl);;모든 파일 (*)",
        )
        if path:
            self._edit_input.setText(path)
            self._suggest_output_path(path)

    def _suggest_output_path(self, input_path: str) -> None:
        if self._edit_output.text().strip():
            return
        p = Path(input_path)
        out_dir = p.parent
        stem = p.stem
        if not stem.endswith("_chunks"):
            stem = f"{stem}_chunks"
        self._edit_output.setText(str(out_dir / f"{stem}.jsonl"))

    def _on_browse_output(self) -> None:
        start = self._edit_output.text().strip() or _default_output_dir(self._state)
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Chunk JSONL 저장 경로",
            start,
            "JSONL (*.jsonl);;모든 파일 (*)",
        )
        if path:
            self._edit_output.setText(path)

    def _on_run(self) -> None:
        input_path = self._edit_input.text().strip()
        output_path = self._edit_output.text().strip()
        if not input_path:
            self._label_status.setText("원본 JSONL 파일을 선택하세요.")
            self._log.setPlainText("입력 파일 경로가 비어 있습니다.")
            return
        if not output_path:
            self._label_status.setText("Chunk JSONL 저장 경로를 지정하세요.")
            self._log.setPlainText("출력 파일 경로가 비어 있습니다.")
            return

        records = load_jsonl(input_path)
        if not records:
            self._label_status.setText("원본 JSONL에서 레코드를 읽지 못했습니다.")
            self._log.setPlainText("파일이 비어 있거나 형식이 맞지 않습니다.")
            return

        target_len = self._spin_target.value()
        max_len = self._spin_max.value()
        if max_len < target_len:
            max_len = target_len

        try:
            chunks = build_chunks(records, target_len=target_len, max_len=max_len)
        except Exception as e:
            self._label_status.setText(f"Chunk 생성 실패: {e}")
            self._log.setPlainText(f"오류:\n{e}")
            return

        log_lines = [f"Chunk 개수: {len(chunks)}"]

        if self._check_validate.isChecked():
            ok, messages = validate_chunks(chunks, max_len=max_len)
            log_lines.extend(messages)
            if not ok:
                self._label_status.setText("검증 실패. Chunk JSONL은 저장되었을 수 있습니다.")
        else:
            log_lines.append("검증 생략.")

        if self._check_coverage.isChecked() and records and chunks:
            cov_ok, cov_msg = validate_chunk_text_coverage(records, chunks)
            log_lines.extend(cov_msg)

        try:
            count = write_chunk_jsonl(chunks, output_path)
            log_lines.append(f"저장 완료: {output_path} ({count}줄)")
            self._label_status.setText(f"저장 완료: {output_path} ({count}줄)")
        except Exception as e:
            log_lines.append(f"저장 실패: {e}")
            self._label_status.setText(f"저장 실패: {e}")

        self._log.setPlainText("\n".join(log_lines))
