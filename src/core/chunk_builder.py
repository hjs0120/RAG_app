"""RAG용 Chunk JSONL 생성 — Merge(article+paragraph) 및 Split(600/1000) 로직."""

from __future__ import annotations

import re
from typing import Any


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
    """chunk의 meta 필드: pages, line_no 범위, chapter/section."""
    pages = []
    line_nos = []
    for ln in lines:
        p = ln.get("content_page", ln.get("page"))
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
    records: list[dict],
    *,
    target_len: int = TARGET_LEN,
    max_len: int = MAX_LEN,
    min_chunk_len: int = MIN_CHUNK_LEN,
) -> list[dict]:
    """
    원본 JSONL 레코드 리스트에서 RAG용 Chunk 리스트 생성.
    - Merge key: (doc_id, article, section, paragraph) — Phase 16
    - paragraph "0" 그룹: merge 없이 한 줄 = 한 chunk (라인별 분리)
    - min_chunk_len 미만: 이전/다음과 합치거나 건너뜀(제외)
    - 스키마: doc_id, article, section, paragraph, chunk_index, text, meta
    """
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
