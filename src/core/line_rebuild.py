"""라인 재구성 — y좌표 병합, 하이픈 줄바꿈 병합."""

from __future__ import annotations


def _bbox_union(a: list[float], b: list[float]) -> list[float]:
    """두 bbox [x0,y0,x1,y1]의 합집합 직사각형."""
    return [
        min(a[0], b[0]),
        min(a[1], b[1]),
        max(a[2], b[2]),
        max(a[3], b[3]),
    ]


def rebuild_lines(
    lines: list[dict],
    *,
    y_tolerance: float = 2.0,
    hyphen_merge: bool = False,
) -> list[dict]:
    """
    같은 y 좌표 라인 병합, 선택적으로 하이픈 줄바꿈 병합.

    Args:
        lines: extract_pymupdf 추출 결과 (text, bbox, page, line_no)
        y_tolerance: 같은 줄로 볼 y 거리 (포인트)
        hyphen_merge: True면 이전 라인 끝이 '-'로 끝날 때 다음 라인과 합침

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
        # y 기준 정렬 (위에서 아래)
        page_lines.sort(key=lambda x: (x["bbox"][1], x["bbox"][0]))

        # 같은 y(±tolerance) 끼리 병합
        merged: list[dict] = []
        for ln in page_lines:
            bbox = ln["bbox"]
            y_center = (bbox[1] + bbox[3]) / 2
            text = ln.get("text", "").strip()

            if merged:
                last = merged[-1]
                last_y = (last["bbox"][1] + last["bbox"][3]) / 2
                if abs(y_center - last_y) <= y_tolerance:
                    # 같은 줄로 병합
                    last["text"] = last.get("text", "") + " " + text
                    last["bbox"] = _bbox_union(last["bbox"], bbox)
                    continue
            merged.append({"text": text, "bbox": list(bbox), "page": page})

        # 하이픈 줄바꿈 병합
        if hyphen_merge:
            merged = _merge_hyphen_breaks(merged, page)

        for i, ln in enumerate(merged, start=1):
            ln["line_no"] = i
            out.append(ln)

    return out


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

        while i + 1 < len(lines) and text.endswith("-"):
            next_ln = lines[i + 1]
            next_text = next_ln.get("text", "").strip()
            text = text[:-1].rstrip() + next_text  # 하이픈 제거 후 이어붙임
            bbox = _bbox_union(bbox, next_ln["bbox"])
            i += 1

        current["text"] = text
        current["bbox"] = bbox
        current["page"] = page
        result.append(current)
        i += 1

    return result
