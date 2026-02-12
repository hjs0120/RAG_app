"""Export 탭 — JSONL/CSV 저장."""

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QPushButton,
    QLabel,
    QComboBox,
    QCheckBox,
    QPlainTextEdit,
)
from PySide6.QtCore import Qt

from src.core.export_jsonl import write_jsonl, validate_jsonl_file
from src.core.export_csv import write_csv


class TabExport(QWidget):
    """Export 탭 — 포맷 선택, 저장, DB Import 친화 검증."""

    def __init__(self, app_state: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = app_state
        layout = QVBoxLayout(self)

        # Group: 포맷
        group_format = QGroupBox("포맷")
        format_layout = QVBoxLayout(group_format)
        row_fmt = QHBoxLayout()
        row_fmt.addWidget(QLabel("출력 포맷:"))
        self._combo_format = QComboBox()
        self._combo_format.addItem("JSONL (기본)", "jsonl")
        self._combo_format.addItem("CSV", "csv")
        row_fmt.addWidget(self._combo_format)
        row_fmt.addStretch()
        format_layout.addLayout(row_fmt)
        self._check_merge_para = QCheckBox("Paragraph 단위로 합치기 (같은 path 연속 라인 → 1개 레코드, bbox는 union)")
        self._check_merge_para.setChecked(True)
        self._check_merge_para.setToolTip("같은 장/절/조/항의 연속된 본문을 하나의 텍스트로 합칩니다. bbox는 해당 단락 전체를 감싸는 직사각형(union)으로 출력됩니다.")
        format_layout.addWidget(self._check_merge_para)
        layout.addWidget(group_format)

        # Group: 출력
        group_output = QGroupBox("출력")
        output_layout = QVBoxLayout(group_output)
        row_btn = QHBoxLayout()
        self._btn_save = QPushButton("저장")
        self._btn_save.clicked.connect(self._on_save)
        row_btn.addWidget(self._btn_save)
        self._check_validate = QCheckBox("DB Import 친화 검증 (저장 후 JSONL 검증)")
        self._check_validate.setChecked(True)
        row_btn.addWidget(self._check_validate)
        row_btn.addStretch()
        output_layout.addLayout(row_btn)
        self._label_status = QLabel("Parse 탭에서 Path 태깅을 먼저 실행하세요.")
        self._label_status.setStyleSheet("color: #666;")
        output_layout.addWidget(self._label_status)
        self._validation_result = QPlainTextEdit()
        self._validation_result.setReadOnly(True)
        self._validation_result.setMaximumHeight(120)
        self._validation_result.setPlaceholderText("저장 후 검증 결과가 여기에 표시됩니다.")
        output_layout.addWidget(self._validation_result)
        layout.addWidget(group_output)
        layout.addStretch()

    def _on_save(self) -> None:
        parsed = self._state.get("parsed_lines", [])
        if not parsed:
            self._label_status.setText("Parse 탭에서 Path 태깅을 먼저 실행하세요.")
            self._validation_result.clear()
            return
        doc_id = (self._state.get("doc_id") or "").strip() or "export"
        output_dir = self._state.get("output_dir") or "output"
        pdf_paths = self._state.get("pdf_paths", [])
        source_file = Path(pdf_paths[0]).name if pdf_paths else "unknown.pdf"
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        fmt = self._combo_format.currentData()
        merge_para = self._check_merge_para.isChecked()
        if fmt == "csv":
            out_file = out_path / f"{doc_id}.csv"
            try:
                count = write_csv(
                    parsed,
                    out_file,
                    doc_id=doc_id,
                    source_file=source_file,
                    merge_by_paragraph=merge_para,
                )
                self._label_status.setText(f"저장 완료: {out_file} ({count}행)")
            except Exception as e:
                self._label_status.setText(f"저장 실패: {e}")
            self._validation_result.setPlainText("CSV는 DB Import 검증 대상이 아닙니다. 저장만 완료되었습니다.")
            return
        # JSONL
        out_file = out_path / f"{doc_id}.jsonl"
        try:
            count = write_jsonl(
                parsed,
                out_file,
                doc_id=doc_id,
                source_file=source_file,
                merge_by_paragraph=merge_para,
            )
            self._label_status.setText(f"저장 완료: {out_file} ({count}행)")
        except Exception as e:
            self._label_status.setText(f"저장 실패: {e}")
            self._validation_result.clear()
            return
        if self._check_validate.isChecked():
            ok, messages = validate_jsonl_file(out_file)
            if ok:
                self._validation_result.setPlainText("\n".join(messages))
            else:
                self._validation_result.setPlainText("검증 결과:\n" + "\n".join(messages))
        else:
            self._validation_result.clear()
