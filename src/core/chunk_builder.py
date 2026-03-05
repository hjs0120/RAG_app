"""RAG용 Chunk JSONL 생성 — 조(Article) 단위 의미 기반 청킹.

Phase 8: Canonical structure 기반 조=1청크. 글자 수 하드 컷 폐기.
- 조 단위로 그룹핑, 초과 시 항(①②③) 우선 → 마침표 기준 분할
- 모든 청크 서두에 [제N조 제목] 헤더 삽입
"""

from __future__ import annotations

import re
from itertools import groupby
from typing import Any, Union

from src.core.canonical_schema import CanonicalRecord


# 기본값 (Phase 8)
DEFAULT_SPLIT_THRESHOLD = 1000  # 조문 분할 임계치(자): 이 값 초과 시 항/마침표 기준 분할
MIN_CHUNK_LEN = 30  # 너무 짧은 chunk 방지


def _norm(v: Any) -> str:
    """None/빈 값을 빈 문자열로, 아니면 str."""
    if v is None:
        return ""
    s = str(v).strip()
    return s if s else ""


def merge_key(record: dict) -> tuple[str, str, str, str]:
    """
    그룹핑용 Merge Key 생성 (V2 레거시).
    - doc_id, article, section, paragraph
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
        ch = _norm(path.get("chapter"))
        section = ch if ch else "_"
    if not section:
        section = "_"
    if not paragraph:
        paragraph = "0"
    return (doc_id, article, section, paragraph)


# ----- Canonical (Phase 4 + Phase 8) -----


def _is_canonical(record: Any) -> bool:
    """레코드가 Canonical 형식인지 판별."""
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


def _extract_article_label(rec: dict) -> str | None:
    """structure에서 article type의 label 추출. 없으면 None."""
    structure = rec.get("structure") or []
    for s in structure:
        stype = s.get("type") if isinstance(s, dict) else getattr(s, "type", "")
        if stype == "article":
            label = s.get("label") if isinstance(s, dict) else getattr(s, "label", "")
            return _norm(label) or None
    return None


def _extract_article_header(recs: list[dict]) -> str:
    """
    청크 헤더용 문자열 생성. [제N조 제목] 형태.
    첫 레코드 본문에서 '제10조(제목)' 패턴 추출, 없으면 structure의 article label 사용.
    """
    if not recs:
        return ""
    first_text = _canonical_text(recs[0])
    # 제10조(피성년후견인의 행위와 취소) 또는 제 10조(제목) 패턴
    m = re.search(r"제\s*\d+(?:의\d+)?\s*조\s*(?:\([^)]+\))?", first_text)
    if m:
        return m.group(0).strip()
    # structure에서 article label 사용
    for r in recs:
        lab = _extract_article_label(r)
        if lab:
            return lab
    return ""


def _article_group_key(rec: dict) -> tuple[str, str]:
    """조(Article) 단위 그룹핑 키. (doc_id, article_label). article 없으면 (doc_id, _title_구분자)"""
    doc_id = _norm(rec.get("doc_id")) or "_"
    article = _extract_article_label(rec)
    if article:
        return (doc_id, article)
    # 제목 등: structure_path로 구분하여 각각 별도 청크
    path = _canonical_structure_path(rec)
    return (doc_id, f"_title_{path}" if path else "_title")


def _group_canonical_by_article(records: list[dict]) -> list[tuple[tuple[str, str], list[dict]]]:
    """Canonical 레코드를 조(Article) 단위로 그룹핑. 원본 순서 유지."""
    # 원본 순서 유지하며 article 기준으로 그룹
    result: list[tuple[tuple[str, str], list[dict]]] = []
    current_key: tuple[str, str] | None = None
    current_group: list[dict] = []

    for rec in records:
        key = _article_group_key(rec)
        if key != current_key:
            if current_group:
                result.append((current_key, current_group))
            current_key = key
            current_group = [rec]
        else:
            current_group.append(rec)

    if current_group:
        result.append((current_key, current_group))
    return result


def _build_canonical_chunk_meta(recs: list[dict], structure_path: str) -> dict[str, Any]:
    """Canonical Chunk의 meta: structure_path, physical_page, file_name, pages."""
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


# ----- Phase 8: 항/마침표 기준 분할 (하드 컷 없음) -----

# 항 번호 패턴: ①②③④⑤⑥⑦⑧⑨⑩, (1) (2), 1) 2) 등
_RE_PARAGRAPH = re.compile(r"([①②③④⑤⑥⑦⑧⑨⑩]|\s*\(\s*\d+\s*\)\s*|\s*\d+\)\s*)")
# 문장 끝: "다.", "본다.", "한다." 등 또는 ". "
_RE_SENTENCE_END = re.compile(r"\.\s+|[다라마바사아자차카타파하]\.\s*")


def _split_at_paragraph_boundaries(text: str, max_len: int) -> list[str]:
    """항(①②③) 경계를 먼저 찾아 분할. 각 파트가 max_len 초과 시 문장 끝으로 추가 분할."""
    text = text.strip()
    if not text or len(text) <= max_len:
        return [text] if text.strip() else []

    # ① ② ③ 위치 수집 (항 시작점)
    positions: list[int] = []
    for m in _RE_PARAGRAPH.finditer(text):
        positions.append(m.start())
    if not positions:
        # 항 마커 없으면 문장 끝 기준으로만 분할
        return _split_at_sentence_end(text, max_len)

    # 항 경계로 분할 (각 segment = 한 항)
    parts: list[str] = []
    for i, pos in enumerate(positions):
        end = positions[i + 1] if i + 1 < len(positions) else len(text)
        seg = text[pos:end].strip()
        if seg:
            parts.append(seg)
    # 첫 ① 이전 내용(조 제목+도입)이 있으면 첫 파트로
    if positions[0] > 0:
        lead = text[: positions[0]].strip()
        if lead:
            parts.insert(0, lead)

    # 각 파트가 max_len 초과면 문장 끝 기준으로 추가 분할
    result: list[str] = []
    for p in parts:
        if len(p) <= max_len:
            result.append(p)
        else:
            result.extend(_split_at_sentence_end(p, max_len))
    return result


def _split_at_sentence_end(text: str, max_len: int) -> list[str]:
    """문장 종결(다. / . 등) 기준으로만 분할. 하드 컷 없음."""
    if len(text) <= max_len:
        return [text] if text.strip() else []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        rest = text[start:].strip()
        if not rest:
            break
        if len(rest) <= max_len:
            chunks.append(rest)
            break
        search_region = rest[: max_len + 1]
        last_match = None
        for m in _RE_SENTENCE_END.finditer(search_region):
            last_match = m
        if last_match:
            end_pos = last_match.end()
            seg = rest[:end_pos].strip()
            if seg:
                chunks.append(seg)
            start += len(rest[:end_pos])
        else:
            # 문장 끝 없으면 max_len 직후 첫 문장 끝까지 확장 (하드 컷 금지)
            extended = rest[: max_len + 200]
            m2 = _RE_SENTENCE_END.search(rest[max_len:])
            if m2:
                end_pos = max_len + m2.end()
                seg = rest[:end_pos].strip()
                if seg:
                    chunks.append(seg)
                start += len(rest[:end_pos])
            else:
                chunks.append(rest)
                break
    return chunks


def _split_article_semantic(text: str, split_threshold: int) -> list[str]:
    """
    조문이 split_threshold 초과 시, 항(①②③) 우선 → 마침표 순으로 분할.
    하드 컷 없음.
    """
    text = text.strip()
    if not text:
        return []
    if len(text) <= split_threshold:
        return [text]
    return _split_at_paragraph_boundaries(text, split_threshold)


def _build_chunks_from_canonical(
    records: list[Union[CanonicalRecord, dict]],
    *,
    split_threshold: int = DEFAULT_SPLIT_THRESHOLD,
    min_chunk_len: int = MIN_CHUNK_LEN,
) -> list[dict]:
    """
    Canonical 레코드에서 RAG용 Chunk 생성 (Phase 8).
    - 조(Article) 단위 그룹핑
    - 조문 길이 <= split_threshold: 1청크
    - 조문 길이 > split_threshold: 항(①②③) 우선 → 마침표 기준 분할
    - 모든 청크 서두에 [제N조 제목] 헤더 삽입
    """
    norm_recs = [_record_to_canonical_dict(r) for r in records]
    grouped = _group_canonical_by_article(norm_recs)
    chunks_out: list[dict] = []

    for (doc_id, article_key), recs in grouped:
        structure_path = _canonical_structure_path(recs[0]) if recs else ""
        header = _extract_article_header(recs) if article_key != "_title" else ""
        header_prefix = f"[{header}] " if header else ""

        if article_key == "_title":
            # 제목 등 (article 없음): 한 줄 = 한 chunk
            for idx, rec in enumerate(recs, start=1):
                text = _canonical_text(rec)
                if not text:
                    continue
                if min_chunk_len > 0 and len(text) < min_chunk_len:
                    continue
                meta = _build_canonical_chunk_meta([rec], structure_path)
                chunk_id = _make_chunk_id(doc_id, structure_path or "_title", idx)
                chunks_out.append({
                    "chunk_id": chunk_id,
                    "doc_id": doc_id,
                    "text": text,
                    "meta": meta,
                })
            continue

        # 조(Article) 본문: merge 후 필요 시 분할
        clean_text = " ".join(_canonical_text(r) for r in recs if _canonical_text(r)).strip()
        if not clean_text:
            continue

        text_parts = _split_article_semantic(clean_text, split_threshold)
        for idx, part in enumerate(text_parts, start=1):
            part = part.strip()
            if not part:
                continue
            if min_chunk_len > 0 and len(part) < min_chunk_len:
                continue
            meta = _build_canonical_chunk_meta(recs, structure_path)
            chunk_id = _make_chunk_id(doc_id, structure_path, idx)
            # 모든 청크 서두에 헤더 삽입
            chunks_out.append({
                "chunk_id": chunk_id,
                "doc_id": doc_id,
                "text": header_prefix + part,
                "meta": meta,
            })
    return chunks_out


def _make_chunk_id(doc_id: str, structure_path: str, chunk_index: int) -> str:
    """chunk_id 생성."""
    safe_path = re.sub(r"[^\w\s>]", "", structure_path).replace(" ", "").replace(">", "_")[:40]
    safe_path = safe_path.rstrip("_") if safe_path else "0"
    return f"{doc_id}_{safe_path}_{chunk_index}"


def from_legacy(records: list[dict]) -> list[dict]:
    """V2 JSONL → Canonical dict 형태 변환 (선택적)."""
    return records


def group_by_merge_key(records: list[dict]) -> list[tuple[tuple[str, str, str, str], list[dict]]]:
    """V2 레거시: merge key로 그룹핑."""
    sorted_records = sorted(records, key=merge_key)
    out: list[tuple[tuple[str, str, str, str], list[dict]]] = []
    for key, group in groupby(sorted_records, key=merge_key):
        out.append((key, list(group)))
    return out


def clean_group_text(lines: list[dict], join_with: str = " ") -> str:
    """그룹 내 text 합침."""
    parts = []
    for ln in lines:
        t = (ln.get("text") or "").strip()
        if t:
            parts.append(t)
    return join_with.join(parts).strip()


def build_chunk_meta(lines: list[dict], path: dict) -> dict[str, Any]:
    """V2 레거시: chunk meta."""
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
    split_threshold: int = DEFAULT_SPLIT_THRESHOLD,
    min_chunk_len: int = MIN_CHUNK_LEN,
) -> list[dict]:
    """
    RAG용 Chunk 리스트 생성.

    Phase 8: Canonical은 조 단위 청킹. split_threshold 초과 시 항/마침표 기준 분할.
    V2(path 기반): 기존 merge+split 로직 유지 (split_threshold 적용).
    """
    if not records:
        return []

    if _is_canonical(records[0]):
        return _build_chunks_from_canonical(
            records,
            split_threshold=split_threshold,
            min_chunk_len=min_chunk_len,
        )

    # V2 레거시 경로 (해양규칙 등 path 기반)
    chunks_out: list[dict] = []
    grouped = group_by_merge_key(records)
    for (doc_id, article, section, paragraph), lines in grouped:
        if paragraph == "0":
            path = (lines[0].get("path") or {}) if lines else {}
            for idx, ln in enumerate(lines, start=1):
                text = (ln.get("text") or "").strip()
                if not text:
                    continue
                if min_chunk_len > 0 and len(text) < min_chunk_len:
                    continue
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
        # V2도 split_threshold 사용 (문자 수 하드 컷 없음)
        text_parts = _split_article_semantic(clean_text, split_threshold)
        for idx, part in enumerate(text_parts, start=1):
            part = part.strip()
            if not part:
                continue
            if min_chunk_len > 0 and len(part) < min_chunk_len:
                continue
            meta = build_chunk_meta(lines, path)
            chunks_out.append({
                "doc_id": doc_id,
                "article": article,
                "section": section,
                "paragraph": paragraph,
                "chunk_index": idx,
                "text": part,
                "meta": meta,
            })
    return chunks_out


def write_chunk_jsonl(chunks: list[dict], output_path: str | None) -> int:
    """Chunk 리스트를 JSONL로 저장."""
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
