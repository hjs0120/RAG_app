"""RAG용 Chunk JSONL 생성 — Merge(article+paragraph) 및 Split(600/1000) 로직.

Phase 4: Canonical JSON 입력 지원. list[CanonicalRecord] 또는 list[dict] (Canonical to_dict).
V2 JSONL (path 기반) 하위 호환.
"""

from __future__ import annotations

import re
from typing import Any, Union

from src.core.canonical_schema import CanonicalRecord


# 기본값 (Phase 13 명세)
TARGET_LEN = 600
MAX_LEN = 1000
MIN_CHUNK_LEN = 30  # Phase 16: 너무 짧은 chunk 방지


def _norm(v: Any) -> str:
    """None/빈 값을 빈 문자열로, 아니면 str."""
    if v is None:
        return ""
    s = str(v).strip()
    return s if s else ""


def merge_key(record: dict) -> tuple[str, str, str, str]:
    """
    그룹핑용 Merge Key 생성. (Phase 16: section 포함)
    - doc_id
    - article (없으면 chapter+section, 둘 다 없으면 "_")
    - section (101.적용 vs 101.하중 구분, 없으면 chapter_section 또는 "_")
    - paragraph (없으면 "0")
    """
    doc_id = _norm(record.get("doc_id")) or "_"
    path = record.get("path") or {}
    article = _norm(path.get("article"))
    section = _norm(path.get("section"))
    paragraph = _norm(path.get("paragraph"))
    if not article:
        ch = _norm(path.get("chapter"))
        sec = _norm(path.get("section"))
        article = f"{ch}_{sec}" if (ch or sec) else "_"
    if not section and article != "_":
        # section 없으면 chapter 등으로 fallback
        ch = _norm(path.get("chapter"))
        section = ch if ch else "_"
    if not section:
        section = "_"
    if not paragraph:
        paragraph = "0"
    return (doc_id, article, section, paragraph)


# ----- Canonical (Phase 4) -----


def _is_canonical(record: Any) -> bool:
    """레코드가 Canonical 형식(dict 또는 CanonicalRecord)인지 판별."""
    if hasattr(record, "content") and hasattr(record, "structure"):
        return True
    if isinstance(record, dict) and "content" in record:
        return True
    return False


def _record_to_canonical_dict(record: Union[CanonicalRecord, dict]) -> dict:
    """CanonicalRecord 또는 dict를 Canonical dict로 정규화."""
    if hasattr(record, "to_dict"):
        return record.to_dict()
    return record


def _canonical_text(rec: dict) -> str:
    """Canonical dict에서 본문 텍스트 추출."""
    content = rec.get("content") or {}
    return (content.get("text") or "").strip()


def _canonical_structure_path(rec: dict) -> str:
    """Canonical structure를 '제1장 > 제1절 > 제101조 > 1항' 형태로 조합."""
    structure = rec.get("structure") or []
    if not structure:
        return ""
    labels = []
    for s in structure:
        if isinstance(s, dict):
            labels.append(s.get("label") or "")
        else:
            labels.append(getattr(s, "label", ""))
    return " > ".join(l for l in labels if l)


def _canonical_merge_key(rec: dict) -> tuple[str, str, bool]:
    """
    Canonical 그룹핑용 키.
    Returns: (doc_id, structure_path, is_merge_group)
    - is_merge_group: structure 마지막 type이 paragraph면 True (merge 대상)
    """
    doc_id = _norm(rec.get("doc_id")) or "_"
    structure = rec.get("structure") or []
    path = _canonical_structure_path(rec)

    is_merge = False
    if structure:
        last = structure[-1]
        stype = last.get("type") if isinstance(last, dict) else getattr(last, "type", "")
        is_merge = stype == "paragraph"

    return (doc_id, path or "_", is_merge)


def _group_canonical(records: list[dict]) -> list[tuple[tuple[str, str, bool], list[dict]]]:
    """Canonical 레코드를 merge key로 그룹핑."""
    from itertools import groupby

    sorted_rec = sorted(records, key=_canonical_merge_key)
    out: list[tuple[tuple[str, str, bool], list[dict]]] = []
    for key, group in groupby(sorted_rec, key=_canonical_merge_key):
        out.append((key, list(group)))
    return out


def _build_canonical_chunk_meta(recs: list[dict], structure_path: str) -> dict[str, Any]:
    """Canonical Chunk의 meta: structure_path, physical_page, file_name."""
    pages: list[int] = []
    file_name = ""
    for r in recs:
        loc = r.get("location") or {}
        pp = loc.get("physical_page")
        if pp is not None and pp not in pages:
            pages.append(pp)
        src = r.get("source") or {}
        fn = src.get("file_name")
        if fn:
            file_name = str(fn)
    physical_page = pages[0] if pages else None
    return {
        "structure_path": structure_path,
        "physical_page": physical_page,
        "file_name": file_name,
        "pages": pages,
    }


def _build_chunks_from_canonical(
    records: list[Union[CanonicalRecord, dict]],
    *,
    target_len: int = TARGET_LEN,
    max_len: int = MAX_LEN,
    min_chunk_len: int = MIN_CHUNK_LEN,
) -> list[dict]:
    """
    Canonical 레코드에서 RAG용 Chunk 생성.
    스키마: chunk_id, doc_id, text, meta { structure_path, physical_page, file_name }
    """
    # dict로 정규화
    norm_recs = [_record_to_canonical_dict(r) for r in records]
    grouped = _group_canonical(norm_recs)
    chunks_out: list[dict] = []

    for (doc_id, structure_path, is_merge_group), recs in grouped:
        file_name = ""
        for r in recs:
            src = r.get("source") or {}
            if src.get("file_name"):
                file_name = str(src["file_name"])
                break

        if not is_merge_group:
            # 제목 등: 한 줄 = 한 chunk
            for idx, rec in enumerate(recs, start=1):
                text = _canonical_text(rec)
                if not text:
                    continue
                if min_chunk_len > 0 and len(text) < min_chunk_len:
                    continue
                meta = _build_canonical_chunk_meta([rec], structure_path)
                chunk_id = _make_chunk_id(doc_id, structure_path, idx)
                chunks_out.append({
                    "chunk_id": chunk_id,
                    "doc_id": doc_id,
                    "text": text,
                    "meta": meta,
                })
            continue

        # paragraph: merge 후 split
        clean_text = " ".join(_canonical_text(r) for r in recs if _canonical_text(r)).strip()
        if not clean_text:
            continue
        text_parts = split_into_chunks(clean_text, target_len=target_len, max_len=max_len)
        for idx, part in enumerate(text_parts, start=1):
            if min_chunk_len > 0 and len(part.strip()) < min_chunk_len:
                continue
            meta = _build_canonical_chunk_meta(recs, structure_path)
            chunk_id = _make_chunk_id(doc_id, structure_path, idx)
            chunks_out.append({
                "chunk_id": chunk_id,
                "doc_id": doc_id,
                "text": part.strip(),
                "meta": meta,
            })
    return chunks_out


def _make_chunk_id(doc_id: str, structure_path: str, chunk_index: int) -> str:
    """chunk_id 생성: doc_id + structure_path 축약 + chunk_index."""
    safe_path = re.sub(r"[^\w\s>]", "", structure_path).replace(" ", "").replace(">", "_")[:40]
    safe_path = safe_path.rstrip("_") if safe_path else "0"
    return f"{doc_id}_{safe_path}_{chunk_index}"


def from_legacy(records: list[dict]) -> list[dict]:
    """
    V2 JSONL 레코드를 Canonical dict 형태로 변환 (가능한 범위).
    path.article, path.section 등 → structure 추정.
    완전 변환은 아니며, build_chunks에서 V2 경로로 처리하는 것이 더 정확함.
    """
    # V2를 그대로 build_chunks_legacy에 넘기는 것이 맞음. 이 함수는 선택적.
    return records


def group_by_merge_key(records: list[dict]) -> list[tuple[tuple[str, str, str, str], list[dict]]]:
    """
    각 레코드를 merge key로 그룹핑.
    Returns:
        [( (doc_id, article, section, paragraph), [line1, line2, ...] ), ...]
    """
    from itertools import groupby
    sorted_records = sorted(records, key=merge_key)
    out: list[tuple[tuple[str, str, str], list[dict]]] = []
    for key, group in groupby(sorted_records, key=merge_key):
        out.append((key, list(group)))
    return out


def clean_group_text(lines: list[dict], join_with: str = " ") -> str:
    """
    그룹 내 라인들의 text를 합쳐 하나의 clean_text로 만든다.
    - join_with: 라인 사이 연결 문자 (기본 공백)
    - 앞뒤·연속 공백 정리
    """
    parts = []
    for ln in lines:
        t = (ln.get("text") or "").strip()
        if t:
            parts.append(t)
    return join_with.join(parts).strip()


def _split_at_sentence_end(text: str, max_len: int) -> list[str]:
    """문장 종결(다. / . 등) 기준으로 분할. max_len 넘지 않게."""
    if len(text) <= max_len:
        return [text] if text.strip() else []
    # 문장 끝 후보: "다.", "이다.", "한다." 등 또는 ". " (마침표+공백)
    pattern = re.compile(r"\.\s+|[다라마바사아자차카타파하]\.\s*")
    chunks: list[str] = []
    start = 0
    while start < len(text):
        rest = text[start:]
        if len(rest) <= max_len:
            if rest.strip():
                chunks.append(rest.strip())
            break
        # max_len 구간 안에서 마지막 문장 끝 찾기
        search_region = rest[: max_len + 1]
        last_match = None
        for m in pattern.finditer(search_region):
            last_match = m
        if last_match:
            end_pos = last_match.end()
            seg = rest[:end_pos].strip()
            if seg:
                chunks.append(seg)
            start += end_pos
        else:
            # 문장 끝 없으면 공백/줄바꿈으로 자르기
            cut = rest.rfind(" ", 0, max_len + 1)
            if cut <= 0:
                cut = max_len
            seg = rest[:cut].strip()
            if seg:
                chunks.append(seg)
            start += cut
    return chunks


def split_into_chunks(
    text: str,
    *,
    target_len: int = TARGET_LEN,
    max_len: int = MAX_LEN,
) -> list[str]:
    """
    그룹 텍스트를 target_len 권장, max_len 초과 금지로 분할.
    우선순위: \\n 기준 → 문장 종결(다. / .) 기준 → 하드 컷(문자수).
    """
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_len:
        return [text]

    chunks: list[str] = []
    remaining = text

    while len(remaining) > max_len:
        # 1) \n 기준으로 나눌 수 있는지
        segment = remaining[: max_len + 1]
        last_nl = segment.rfind("\n")
        if last_nl > target_len or (last_nl > 0 and last_nl <= max_len):
            cut = last_nl + 1
            part = remaining[:cut].rstrip()
            if len(part) > max_len:
                part = part[:max_len].rstrip() or part[:max_len]
            remaining = remaining[cut:].lstrip()
            if part:
                chunks.append(part)
            continue
        # 2) 문장 종결 기준
        sentence_chunks = _split_at_sentence_end(remaining, max_len)
        if len(sentence_chunks) >= 2:
            part = sentence_chunks[0]
            if len(part) > max_len:
                part = part[:max_len].rstrip() or part[:max_len]
            chunks.append(part)
            remaining = " ".join(sentence_chunks[1:])
            continue
        # 3) 하드 컷
        cut = remaining.rfind(" ", 0, max_len + 1)
        if cut <= 0:
            cut = max_len
        part = remaining[:cut].strip()
        if len(part) > max_len:
            part = part[:max_len].rstrip() or part[:max_len]
        remaining = remaining[cut:].lstrip()
        if part:
            chunks.append(part)

    if remaining.strip():
        chunks.append(remaining.strip())
    return chunks


def build_chunk_meta(lines: list[dict], path: dict) -> dict[str, Any]:
    """chunk의 meta 필드: pages(물리 페이지), line_no 범위, chapter/section."""
    pages: list[int] = []
    line_nos: list[int] = []
    for ln in lines:
        p = ln.get("page")
        if p is not None and p not in pages:
            pages.append(p)
        ln_no = ln.get("line_no")
        if ln_no is not None:
            line_nos.append(ln_no)
    path = path or {}
    return {
        "pages": pages,
        "line_no_range": [min(line_nos), max(line_nos)] if line_nos else None,
        "chapter": path.get("chapter"),
        "section": path.get("section"),
    }


def build_chunks(
    records: list[Union[CanonicalRecord, dict]],
    *,
    target_len: int = TARGET_LEN,
    max_len: int = MAX_LEN,
    min_chunk_len: int = MIN_CHUNK_LEN,
) -> list[dict]:
    """
    원본 레코드 리스트에서 RAG용 Chunk 리스트 생성.

    Phase 4: Canonical 입력 지원.
    - Canonical (content/structure 있음): chunk_id, doc_id, text, meta { structure_path, physical_page, file_name }
    - V2 (path 있음): doc_id, article, section, paragraph, chunk_index, text, meta

    - paragraph "0" / structure 미merge 그룹: 한 줄 = 한 chunk
    - min_chunk_len 미만: 건너뜀
    """
    if not records:
        return []

    if _is_canonical(records[0]):
        return _build_chunks_from_canonical(
            records,
            target_len=target_len,
            max_len=max_len,
            min_chunk_len=min_chunk_len,
        )

    chunks_out: list[dict] = []
    grouped = group_by_merge_key(records)

    for (doc_id, article, section, paragraph), lines in grouped:
        # paragraph "0" 그룹: merge 하지 않고 라인별 chunk
        if paragraph == "0":
            path = (lines[0].get("path") or {}) if lines else {}
            for idx, ln in enumerate(lines, start=1):
                text = (ln.get("text") or "").strip()
                if not text:
                    continue
                if min_chunk_len > 0 and len(text) < min_chunk_len:
                    continue  # 너무 짧은 제목만 chunk 제외
                meta = build_chunk_meta([ln], path)
                chunks_out.append({
                    "doc_id": doc_id,
                    "article": article,
                    "section": section,
                    "paragraph": paragraph,
                    "chunk_index": idx,
                    "text": text,
                    "meta": meta,
                })
            continue

        clean_text = clean_group_text(lines)
        if not clean_text:
            continue
        path = (lines[0].get("path") or {}) if lines else {}
        text_parts = split_into_chunks(clean_text, target_len=target_len, max_len=max_len)
        for idx, part in enumerate(text_parts, start=1):
            if min_chunk_len > 0 and len(part.strip()) < min_chunk_len:
                continue  # 너무 짧은 chunk 제외
            meta = build_chunk_meta(lines, path)
            chunks_out.append({
                "doc_id": doc_id,
                "article": article,
                "section": section,
                "paragraph": paragraph,
                "chunk_index": idx,
                "text": part.strip(),
                "meta": meta,
            })
    return chunks_out


def write_chunk_jsonl(chunks: list[dict], output_path: str | None) -> int:
    """
    Chunk 리스트를 JSONL 파일로 저장.
    output_path가 None이면 쓰지 않고 0 반환.
    Returns: 쓴 줄 수.
    """
    import json
    from pathlib import Path
    if output_path is None or not chunks:
        return 0
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with open(path, "w", encoding="utf-8") as f:
        for rec in chunks:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            count += 1
    return count
