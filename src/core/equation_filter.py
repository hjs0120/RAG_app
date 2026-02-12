"""
수식 구간 제외 — 패턴 없는 들여쓰기 블록(변수 정의 등) 감지. Phase 12.
페이지별 기준 왼쪽 여백(median x0)보다 충분히 오른쪽에서 시작하는 라인을
수식/변수 정의 블록으로 간주해 제외한다.
"""

from __future__ import annotations

from collections import defaultdict


def _reference_left_per_page(lines: list[dict]) -> dict[int, float]:
    """페이지별로 라인 bbox 왼쪽 끝(x0)의 중앙값을 구해, 해당 페이지의 '본문 기준 왼쪽'으로 쓴다."""
    by_page: dict[int, list[float]] = defaultdict(list)
    for line in lines:
        bbox = line.get("bbox")
        page = line.get("page")
        if not bbox or len(bbox) < 4 or page is None:
            continue
        by_page[page].append(bbox[0])
    return {p: (sorted(x0s)[len(x0s) // 2] if x0s else 0.0) for p, x0s in by_page.items()}


def _is_indented_line(
    line: dict,
    reference_left_by_page: dict[int, float],
    indent_threshold_pt: float,
) -> bool:
    """
    해당 라인이 '들여쓰기된' 라인인지 판단.
    bbox 왼쪽 끝(x0)이 해당 페이지 기준 왼쪽보다 indent_threshold_pt 이상 크면 True.
    (변수 정의 목록처럼 본문보다 오른쪽에서 시작하는 블록을 수식 관련으로 간주)
    """
    bbox = line.get("bbox")
    page = line.get("page")
    if not bbox or len(bbox) < 4 or page is None:
        return False
    ref = reference_left_by_page.get(page)
    if ref is None:
        return False
    return float(bbox[0]) > ref + indent_threshold_pt


def apply_equation_filter(
    lines: list[dict],
    *,
    exclude_equation: bool = True,
    indent_threshold_pt: float = 25.0,
) -> list[dict]:
    """
    수식·변수 정의 등 들여쓰기 블록을 제외한다.

    - 패턴이 없는 수식/변수 정의(예: V:, p:, C_s: ...)는 본문보다 오른쪽(들여쓰기)으로
      인쇄되는 경우가 많음. 페이지별 본문 기준 왼쪽(bbox x0 중앙값)보다
      indent_threshold_pt(기본 25pt) 이상 오른쪽에서 시작하는 라인을 제외.
    - exclude_equation False면 필터 미적용.

    Args:
        lines: text, bbox, page, line_no 를 갖는 라인 리스트
        exclude_equation: True면 들여쓰기 블록 제외
        indent_threshold_pt: 기준 왼쪽보다 이 값(pt) 이상 오른쪽이면 들여쓰기로 간주

    Returns:
        필터링된 라인 리스트.
    """
    if not lines or not exclude_equation:
        return list(lines)

    reference_left = _reference_left_per_page(lines)
    out = []
    for line in lines:
        if _is_indented_line(line, reference_left, indent_threshold_pt):
            continue
        out.append(line)
    return out
