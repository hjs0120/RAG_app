"""RAG 답변·질문 정제 프롬프트 템플릿."""

RAG_SYSTEM = """당신은 제공된 문서(CONTEXT)만을 근거로 질문에 답변하는 RAG 어시스턴트입니다.

규칙:
1. 질문이 특정 문장의 존재 여부를 묻는 것이 아니라, 개념 설명, 요약, 정리, 기준, 구성 요소 등을 묻는 경우에는 CONTEXT에 포함된 관련 조항, 항목, 설명을 종합하여 논리적으로 재구성하여 답변하세요.

2. 질문과 동일한 문장이 없더라도, 의미적으로 관련된 정보가 CONTEXT에 존재하면 이를 정리하여 답변하세요.

3. CONTEXT에 일부 관련 정보라도 존재하면 이를 기반으로 최대한 답변을 구성하세요.

4. CONTEXT에는 여러 조항(article), 절(section), 항(paragraph)이 포함될 수 있습니다. 관련된 여러 조항이 있다면 이를 연결하여 하나의 설명으로 정리하세요. 조각을 나열하지 말고, 조항을 종합하여 설명하세요.

5. 단순히 특정 조항의 위치만 언급하지 말고, 해당 조항의 내용을 요약하여 설명하세요.

6. "문서에서 해당 근거를 찾지 못했습니다"는 CONTEXT에 질문과 의미적으로 관련된 정보가 전혀 없을 때만 사용하세요.

7. 답변은 가능하면 구조화하여 작성하세요 (번호 목록, 항목 구분, 단계 구분 등).

8. 답변 말미에 반드시 [출처] 섹션을 포함하세요. 제공된 출처 목록의 형식을 그대로 사용하고 임의로 변경하지 마세요.

9. CONTEXT의 문구를 인용할 때는 해당 출처 번호를 붙이세요 (예: [1])."""

RAG_USER_TEMPLATE = """## 문서 내용 (CONTEXT)

{context}

## 출처 목록 (답변 말미 [출처] 섹션에 이 형식 그대로 사용)

{sources}

## 질문

{question}

---
지시: 위 CONTEXT에 의미적으로 관련된 정보가 있으면 이를 종합하여 구조화된 답변을 작성하세요. 조항 위치만 언급하지 말고 내용을 요약하여 설명하세요. 답변 끝에 [출처] 섹션을 반드시 포함하세요."""

QUESTION_REFINE_SYSTEM = """당신은 사용자 질문을 검색에 적합하게 다듬는 도우미입니다.
질문의 핵심 키워드만 추출하거나, 규격/문서 검색에 맞게 간단히 재작성하세요.
원문 의미를 바꾸지 마세요. 1~2문장으로 출력하세요."""

QUESTION_REFINE_USER = """다음 질문을 문서 검색에 적합하게 다듬어 주세요:

{question}"""


def build_rag_prompt(context: str, sources: list[str], question: str) -> str:
    """
    RAG 답변용 프롬프트 생성.
    sources: ["[1] doc_id=..., page=..., section=..., chunk_id=...", ...]
    """
    sources_text = "\n".join(sources) if sources else "(출처 없음)"
    return RAG_USER_TEMPLATE.format(
        context=context or "(컨텍스트 없음)",
        sources=sources_text,
        question=question,
    )


def build_rag_full_prompt(context: str, sources: list[str], question: str) -> str:
    """Ollama /api/generate용 단일 프롬프트 (system + user 통합)."""
    user_part = build_rag_prompt(context, sources, question)
    return f"{RAG_SYSTEM}\n\n---\n\n{user_part}"


def build_rag_chat_messages(
    context: str, sources: list[str], question: str
) -> list[dict[str, str]]:
    """Ollama /api/chat용 메시지 리스트. instruct 모델 호환."""
    return [
        {"role": "system", "content": RAG_SYSTEM},
        {"role": "user", "content": build_rag_prompt(context, sources, question)},
    ]


def build_question_refine_prompt(question: str) -> str:
    """질문 정제용 프롬프트 (옵션, 기본 OFF)."""
    return f"{QUESTION_REFINE_SYSTEM}\n\n---\n\n{QUESTION_REFINE_USER.format(question=question)}"
