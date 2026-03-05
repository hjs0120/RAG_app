"""차례(목차) 구간 탐지 — '차 례' 이후 첫 '제 n 장' 시작점."""

from __future__ import annotations

import re
from typing import Any


# 차례 표제: "차", "례" 사이 공백 허용
_RE_TOC = re.compile(r"차\s*례")
# 본문 장 헤더: 줄 시작에 "제 N 장"
_RE_CHAPTER = re.compile(r"^제\s*\d+\s*장")
# 목차 항목: 줄 끝에 점(.) 2개 이상 + 쪽번호가 있으면 목차 줄로 간주.
# 주의: "제 1장 통칙 31"처럼 본문 쪽번호(공백+숫자만)는 제외 — 과도한 skip 방지.
_RE_TOC_PAGE_NUMBER = re.compile(r"\.{2,}\s*\d+\s*$")


def _is_toc_entry_line(text: str) -> bool:
    """목차 페이지에서 '제 n 장 총칙 ........ 7' 형태(점 2개 이상 + 쪽번호)면 True."""
    return bool(_RE_TOC_PAGE_NUMBER.search(text))


def detect_toc_start(lines: list[dict[str, Any]]) -> tuple[int | None, int | None]:
    """
    라인 리스트에서 '차례' 위치와 본문 시작(첫 '제 n 장') 인덱스를 구한다.

    규칙:
    - `차\\s*례` 매칭 → toc_mode=True (해당 인덱스 기록)
    - toc_mode 상태에서 `^제\\s*\\d+\\s*장` 매칭 시, 해당 줄이 목차 항목(끝에 쪽번호)이면
      건너뛰고, 목차 항목이 아닌 첫 '제 n 장'을 본문 시작으로 사용.

    Args:
        lines: extract 라인 리스트. 각 항목은 "text" 키를 가짐.

    Returns:
        (toc_line_index, body_start_index)
        - toc_line_index: "차 례"가 처음 나오는 라인 인덱스 (없으면 None)
        - body_start_index: "차례" 이후 첫 본문용 "제 n 장" 라인 인덱스 (없으면 None)
    """
    toc_index: int | None = None
    body_start: int | None = None

    for i, ln in enumerate(lines):
        text = (ln.get("text") or "").strip()
        if not text:
            continue

        if toc_index is None and _RE_TOC.search(text):
            toc_index = i

        if toc_index is not None and _RE_CHAPTER.search(text):
            # 목차 안의 "제 n 장 ........ 7" 형태는 건너뛰기 (본문은 7페이지부터 등)
            if _is_toc_entry_line(text):
                continue
            body_start = i
            break

    return (toc_index, body_start)


def apply_toc_filter(
    lines: list[dict[str, Any]], *, after_toc: bool
) -> list[dict[str, Any]]:
    """
    after_toc이 True면 '차례' 이후 첫 '제 n 장'부터만 반환, False면 전체 반환.

    Args:
        lines: 전체 추출 라인 리스트
        after_toc: True면 본문 시작점부터만 반환

    Returns:
        필터링된 라인 리스트 (동일 dict 참조, 복사 아님).
    """
    if not after_toc or not lines:
        return lines
    _, body_start = detect_toc_start(lines)
    if body_start is None:
        return lines
    return lines[body_start:]
