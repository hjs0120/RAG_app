"""CSV 출력 (옵션)."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from src.core.export_jsonl import merge_paragraphs


def _bbox_str(bbox: list[float] | None) -> str:
    if not bbox or len(bbox) < 4:
        return ""
    return ",".join(str(x) for x in bbox[:4])


def build_csv_row(
    line: dict,
    *,
    doc_id: str,
    source_file: str,
) -> dict[str, Any]:
    """파싱된 라인 한 줄을 CSV 행(플랫 필드)으로 변환한다."""
    path = line.get("path") or {}
    row = {
        "doc_id": doc_id,
        "page": line.get("page"),
        "line_no": line.get("line_no"),
        "path_part": path.get("part"),
        "path_chapter": path.get("chapter"),
        "path_section": path.get("section"),
        "path_article": path.get("article"),
        "path_paragraph": path.get("paragraph"),
        "text": line.get("text", ""),
        "bbox": _bbox_str(line.get("bbox")),
        "source_file": source_file,
        "block_type": line.get("block_type") or "",
    }
    return row


DEFAULT_CSV_FIELDS = [
    "doc_id", "page", "line_no",
    "path_chapter", "path_section", "path_article", "path_paragraph",
    "text", "bbox", "source_file", "block_type",
]


def write_csv(
    parsed_lines: list[dict],
    output_path: str | Path,
    *,
    doc_id: str,
    source_file: str,
    fields: list[str] | None = None,
    merge_by_paragraph: bool = False,
) -> int:
    """
    파싱된 라인 리스트를 CSV 파일로 저장한다.

    Args:
        parsed_lines: path가 붙은 라인 리스트
        output_path: 출력 파일 경로
        doc_id: 문서 ID
        source_file: 소스 PDF 파일명
        fields: 포함할 컬럼 목록. None이면 DEFAULT_CSV_FIELDS 사용.
        merge_by_paragraph: True면 같은 path의 연속 라인을 하나 행으로 합침.

    Returns:
        쓴 레코드(헤더 제외) 수
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = merge_paragraphs(parsed_lines) if merge_by_paragraph else parsed_lines
    cols = fields or DEFAULT_CSV_FIELDS
    count = 0
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()
        for line in lines:
            row = build_csv_row(line, doc_id=doc_id, source_file=source_file)
            writer.writerow({k: row.get(k, "") for k in cols})
            count += 1
    return count
