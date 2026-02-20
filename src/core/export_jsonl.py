"""goal.md 형식의 JSONL 출력."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = {"doc_id", "page", "path", "text", "bbox", "source"}


def _path_key(path: dict | None) -> tuple[Any, ...]:
    """path로 paragraph 그룹을 구분하는 키. 동일 키 = 같은 paragraph."""
    if not path:
        return (None, None, None, None)
    return (
        path.get("chapter"),
        path.get("section"),
        path.get("article"),
        path.get("paragraph"),
    )


def _bbox_union(bboxes: list[list[float]]) -> list[float]:
    """여러 bbox [x0,y0,x1,y1]를 감싸는 최소 직사각형(union) 반환."""
    if not bboxes:
        return []
    valid = [b for b in bboxes if b and len(b) >= 4]
    if not valid:
        return []
    return [
        min(b[0] for b in valid),
        min(b[1] for b in valid),
        max(b[2] for b in valid),
        max(b[3] for b in valid),
    ]


def _path_page_key(line: dict) -> tuple[Any, ...]:
    """(path, page)로 paragraph 그룹을 구분. 같은 path라도 페이지가 바뀌면 별도 그룹."""
    path_k = _path_key(line.get("path"))
    page = line.get("page")
    return (*path_k, page)


def merge_paragraphs(parsed_lines: list[dict]) -> list[dict]:
    """
    같은 path(chapter/section/article/paragraph) **그리고 같은 page**를 가진 연속 라인을
    하나의 레코드로 합친다. 페이지가 넘어가면 (path, page)가 바뀌므로 별도 레코드가 된다.

    - text: 해당 그룹(같은 path+page) 내에서만 공백 하나로 이어붙임
    - bbox: 해당 그룹 내 라인들의 union (페이지 단위로 구분됨)
    - page, line_no: 해당 그룹의 첫 라인 값

    Returns:
        합쳐진 레코드 리스트. 각 항목은 원본과 동일한 키를 가지며 text, bbox만 병합됨.
    """
    if not parsed_lines:
        return []
    out: list[dict] = []
    group: list[dict] = []
    current_key = None

    def flush() -> None:
        if not group:
            return
        first = group[0]
        path = first.get("path") or {}
        texts = [ln.get("text", "").strip() for ln in group if ln.get("text")]
        bboxes = [ln.get("bbox") for ln in group if ln.get("bbox")]
        out.append({
            "text": " ".join(texts),
            "bbox": _bbox_union(bboxes),
            "page": first.get("page"),
            "line_no": first.get("line_no"),
            "path": dict(path),
        })
        if "block_type" in first:
            out[-1]["block_type"] = first["block_type"]

    for line in parsed_lines:
        key = _path_page_key(line)
        if key != current_key:
            flush()
            group = []
            current_key = key
        group.append(line)
    flush()
    return out


def build_record(
    line: dict,
    *,
    doc_id: str,
    source_file: str,
    content_start_pdf_page: int | None = None,
) -> dict[str, Any]:
    """
    파싱된 라인 한 줄을 goal.md 1.3절 형식의 export 레코드로 변환한다.

    Args:
        line: path가 붙은 라인 (text, bbox, page, line_no, path)
        doc_id: 문서 ID
        source_file: 소스 PDF 파일명(경로 제외)
        content_start_pdf_page: 본문 시작 PDF 페이지. 있으면 content_page(문서 내 페이지) 계산

    Returns:
        doc_id, page, content_page, line_no, path, text, bbox, source 를 갖는 딕셔너리
    """
    path = line.get("path") or {}
    page = line.get("page")
    content_page: int | None = None
    if page is not None and content_start_pdf_page is not None:
        content_page = max(1, page - content_start_pdf_page + 1)
    rec = {
        "doc_id": doc_id,
        "page": page,
        "content_page": content_page if content_page is not None else page,
        "line_no": line.get("line_no"),
        "path": {
            "part": path.get("part"),
            "chapter": path.get("chapter"),
            "section": path.get("section"),
            "article": path.get("article"),
            "paragraph": path.get("paragraph"),
        },
        "text": line.get("text", ""),
        "bbox": line.get("bbox") or [],
        "source": {"file": source_file},
    }
    if "block_type" in line and line["block_type"]:
        rec["block_type"] = line["block_type"]
    return rec


def write_jsonl(
    parsed_lines: list[dict],
    output_path: str | Path,
    *,
    doc_id: str,
    source_file: str,
    merge_by_paragraph: bool = False,
    content_start_pdf_page: int | None = None,
) -> int:
    """
    파싱된 라인 리스트를 JSONL 파일로 저장한다.

    Args:
        parsed_lines: path가 붙은 라인 리스트
        output_path: 출력 파일 경로
        doc_id: 문서 ID
        source_file: 소스 PDF 파일명
        merge_by_paragraph: True면 같은 path의 연속 라인을 하나 레코드로 합침(bbox는 union)
        content_start_pdf_page: 본문 시작 PDF 페이지. 있으면 content_page(문서 내 페이지) 추가

    Returns:
        쓴 레코드(라인) 수
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = merge_paragraphs(parsed_lines) if merge_by_paragraph else parsed_lines
    count = 0
    with open(output_path, "w", encoding="utf-8") as f:
        for line in lines:
            rec = build_record(
                line,
                doc_id=doc_id,
                source_file=source_file,
                content_start_pdf_page=content_start_pdf_page,
            )
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            count += 1
    return count


def write_records_jsonl(records: list[dict], output_path: str | Path) -> int:
    """
    이미 export 형식인 레코드 리스트를 JSONL 파일로 저장한다. (검수 탭 저장용)

    Args:
        records: doc_id, page, line_no, path, text, bbox, source 등을 가진 딕셔너리 리스트
        output_path: 출력 파일 경로

    Returns:
        쓴 레코드(라인) 수
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with open(output_path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            count += 1
    return count


def load_jsonl(file_path: str | Path) -> list[dict]:
    """
    JSONL 파일을 읽어 레코드 리스트로 반환한다.

    Args:
        file_path: JSONL 파일 경로

    Returns:
        각 줄을 파싱한 딕셔너리 리스트. 파싱 실패한 줄은 건너뛴다.
    """
    file_path = Path(file_path)
    records: list[dict] = []
    if not file_path.is_file():
        return records
    with open(file_path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def validate_jsonl_file(file_path: str | Path) -> tuple[bool, list[str]]:
    """
    JSONL 파일에 대한 DB Import 친화 검증을 수행한다.

    - 각 줄이 유효한 JSON인지
    - 필수 필드(doc_id, page, path, text, bbox, source) 누락 여부

    Returns:
        (모두 통과 여부, 메시지 리스트)
    """
    file_path = Path(file_path)
    messages: list[str] = []
    all_ok = True
    if not file_path.is_file():
        return False, ["파일이 없습니다."]
    with open(file_path, "r", encoding="utf-8") as f:
        for i, raw in enumerate(f, 1):
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                all_ok = False
                messages.append(f"라인 {i}: JSON 파싱 실패 — {e}")
                continue
            missing = REQUIRED_FIELDS - set(obj.keys())
            if missing:
                all_ok = False
                messages.append(f"라인 {i}: 필수 필드 누락 — {missing}")
    if all_ok and not messages:
        messages.append("JSON 파싱 가능.")
        messages.append("필수 필드 누락 없음.")
    return all_ok, messages
