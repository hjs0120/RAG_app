"""Path 태깅 — chapter/section/article/paragraph 상태 머신."""

from __future__ import annotations

from typing import Any

from src.core.rules import RuleMatch, classify_line


def _empty_path() -> dict[str, Any]:
    return {
        "part": None,
        "chapter": None,
        "section": None,
        "article": None,
        "paragraph": None,
    }


def _copy_path(path: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in path.items()}


def parse_lines(lines: list[dict]) -> list[dict]:
    """
    라인 리스트를 순서대로 읽으며 각 라인에 path 메타데이터를 부여한다.

    각 라인은 text, bbox, page, line_no 를 갖는다고 가정한다.
    반환 시 각 라인에 "path" 키가 추가된다: { part, chapter, section, article, paragraph }.

    상태 규칙:
    - part 만나면 → part 갱신, chapter/section/article/paragraph 초기화
    - chapter 만나면 → chapter 갱신, section/article/paragraph 초기화
    - section 만나면 → section 갱신, article/paragraph 초기화
    - article 만나면 → article 갱신, paragraph 초기화
    - paragraph 만나면 → paragraph 갱신
    - 그 외 라인은 현재 path 유지(paragraph만 None일 수 있음)
    """
    result: list[dict] = []
    path = _empty_path()

    for line in lines:
        line_copy = dict(line)
        text = line_copy.get("text", "").strip()

        if not text:
            line_copy["path"] = _copy_path(path)
            result.append(line_copy)
            continue

        matched: RuleMatch | None = classify_line(text)

        if matched:
            if matched.kind == "part":
                path["part"] = matched.value
                path["chapter"] = getattr(matched, "chapter_value", None) or None
                path["section"] = None
                path["article"] = None
                path["paragraph"] = None
            elif matched.kind == "chapter":
                path["chapter"] = matched.value
                path["section"] = None
                path["article"] = None
                path["paragraph"] = None
            elif matched.kind == "section":
                path["section"] = matched.value
                path["article"] = None
                path["paragraph"] = None
            elif matched.kind == "article":
                path["article"] = matched.value
                path["paragraph"] = None
                # section은 "제 N 절" 구조만 사용. 조문 제목("적용", "연차검사" 등)은 section에 넣지 않음
                # 명시적 "제 N 장" 없을 때, 조문 번호(101/302) 앞자리로 chapter 추론
                if path["chapter"] is None and len(matched.value) >= 2:
                    ch_num = matched.value[0] if len(matched.value) <= 3 else matched.value[:2]
                    path["chapter"] = f"제 {ch_num} 장"
            elif matched.kind == "paragraph":
                path["paragraph"] = matched.value

        line_copy["path"] = _copy_path(path)
        result.append(line_copy)

    return result
