"""라인 재구성 — y좌표 병합, 하이픈 줄바꿈 병합, 문단 연속 병합."""

from __future__ import annotations

import re


def _bbox_union(a: list[float], b: list[float]) -> list[float]:
    """두 bbox [x0,y0,x1,y1]의 합집합 직사각형."""
    return [
        min(a[0], b[0]),
        min(a[1], b[1]),
        max(a[2], b[2]),
        max(a[3], b[3]),
    ]


# 문단 연속 병합: 같은 내용 이어짐 판단
_RE_CONTINUATION_END = re.compile(
    r"(?:[,，:：]|및|또는|과|와|에서|하여|로|으로)\s*$"
)  # 쉼표, 콜론, 접속사로 끝
_RE_SENTENCE_END = re.compile(
    r"(?:다|한다|이다|된다|함|됨|상태|것이다)\.?\s*$"
)  # 문장 종결
_RE_NEW_SECTION = re.compile(
    r"^(?:\d+\s*편|제\s*\d+\s*[장절]|\d{2,}\.\s|\d\.\s+[가-힣]|\(\d+\)\s|[(（][가나다라마바사아자차카타파하][)）]\s)"
)  # 새 섹션/항 시작
_RE_STRUCTURAL_HEADER = re.compile(r"^제\s*\d+\s*[장절]")  # 장/절 헤더 — y-merge 금지
# 장/절 제목 이어붙임: "제 1 장" 다음 "총칙" → "제 1 장 총칙"
_RE_HEADER_TITLE_ONLY = re.compile(r"^[가-힣\s]{1,20}$")  # 한글 1~20자 (총칙, 일반사항 등)


def _is_continuation(prev_text: str, curr_text: str) -> bool:
    """
    curr가 prev의 문단 연속인지 판단.
    - prev가 쉼표/콜론/접속사로 끝 → 연속
    - prev가 문장 종결(다./한다./상태.)이면 → 비연속
    - curr가 새 섹션(제 N 장, 101., (1) 등)이면 → 비연속
    """
    prev = prev_text.strip()
    curr = curr_text.strip()
    if not prev or not curr:
        return False
    if _RE_NEW_SECTION.match(curr):
        return False
    if _RE_SENTENCE_END.search(prev):
        return False
    if _RE_CONTINUATION_END.search(prev):
        return True
    # "(4)호, (5)호" → "(8)호..." 이어가기
    if re.search(r"\)호\s*$", prev):
        return True
    # "(2) 보통(FAIR):" 다음 "휠보강재의..." 등 : 끝나면 연속
    if prev.rstrip().endswith((":", "：")):
        return True
    # "고려하는 부위" 다음 "중 20% 이상에..." — 문장 이어가기
    if re.match(r"^(중|및|또는|과|와|등|그리고)\s", curr):
        return True
    return False


def rebuild_lines(
    lines: list[dict],
    *,
    y_tolerance: float = 2.0,
    hyphen_merge: bool = False,
    paragraph_merge: bool = True,
) -> list[dict]:
    """
    같은 y 좌표 라인 병합, 하이픈 줄바꿈 병합, 문단 연속 병합.

    Args:
        lines: extract_pymupdf 추출 결과 (text, bbox, page, line_no)
        y_tolerance: 같은 줄로 볼 y 거리 (포인트)
        hyphen_merge: True면 이전 라인 끝이 '-'로 끝날 때 다음 라인과 합침
        paragraph_merge: True면 문단 연속(쉼표/접속사 이어짐) 라인 병합

    Returns:
        재구성된 라인 리스트. page별 line_no는 1부터 재부여.
    """
    if not lines:
        return []

    # 페이지별로 그룹
    by_page: dict[int, list[dict]] = {}
    for ln in lines:
        p = ln.get("page", 1)
        by_page.setdefault(p, []).append(dict(ln))

    out: list[dict] = []
    for page in sorted(by_page.keys()):
        page_lines = by_page[page]
        page_lines.sort(key=lambda x: (x["bbox"][1], x["bbox"][0]))

        merged: list[dict] = []
        for ln in page_lines:
            bbox = ln["bbox"]
            y_center = (bbox[1] + bbox[3]) / 2
            text = ln.get("text", "").strip()
            segs = ln.get("segments") or [{"text": text, "bold": False}]

            if merged:
                last = merged[-1]
                last_text = last.get("text", "").strip()
                # 장/절 헤더는 다른 라인과 y-merge 하지 않음 (항상 별도 라인 유지)
                if not (_RE_STRUCTURAL_HEADER.search(last_text) or _RE_STRUCTURAL_HEADER.search(text)):
                    last_y = (last["bbox"][1] + last["bbox"][3]) / 2
                    if abs(y_center - last_y) <= y_tolerance:
                        last["text"] = last.get("text", "") + " " + text
                        last["bbox"] = _bbox_union(last["bbox"], bbox)
                        last["segments"] = last.get("segments", []) + segs
                        continue
            merged.append({"text": text, "bbox": list(bbox), "page": page, "segments": segs})

        merged = _merge_header_title_continuations(merged, page)
        if hyphen_merge:
            merged = _merge_hyphen_breaks(merged, page)
        if paragraph_merge:
            merged = _merge_paragraph_continuations(merged, page)

        for i, ln in enumerate(merged, start=1):
            ln["line_no"] = i
            out.append(ln)

    return out


def _merge_header_title_continuations(lines: list[dict], page: int) -> list[dict]:
    """
    "제 1 장" 다음 "총칙" → "제 1 장 총칙" 같이 장/절 제목만 이어붙임.
    goal: chapter="제 1 장 총칙", section="제 1 절 일반사항" 전체 텍스트 확보.
    """
    if len(lines) <= 1:
        return lines
    result: list[dict] = []
    i = 0
    while i < len(lines):
        current = dict(lines[i])
        text = current.get("text", "").strip()
        bbox = list(current["bbox"])
        segs = list(current.get("segments") or [{"text": text, "bold": False}])
        while i + 1 < len(lines):
            next_ln = lines[i + 1]
            next_text = next_ln.get("text", "").strip()
            if not next_text:
                i += 1
                continue
            # 이전이 장/절 헤더(제목만 있거나 짧은 rest)이고, 다음이 제목 연속(한글 1~20자, 구조 아님)
            if _RE_STRUCTURAL_HEADER.match(text) and _RE_HEADER_TITLE_ONLY.match(next_text):
                if not _RE_NEW_SECTION.match(next_text) and len(next_text) <= 20:
                    text = text + " " + next_text
                    bbox = _bbox_union(bbox, next_ln["bbox"])
                    segs = segs + (next_ln.get("segments") or [{"text": next_text, "bold": False}])
                    i += 1
                    continue
            break
        current["text"] = text
        current["bbox"] = bbox
        current["page"] = page
        current["segments"] = segs
        result.append(current)
        i += 1
    return result


def _merge_paragraph_continuations(lines: list[dict], page: int) -> list[dict]:
    """
    문단 연속(쉼표/접속사 이어짐, 같은 내용 이어짐)인 라인을 병합.
    예: "(2) 보통(FAIR):" 설명 3줄, "502.의 2항의 (4)호, (5)호, ..." 여러 줄.
    """
    if len(lines) <= 1:
        return lines
    result: list[dict] = []
    i = 0
    while i < len(lines):
        current = dict(lines[i])
        text = current.get("text", "").strip()
        bbox = list(current["bbox"])
        segs = list(current.get("segments") or [{"text": text, "bold": False}])
        while i + 1 < len(lines):
            next_ln = lines[i + 1]
            next_text = next_ln.get("text", "").strip()
            if not _is_continuation(text, next_text):
                break
            text = text + " " + next_text
            bbox = _bbox_union(bbox, next_ln["bbox"])
            segs = segs + (next_ln.get("segments") or [{"text": next_text, "bold": False}])
            i += 1
        current["text"] = text
        current["bbox"] = bbox
        current["page"] = page
        current["segments"] = segs
        result.append(current)
        i += 1
    return result


def _merge_hyphen_breaks(lines: list[dict], page: int) -> list[dict]:
    """끝이 '-'로 끝나는 라인을 다음 라인과 합친다 (줄바꿈 하이픈 제거)."""
    if len(lines) <= 1:
        return lines

    result: list[dict] = []
    i = 0
    while i < len(lines):
        current = dict(lines[i])
        text = current.get("text", "").strip()
        bbox = list(current["bbox"])

        segs = list(current.get("segments") or [{"text": text, "bold": False}])
        while i + 1 < len(lines) and text.endswith("-"):
            next_ln = lines[i + 1]
            next_text = next_ln.get("text", "").strip()
            text = text[:-1].rstrip() + next_text
            bbox = _bbox_union(bbox, next_ln["bbox"])
            segs = segs + (next_ln.get("segments") or [{"text": next_text, "bold": False}])
            i += 1

        current["text"] = text
        current["bbox"] = bbox
        current["page"] = page
        current["segments"] = segs
        result.append(current)
        i += 1

    return result
