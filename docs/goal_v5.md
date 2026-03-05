**v5 설계문서 (멀티 문서 대응 아키텍처 — 전략 패턴 기반 룰 엔진)** 내용을 정리

---

# 설계문서 — V5 멀티 문서 대응 아키텍처

---

## 0. 범위 (Scope)

| 항목        | 내용                                      |
| --------- | --------------------------------------- |
| **목표**    | 민법 등 일반 법령 문서를 추가로 지원할 수 있는 멀티 문서 아키텍처 구축 |
| **대상 버전** | v5                                      |
| **핵심 변화** | 해양규칙 전용 `rule_marine_regulation.py` → 전략 패턴 기반 룰 엔진 분리 |
| **기반**    | V3 Canonical Schema 유지, V4 서버 구조 유지 |
| **신규 문서 유형** | 민법 등 일반 법령 (`제 N조` 형식) 지원 |

---

# 1. 전체 아키텍처 개편 방향

## 1.1 기존 구조 (V4)

```
PDF 선택 → Raw 추출 → map_to_canonical(rule_marine_regulation)
                        ↓
                    Canonical JSON
                        ↓
                    Chunk → 임베딩 → RAG
```

- `rule_marine_regulation.py`의 `map_to_canonical()`이 단일 진입점
- `rules.py`의 조(Article) 패턴: `^(\d{2,})\.` (해양규칙 "101.", "202." 형식만 지원)
- 민법 "제 1조", "제 274조" 형식 미지원

---

## 1.2 V5 구조

```
PDF 선택 + 문서 타입 선택
        ↓
Raw 추출 (extract_pdf_raw.py)
        ↓
Mapper Factory → doc_type에 따라 적절한 Mapper 반환
        ↓
BaseStructureMapper 구현체
  ├─ MarineStructureMapper (해양규칙: 101. 형식)
  └─ StatuteStructureMapper (민법 등: 제 N조 형식)
        ↓
Canonical JSON (기존 스키마 유지)
        ↓
Chunk → 임베딩 → RAG
```

핵심 목표:

> 문서 유형별 파싱 로직을 전략 패턴으로 분리하여, 새 문서 타입 추가 시 기존 코드 수정 없이 확장 가능하게 한다.

---

# 2. 단계별 개발 계획

---

## 2-1. 1단계 — BaseStructureMapper 인터페이스 정의

### 2-1-1. 목적

* 모든 문서 파서의 부모가 될 추상 베이스 클래스 정의
* Raw JSONL → Canonical JSON 변환 공통 인터페이스 확립
* 장/절/항/호/목 등 공통 정규식은 베이스에서 처리

### 2-1-2. 신규 모듈

| 파일 | 역할 |
| --- | --- |
| `src/core/base_mapper.py` | `BaseStructureMapper` 추상 클래스 정의 |

### 2-1-3. 설계 사항

* **공통 패턴**: 편(part), 장(chapter), 절(section), 항/호/목(paragraph) — `rules.py` 공유 또는 베이스에서 처리
* **추상 메서드**: 조(Article) 번호 추출 로직 `_extract_article_no()` — 문서별로 다르므로 자식 클래스에서 구현
* **공통 인터페이스**: `map_to_canonical(raw_blocks, source_meta, ...) -> list[CanonicalRecord]`
* **안전장치**: `check_compatibility(raw_blocks, max_pages=5) -> tuple[bool, int]` — 문서 앞부분(기본 5페이지) Raw 블록에서 매퍼 핵심 패턴(조/항 번호) 발견 여부와 발견 개수 반환

---

## 2-2. 2단계 — 문서별 Mapper 분리

### 2-2-1. MarineStructureMapper (해양규칙)

* **기반**: 기존 `rule_marine_regulation.py`를 `BaseStructureMapper` 상속 구조로 리팩토링
* **조(Article) 패턴**: `^(\d{2,})\.` (101., 202. 형식)
* **출처**: `rule_marine_regulation.py` → `marine_mapper.py` 또는 동일 파일 내 클래스화

### 2-2-2. StatuteStructureMapper (민법 등 일반 법령)

* **신규 생성**: `src/core/statute_mapper.py` (또는 `rule_statute.py`)
* **조(Article) 패턴**: `^제\s*\d+\s*조` (제 1조, 제 274조 형식)
* **편/장/절/항/호/목**: 기존 `rules.py` 패턴과 호환 (동일 구조)

---

## 2-3. 3단계 — Mapper Factory 도입

### 2-3-1. 목적

* DB 생성 탭에서 선택한 문서 타입에 따라 적절한 Mapper 인스턴스 자동 반환
* 파싱 엔진 교체 시 호출부 수정 최소화

### 2-3-2. 신규 모듈

| 파일 | 역할 |
| --- | --- |
| `src/core/mapper_factory.py` | `get_mapper(doc_type: str) -> BaseStructureMapper` 구현 |

### 2-3-3. doc_type 매핑

| doc_type | Mapper |
| --- | --- |
| `marine` / `regulation` | MarineStructureMapper |
| `statute` / `law` | StatuteStructureMapper |

---

## 2-4. 4단계 — rules.py 및 line_rebuild.py 유연화

### 2-4-1. rules.py

* **민법 조문 패턴 추가**: `match_article_statute()` 또는 `classify_line(doc_type)` 오버로드
* **상수화**: `RE_ARTICLE_MARINE`, `RE_ARTICLE_STATUTE` 등 패턴 분리

### 2-4-2. line_rebuild.py

* **현재**: `_RE_NEW_SECTION`에 `제 N 조` 패턴 없음 → 민법 "제 1조"가 문단 구분으로 인식되지 않음
* **변경**: Mapper에서 주입받거나, 공통 패턴 리스트(`RE_NEW_SECTION_EXTRA`)를 확장하여 "제 N조" 추가
* **목적**: 민법에서 문단 병합 시 조문 경계가 깨지지 않도록 함

---

## 2-5. 5단계 — DB 생성 탭 UI 연동

### 2-5-1. 변경 사항

* **1. Import** 그룹에 **문서 타입** 선택 콤보박스 추가
  * 옵션: `해양규칙(marine)` / `법령(statute)` 등
* **3. Canonical 변환** 실행 시 `doc_type`을 Mapper Factory에 전달
* 기존 `map_to_canonical(raw_blocks, source_meta)` 호출을 `get_mapper(doc_type).map_to_canonical(...)`로 변경

---

## 2-6. 6단계 — 매퍼 호환성 검사 안전장치

### 2-6-1. 목적

문서 타입과 실제 문서 형식이 불일치할 경우(예: 법령 선택 후 해양규칙 PDF 사용) 잘못된 Canonical/Chunk 생성·임베딩을 방지한다.

### 2-6-2. check_compatibility 메서드

* **위치**: `BaseStructureMapper`에 추가
* **시그니처**: `check_compatibility(raw_blocks: list[dict], max_pages: int = 5) -> tuple[bool, int]`
* **동작**: 문서 앞부분 `max_pages` 페이지에 해당하는 Raw 블록만 대상으로, 해당 매퍼의 핵심 패턴(조/항 번호)이 발견되는지 검사
* **반환**: `(호환 여부, 발견된 패턴 수)` — 1개 이상 발견 시 `(True, n)`, 0개면 `(False, 0)`
* **구현**: 각 Mapper가 `_extract_article_no` 또는 동일 패턴 로직으로 블록 텍스트 스캔

### 2-6-3. Dry-run 프로세스

* **위치**: `tab_db_create.py`
* **시점**: Chunk 생성 또는 임베딩 실행 직전
* **절차**:
  1. 현재 `doc_type`에 해당하는 Mapper 획득
  2. `raw_blocks`(앞 5페이지 이내)로 `check_compatibility` 호출
  3. 결과가 `(False, 0)`이면 경고 팝업 표시 후 사용자 선택 대기

### 2-6-4. 경고 팝업

* **조건**: `check_compatibility` 반환값이 `(False, 0)`일 때
* **위젯**: `QMessageBox`
* **제목/메시지**: **"매퍼 불일치"** — 선택한 문서 타입과 실제 문서 형식이 맞지 않을 수 있다는 경고
* **버튼**: `[중단]` / `[강제 진행]`
  * **중단**: 해당 단계(Chunk 생성 또는 임베딩) 취소
  * **강제 진행**: 사용자 확인 후 그대로 진행

### 2-6-5. 로그 안내

* **대상**: 애플리케이션 로그 (tab_server_service 로그 패널과 연동된 공통 로거, 또는 Admin UI 공통 로그)
* **기록 내용**:
  * 검사 시점, `doc_type`, 호환 여부(성공/실패)
  * 발견된 패턴 수
  * 예: `[INFO] 매퍼 호환성 검사: marine, 호환됨, 패턴 12건 발견` / `[WARN] 매퍼 호환성 검사: statute, 불일치, 패턴 0건`

---

# 3. 모듈 구조 요약

## 3-1. 신규/변경 파일

```
src/core/
├── base_mapper.py          # 신규: BaseStructureMapper (map_to_canonical, check_compatibility)
├── marine_mapper.py        # 신규 또는 rule_marine_regulation.py 리팩토링
├── statute_mapper.py       # 신규: StatuteStructureMapper (민법용)
├── mapper_factory.py       # 신규: doc_type → Mapper 인스턴스
├── rules.py                # 수정: 조문 패턴 확장 (민법 "제 N조")
└── line_rebuild.py         # 수정: _RE_NEW_SECTION에 "제 N조" 패턴 추가

src/ui/tabs/
└── tab_db_create.py        # 수정: doc_type 선택 UI, mapper_factory 연동
```

---

# 4. 작업 체크리스트 (우선순위)

| 우선순위 | 작업명 | 내용 | 관련 파일 |
| --- | --- | --- | --- |
| **P0** | Interface 정의 | `BaseStructureMapper` 클래스 설계 | `base_mapper.py` |
| **P0** | 민법 조문 패턴 | `제 N조` 인식 정규식 추가 | `rules.py` |
| **P0** | line_rebuild 확장 | `제 N조`를 새 섹션으로 인식 | `line_rebuild.py` |
| **P1** | Marine Mapper 클래스화 | 기존 `map_to_canonical` → `MarineStructureMapper` | `rule_marine_regulation.py` / `marine_mapper.py` |
| **P1** | Statute Mapper 신규 | 민법용 `StatuteStructureMapper` 구현 | `statute_mapper.py` |
| **P1** | Mapper Factory | `doc_type` → Mapper 반환 | `mapper_factory.py` |
| **P2** | UI 연동 | DB 생성 탭에 `doc_type` 선택 추가 | `tab_db_create.py` |
| **P2** | 안전장치 | check_compatibility, Dry-run, 경고 팝업, 로그 | `base_mapper.py`, `tab_db_create.py` |

---

