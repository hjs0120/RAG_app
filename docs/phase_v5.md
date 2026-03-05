# RAG_app V5 — 멀티 문서 대응 아키텍처 단계별 개발 계획

## 개요

- **기반 문서**: `goal_v5.md`
- **목표**: 민법 등 일반 법령 문서를 추가 지원할 수 있는 전략 패턴 기반 룰 엔진 구축
- **핵심 방향**: BaseStructureMapper 추상화 → Marine/Statute Mapper 분리 → Mapper Factory → DB 생성 탭 doc_type 연동

---

## UI 프레임워크

- **PySide6** (Qt for Python 6) 기반 — V4 유지
- **탭 구조**: [서버 서비스] → [사용] → [DB 생성] (변경 없음)
- **DB 생성 탭**: 1. Import 그룹에 **문서 타입** 선택 콤보박스 추가 예정

---

## 테스트 데이터

- **해양규칙**: `data/이동식 해양구조물 규칙_2024-7-92.pdf` (기존)
- **민법(법령)**: `data/` 내 민법 PDF (추가 테스트용)
- **기존 인덱스**: `output/rules.index`, `output/rules_meta.jsonl`

---

## Python 가상환경

- **권장 환경**: Conda 가상환경 `PySide6` (V4와 동일)
- **V5 추가 의존성**: 없음 (기존 패키지만 사용)

### V5 핵심 의존성 (변경 없음)

- **PySide6** — Admin UI
- **PyMuPDF** — PDF 추출
- **faiss** — 벡터 검색
- **sentence-transformers** — BGE 임베딩

---

## Phase 진도 요약

| Phase | 내용 | 완료 |
|-------|------|:----:|
| 1 | BaseStructureMapper 인터페이스 정의 (base_mapper.py) | [x] |
| 2 | rules.py 민법 조문 패턴 + line_rebuild 유연화 | [x] |
| 3 | MarineStructureMapper 클래스화 (기존 rule_marine_regulation 리팩토링) | [x] |
| 4 | StatuteStructureMapper 신규 + mapper_factory | [x] |
| 5 | DB 생성 탭 doc_type 선택 UI, Mapper 연동, 매퍼 호환성 검사 안전장치 | [x] |
| — | **구조 재구성 지시** (Phase 5와 7 사이) | — |
| 6 | 구조 재구성 — 매퍼 적용 시점을 PDF→Raw로 전진 | [ ] |
| 7 | V5 통합 검증 및 문서화 | [ ] |

각 Phase의 **진도 체크** 항목을 검증 후 `[ ]` → `[x]`로 바꾸고, 위 표의 완료도 필요 시 갱신한다.

**각 Phase 완료 시** 해당 Phase 끝의 **커밋 메시지**를 참고하여 커밋을 정리한다.

---

## Phase 1: BaseStructureMapper 인터페이스 정의

### 목표

모든 문서 파서의 부모가 될 추상 베이스 클래스 `BaseStructureMapper`를 정의한다. Raw JSONL → Canonical JSON 변환 공통 인터페이스를 확립한다.

### 작업 내용

1. **`src/core/base_mapper.py` 신규 생성**

   - `BaseStructureMapper` 추상 클래스(ABC) 정의
   - 공통 인터페이스: `map_to_canonical(raw_blocks, source_meta, *, doc_type, language) -> list[CanonicalRecord]`
   - 추상 메서드: `_extract_article_no(text: str) -> RuleMatch | None` — 조(Article) 번호 추출 (문서별로 다름)
   - **안전장치**: `check_compatibility(raw_blocks, max_pages=5) -> tuple[bool, int]` — 앞부분(기본 5페이지) Raw 블록에서 매퍼 핵심 패턴(조/항) 발견 여부와 개수 반환. `_extract_article_no`를 블록 텍스트에 적용하여 카운트
   - 공통 로직: 편(part), 장(chapter), 절(section), 항/호/목(paragraph) 처리 — `rules.py`의 `classify_line` 또는 공통 패턴 활용
   - 스택 기반 structure 생성, `_rule_match_to_label`, `_build_structure`, `_make_record` 등 공통 헬퍼 (기존 `rule_marine_regulation.py` 로직 참고)

2. **CanonicalRecord 연동**

   - `canonical_schema.CanonicalRecord`, `CanonicalSource`, `CanonicalLocation`, `CanonicalStructureItem`, `CanonicalContent` 임포트
   - 반환형: `list[CanonicalRecord]`

3. **하위 호환 유지**

   - Phase 1에서는 `rule_marine_regulation.map_to_canonical` 그대로 사용 (호출부 변경 없음)
   - `base_mapper.py`는 인터페이스만 정의하고, Phase 3에서 Marine Mapper가 상속받도록 설계

### Phase 1에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `src/core/base_mapper.py` (신규) | BaseStructureMapper 추상 클래스 |
| `src/core/canonical_schema.py` | CanonicalRecord 등 (참조) |
| `src/core/rules.py` | RuleMatch, classify_line (참조) |

### 수동 검증 방법

1. `base_mapper.py` 임포트 시 문법 에러 없음 확인
2. `BaseStructureMapper`를 상속한 더미 클래스 작성 후 `map_to_canonical` 시그니처 호출 가능 여부 확인
3. 기존 `rule_marine_regulation.map_to_canonical` 호출 흐름 정상 동작 (회귀 없음)

### 진도 체크

- [x] `src/core/base_mapper.py` 생성
- [x] `BaseStructureMapper` 추상 클래스 및 `map_to_canonical` 인터페이스 정의
- [x] 추상 메서드 `_extract_article_no` 선언
- [x] `check_compatibility(raw_blocks, max_pages=5) -> tuple[bool, int]` 메서드 정의
- [x] 공통 structure 스택 로직 기본 구현 (자식에서 오버라이드 가능하도록)
- [x] 기존 파이프라인 동작 유지
- [x] 수동 검증 완료

### Phase 1 완료 시 커밋

```
feat(core): Phase 1 — BaseStructureMapper 인터페이스 정의

- base_mapper.py 신규
- Raw → Canonical 변환 공통 인터페이스
```

---

## Phase 2: rules.py 민법 조문 패턴 + line_rebuild 유연화

### 목표

민법 등 일반 법령의 "제 N조" 형식을 인식할 수 있도록 `rules.py`를 확장한다. `line_rebuild.py`의 `_RE_NEW_SECTION`에 "제 N조" 패턴을 추가하여 문단 병합 시 조문 경계가 깨지지 않도록 한다.

### 작업 내용

1. **`src/core/rules.py` 수정**

   - **민법 조문 패턴 추가**: `match_article_statute(line: str) -> RuleMatch | None`
     - 정규식: `^제\s*\d+\s*조` (제 1조, 제 274조 등)
     - `RuleMatch(kind="article", value=조번호, ...)` 반환
   - **상수화 (선택)**: `RE_ARTICLE_MARINE`, `RE_ARTICLE_STATUTE` 등 패턴 분리
   - **`classify_line` 확장**: `classify_line(line, doc_type="marine")` — doc_type이 `statute`/`law`일 때 `match_article_statute` 우선 적용
     - 또는 `classify_line`은 기존 유지하고, `classify_line_for_statute` 별도 함수 추가 후 Mapper에서 선택 호출

2. **`src/core/line_rebuild.py` 수정**

   - `_RE_NEW_SECTION` 정규식에 "제 N조" 패턴 추가
   - 현재: `^(?:\d+\s*편|제\s*\d+\s*[장절]|\d{2,}\.\s|...)`
   - 변경: `제\s*\d+\s*조` 패턴을 OR 조건으로 추가
   - 목적: 민법 "제 1조"가 문단 구분으로 인식되어 잘못된 병합 방지

3. **기존 동작 유지**

   - 해양규칙(101. 형식) 문서의 Raw 추출·line_rebuild 결과 변경 없어야 함
   - 기존 테스트 또는 수동 검증으로 회귀 확인

### Phase 2에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `src/core/rules.py` | match_article_statute, classify_line 확장 |
| `src/core/line_rebuild.py` | _RE_NEW_SECTION에 제 N조 패턴 추가 |

### 수동 검증 방법

1. `match_article_statute("제 1조 법원")` → RuleMatch 반환 확인
2. `match_article_statute("제 274조")` → RuleMatch 반환 확인
3. `match_article_statute("101. 적용")` → None (해양 규칙 형식은 statute에서 미인식)
4. 민법 PDF로 Raw 추출 → "제 1조", "제 2조" 등이 별도 블록으로 분리되는지 확인
5. 해양규칙 PDF로 Raw 추출 → 기존과 동일 결과인지 확인 (회귀 테스트)

### 진도 체크

- [x] `rules.py`: `match_article_statute` 함수 추가
- [x] `rules.py`: doc_type 또는 별도 classify 함수로 statute 조문 인식
- [x] `line_rebuild.py`: `_RE_NEW_SECTION`에 "제 N조" 패턴 추가
- [x] 민법 PDF Raw 추출 시 조문 경계 정상 분리
- [x] 해양규칙 PDF Raw 추출 회귀 없음
- [x] 수동 검증 완료

### Phase 2 완료 시 커밋

```
feat(core): Phase 2 — rules.py 민법 조문 패턴 + line_rebuild 유연화

- rules: match_article_statute, 제 N조 패턴
- line_rebuild: _RE_NEW_SECTION에 제 N조 추가
```

---

## Phase 3: MarineStructureMapper 클래스화

### 목표

기존 `rule_marine_regulation.py`의 `map_to_canonical` 로직을 `BaseStructureMapper`를 상속한 `MarineStructureMapper`로 리팩토링한다. 기존 `map_to_canonical` 함수는 하위 호환을 위해 `MarineStructureMapper().map_to_canonical(...)`을 래핑하여 유지할 수 있다.

### 작업 내용

1. **`src/core/marine_mapper.py` 신규 생성** (또는 `rule_marine_regulation.py` 내부에 클래스 추가)

   - `MarineStructureMapper(BaseStructureMapper)` 클래스 구현
   - `_extract_article_no(text)`: `^(\d{2,})\.` 패턴으로 조문 인식 (기존 `match_article` 활용)
   - `map_to_canonical`: 부모 공통 로직 + Marine 전용 classify 호출

2. **`src/core/rule_marine_regulation.py` 수정**

   - `map_to_canonical`를 `MarineStructureMapper().map_to_canonical(...)` 호출로 위임 (하위 호환)
   - 또는 `rule_marine_regulation.py`를 `marine_mapper.py`로 통합·이관 후 기존 모듈에서 re-export

3. **호출부 변경 없음**

   - `tab_db_create.py` 등에서 `map_to_canonical` 호출 시 Phase 5 이전까지는 Marine Mapper가 사용됨을 보장

### Phase 3에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `src/core/marine_mapper.py` (신규) 또는 `rule_marine_regulation.py` | MarineStructureMapper 클래스 |
| `src/core/base_mapper.py` | BaseStructureMapper 상속 |
| `src/core/rule_marine_regulation.py` | map_to_canonical 래퍼 유지 |

### 수동 검증 방법

1. 해양규칙 PDF: Raw 추출 → Canonical 변환 실행
2. Canonical 결과가 Phase 3 이전과 동일한 structure_path, content를 갖는지 확인
3. Chunk 생성 → 임베딩 → RAG 질의 응답 정상 동작 확인
4. `rule_marine_regulation.map_to_canonical` 직접 호출 시 동일 결과 반환 확인

### 진도 체크

- [x] `MarineStructureMapper` 클래스 구현
- [x] `_extract_article_no`: 101., 202. 형식 인식
- [x] `map_to_canonical` 결과 기존과 동일
- [x] `rule_marine_regulation.map_to_canonical` 하위 호환 유지
- [x] 수동 검증 완료

### Phase 3 완료 시 커밋

```
refactor(core): Phase 3 — MarineStructureMapper 클래스화

- marine_mapper.py 또는 rule_marine_regulation 리팩토링
- BaseStructureMapper 상속
```

---

## Phase 4: StatuteStructureMapper 신규 + mapper_factory

### 목표

민법 등 일반 법령용 `StatuteStructureMapper`를 신규 생성한다. `mapper_factory`를 도입하여 `doc_type`에 따라 적절한 Mapper 인스턴스를 반환하도록 한다.

### 작업 내용

1. **`src/core/statute_mapper.py` 신규 생성**

   - `StatuteStructureMapper(BaseStructureMapper)` 클래스 구현
   - `_extract_article_no(text)`: `^제\s*\d+\s*조` 패턴 (Phase 2의 `match_article_statute` 활용)
   - `map_to_canonical`: 부모 공통 로직 + Statute 전용 classify 호출
   - 편/장/절/항/호/목: 기존 `rules.py` 패턴 공유 (동일 구조)

2. **`src/core/mapper_factory.py` 신규 생성**

   - `get_mapper(doc_type: str) -> BaseStructureMapper` 함수 구현
   - `doc_type` 매핑:
     - `marine`, `regulation` → `MarineStructureMapper`
     - `statute`, `law` → `StatuteStructureMapper`
   - 알 수 없는 `doc_type` 시 기본값 `MarineStructureMapper` 또는 에러 처리

3. **테스트**

   - 민법 PDF: Raw 추출 → `get_mapper("statute").map_to_canonical(...)` 호출 → structure에 "제 1조", "제 2조" 등 포함 여부 확인

### Phase 4에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `src/core/statute_mapper.py` (신규) | StatuteStructureMapper |
| `src/core/mapper_factory.py` (신규) | get_mapper(doc_type) |
| `src/core/base_mapper.py` | 상속 참조 |
| `src/core/rules.py` | match_article_statute 참조 |

### 수동 검증 방법

1. `get_mapper("marine")` → MarineStructureMapper 인스턴스 반환 확인
2. `get_mapper("statute")` → StatuteStructureMapper 인스턴스 반환 확인
3. 민법 PDF Raw 블록으로 `get_mapper("statute").map_to_canonical(...)` 호출
4. Canonical 레코드의 structure에 "제 1조", "제 274조" 등이 정상 반영되는지 확인
5. 해양규칙 PDF로 `get_mapper("marine").map_to_canonical(...)` 호출 → 기존 결과와 동일한지 확인

### 진도 체크

- [x] `StatuteStructureMapper` 클래스 구현
- [x] `_extract_article_no`: 제 N조 형식 인식
- [x] `mapper_factory.get_mapper(doc_type)` 구현
- [x] `doc_type` marine/statute 매핑
- [x] 민법 Canonical 변환 결과 검증
- [x] 수동 검증 완료

### Phase 4 완료 시 커밋

```
feat(core): Phase 4 — StatuteStructureMapper + mapper_factory

- statute_mapper.py, mapper_factory.py 신규
- doc_type별 Mapper 선택
```

---

## Phase 5: DB 생성 탭 doc_type 선택 UI 및 Mapper 연동

### 목표

DB 생성 탭 1. Import 그룹에 문서 타입 선택 콤보박스를 추가하고, 3. Canonical 변환 실행 시 선택한 `doc_type`으로 Mapper Factory를 통해 적절한 Mapper를 사용하도록 연동한다.

### 작업 내용

1. **`src/ui/tabs/tab_db_create.py` 수정**

   - **1. Import** 그룹에 **문서 타입** 선택 콤보박스 추가
     - 옵션: `해양규칙 (marine)`, `법령 (statute)` (표시명/값 쌍)
     - 기본값: `해양규칙 (marine)`
     - `self._combo_doc_type` 등 위젯 생성
   - 상태 저장: `self._state["doc_type"] = combo 현재값`

2. **3. Canonical 변환 로직 변경**

   - 기존: `from src.core.rule_marine_regulation import map_to_canonical` 후 `map_to_canonical(raw_blocks, source_meta)` 직접 호출
   - 변경: `from src.core.mapper_factory import get_mapper` 후 `mapper = get_mapper(self._state.get("doc_type", "marine"))`, `canonical = mapper.map_to_canonical(raw_blocks, source_meta, ...)`
   - `doc_type`이 UI 콤보 값과 일치하도록 매핑 (marine, statute)

3. **라벨/툴팁**

   - 문서 타입 콤보에 툴팁: "해양규칙: 101. 형식 / 법령: 제 N조 형식"

4. **검수 탭 연동 (필요 시)**

   - 검수 시에도 `doc_type`이 전달되어 Canonical 구조가 올바르게 표시되는지 확인

5. **매퍼 호환성 검사 안전장치 (Dry-run)**

   - **시점**: Chunk 생성 또는 임베딩 실행 직전
   - **절차**:
     1. `get_mapper(doc_type)`으로 현재 Mapper 획득
     2. `raw_blocks` 중 앞 5페이지 이내 블록만 사용해 `check_compatibility(raw_blocks, max_pages=5)` 호출
     3. 반환값 `(compatible, count)`가 `(False, 0)`이면 경고 팝업 표시
   - **경고 팝업 (QMessageBox)**:
     - 제목: `매퍼 불일치`
     - 메시지: 선택한 문서 타입과 실제 문서 형식이 맞지 않을 수 있다는 경고
     - 버튼: `[중단]` (취소) / `[강제 진행]`
   - **로그 기록**: 검사 결과(호환 여부, 발견 패턴 수)를 애플리케이션 로그에 기록. tab_server_service 로그 패널과 연동된 공통 로거 사용 시 해당 로그로 전달
     - 예: `[INFO] 매퍼 호환성 검사: marine, 호환됨, 패턴 12건 발견`
     - 예: `[WARN] 매퍼 호환성 검사: statute, 불일치, 패턴 0건`

### Phase 5에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `src/ui/tabs/tab_db_create.py` | doc_type 콤보, get_mapper 연동, check_compatibility Dry-run, 경고 팝업, 로그 |
| `src/core/mapper_factory.py` | get_mapper (참조) |

### 수동 검증 방법

1. Admin UI 실행 → [DB 생성] 탭 이동
2. 1. Import에서 문서 타입 "해양규칙" 선택 후 PDF 선택
3. Raw 추출 → Canonical 변환 실행 → structure_path에 "제 101조" 등 표시 확인
4. 문서 타입 "법령" 선택 후 민법 PDF 선택
5. Raw 추출 → Canonical 변환 실행 → structure_path에 "제 1조", "제 2조" 등 표시 확인
6. Chunk 생성 → 임베딩까지 전체 파이프라인 동작 확인 (해양규칙, 법령 각각)
7. **안전장치 검증**: 법령 선택 후 해양규칙 PDF 사용 시 매퍼 불일치 경고 팝업 표시 → [중단] 시 취소, [강제 진행] 시 진행 확인
8. 호환 시 로그에 "호환됨, 패턴 N건 발견" 기록 확인

### 진도 체크

- [x] 1. Import 그룹에 문서 타입 콤보박스 추가
- [x] doc_type 상태 저장
- [x] 3. Canonical 변환 시 get_mapper(doc_type) 연동
- [x] 해양규칙/법령 전환 시 Canonical 결과 변경 확인
- [x] 전체 파이프라인(Chunk, 임베딩) 정상 동작
- [x] Chunk/임베딩 전 check_compatibility Dry-run 수행
- [x] 매퍼 불일치 시 QMessageBox 경고, [중단]/[강제 진행] 동작
- [x] 검사 결과 로그 기록 (호환 여부, 패턴 수)
- [x] 수동 검증 완료

### Phase 5 완료 시 커밋

```
feat(ui): Phase 5 — DB 생성 탭 doc_type 선택, Mapper 연동, 매퍼 호환성 검사 안전장치

- tab_db_create: 문서 타입 콤보, mapper_factory 연동
- check_compatibility Dry-run, 매퍼 불일치 경고 팝업, 로그 기록
```

---

## 구조 재구성 지시 — 매퍼 적용 시점 변경

> Phase 5 완료 후, Phase 6(구조 재구성) 수행 전 참고. goal_v5.md §2-8 및 §1.3과 연동.

현재 매퍼가 Raw → Canonical 단계에서만 작동한다. 이를 **PDF → Raw (extract_pdf_raw) 단계로 전진 배치**하여 재구성한다.

### 1. 매퍼 주입 (Dependency Injection)

* **대상**: `extract_pdf_raw.py`
* **지시**: 함수들이 고정된 `_RE_NEW_SECTION`을 사용하는 대신, MapperFactory로부터 받은 매퍼의 규칙을 인자로 전달받아 사용하도록 수정한다.

### 2. line_rebuild.py 유연화

* **대상**: `line_rebuild.py`
* **지시**: 섹션을 나누는 기준(`_RE_NEW_SECTION`)을 매퍼가 제공하는 정규식 패턴으로 동적 교체한다.
* **결과**: 민법은 제 N조를 기준으로, 해양규칙은 101.을 기준으로 정확한 Raw 블록을 생성할 수 있어야 한다.

### 3. Raw → Canonical 단계 단순화

* **지시**: 이미 매퍼의 규칙대로 정확하게 쪼개진 Raw 블록이 생성되었으므로, 변환 단계에서는 복잡한 패턴 매칭 없이 Raw의 정보를 Canonical Schema로 옮기기만 한다.

### 4. 적합성 검사 위치 조정

* **시점**: `check_compatibility`는 **추출 시작 직전**에 수행한다.
* **지시**: 검사를 통과한 매퍼의 규칙이 `extract_pdf_raw`에 주입되어야 한다.
* **절차**:
  1. 5페이지만 선행 추출 (Dry-run)
  2. `check_compatibility` 실행
  3. 통과 시 → 매퍼 규칙을 `extract_pdf_raw`에 주입하여 전체 추출
  4. 실패 시 → 추출 자체를 수행하지 않음

---

## Phase 6: 구조 재구성 — 매퍼 적용 시점을 PDF→Raw로 전진

### 목표

매퍼를 Raw → Canonical에서 PDF → Raw (extract_pdf_raw) 단계로 전진 배치한다.

### 작업 내용

위 **구조 재구성 지시**에 따른 구현. 상세는 goal_v5.md §2-8 참조.

### Phase 6에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `src/core/extract_pdf_raw.py` | 매퍼 규칙(섹션 패턴) 주입, max_pages 지원 |
| `src/core/line_rebuild.py` | 매퍼 제공 정규식으로 동적 교체 |
| `src/core/base_mapper.py` | get_section_pattern() 등 매퍼 인터페이스 확장 |
| `src/ui/tabs/tab_db_create.py` | 추출 직전 Dry-run, check_compatibility, 매퍼 주입 |

### 수동 검증 방법

1. 민법 PDF + 해양규칙 선택 → 추출 시 매퍼 불일치 경고, 추출 차단 확인
2. 해양규칙 PDF + 해양규칙 선택 → 정상 추출 (101. 기준 블록)
3. 민법 PDF + 법령 선택 → 정상 추출 (제 N조 기준 블록)
4. Raw → Canonical 변환 결과 정확성 확인

### 진도 체크

- [ ] extract_pdf_raw: 매퍼 규칙 주입, max_pages 파라미터
- [ ] BaseStructureMapper: get_section_pattern() 추가
- [ ] line_rebuild: 동적 패턴 사용
- [ ] tab_db_create: 추출 직전 Dry-run, 검사 통과 시 매퍼 주입
- [ ] Raw → Canonical 단순화
- [ ] 수동 검증 완료

### Phase 6 완료 시 커밋

```
refactor(core): Phase 6 — 매퍼 적용 시점을 PDF→Raw로 전진

- extract_pdf_raw: 매퍼 주입, max_pages
- line_rebuild: 동적 섹션 패턴
- check_compatibility: 추출 직전 Dry-run
```

---

## Phase 7: V5 통합 검증 및 문서화

### 목표

V5 완료 기준(goal_v5.md)을 충족하는지 검증하고, 문서를 정리한다.

### V5 완료 기준

- BaseStructureMapper, MarineStructureMapper, StatuteStructureMapper, mapper_factory 정상 동작
- rules.py에 민법 조문 패턴 추가, line_rebuild에 제 N조 패턴 반영
- DB 생성 탭에서 문서 타입(해양규칙/법령) 선택 가능
- **추출 직전** 매퍼 호환성 검사(Dry-run), 불일치 시 추출 차단
- 해양규칙 PDF → Canonical 변환 결과 기존과 동일
- 민법 PDF → Canonical 변환 시 "제 N조" structure_path 정상 표시
- 기존 RAG, Web Client, 서버 서비스 기능 유지

### 작업 내용

1. **통합 검증**

   - 위 완료 기준 항목 수동 테스트
   - 해양규칙/민법 각각 전체 파이프라인(Raw → Canonical → Chunk → 임베딩 → RAG) 검증
   - 기존 [사용 탭], [서버 서비스 탭], Web Client 동작 회귀 확인

2. **문서 작성**

   - `readme.md` 갱신 (V5 멀티 문서 지원, doc_type 선택 방법 반영)
   - `phase_v5.md` 진도 반영
   - `project_overview.md`에 V5 섹션 추가 (필요 시)

3. **V5 디렉터리 구조 확정**

   ```
   src/core/
   ├── base_mapper.py       (V5 신규)
   ├── marine_mapper.py     (V5 신규 또는 rule_marine_regulation 리팩토링)
   ├── statute_mapper.py    (V5 신규)
   ├── mapper_factory.py    (V5 신규)
   ├── rule_marine_regulation.py  (래퍼 또는 marine_mapper로 통합)
   ├── rules.py             (V5 수정)
   └── line_rebuild.py      (V5 수정)
   ```

### Phase 7에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `readme.md` | V5 멀티 문서 지원 반영 |
| `phase_v5.md` | 진도 반영 |
| `docs/project_overview.md` | V5 섹션 추가 (필요 시) |

### 수동 검증 방법

1. 해양규칙 PDF로 doc_type "해양규칙" 선택 → 전체 파이프라인 실행 → RAG 질의 응답 확인
2. 민법 PDF로 doc_type "법령" 선택 → 전체 파이프라인 실행 → RAG 질의 응답 및 출처(제 N조) 확인
3. 민법 PDF + 해양규칙 선택 → 추출 차단 확인
4. 서버 서비스, Web Client, 기존 탭 기능 회귀 없음 확인

### 진도 체크

- [ ] BaseStructureMapper, Marine/Statute Mapper, mapper_factory 동작 확인
- [ ] 매퍼 적용 시점 전진(PDF→Raw) 검증
- [ ] DB 생성 탭 doc_type 선택, 추출 직전 Dry-run 확인
- [ ] 해양규칙/민법 전체 파이프라인 검증
- [ ] 기존 RAG, Web Client, 서버 기능 유지
- [ ] `readme.md` 갱신
- [ ] `phase_v5.md` 진도 반영
- [ ] 수동 검증 완료

### Phase 7 완료 시 커밋

```
docs: Phase 7 — V5 통합 검증 및 문서화

- readme.md: V5 멀티 문서 지원
- phase_v5.md: 진도 반영
```

---

## 토큰 최소화 가이드

| Phase | 집중할 디렉터리/파일 | 참고 문서 |
|-------|----------------------|-----------|
| 1 | `src/core/base_mapper.py`, `rule_marine_regulation.py` | goal_v5.md §2-1 |
| 2 | `src/core/rules.py`, `src/core/line_rebuild.py` | goal_v5.md §2-4 |
| 3 | `src/core/marine_mapper.py`, `rule_marine_regulation.py`, `base_mapper.py` | goal_v5.md §2-2-1 |
| 4 | `src/core/statute_mapper.py`, `mapper_factory.py` | goal_v5.md §2-2-2, §2-3 |
| 5 | `src/ui/tabs/tab_db_create.py`, `mapper_factory.py`, `base_mapper.py` | goal_v5.md §2-5, §2-6 |
| 6 | `extract_pdf_raw.py`, `line_rebuild.py`, `base_mapper.py`, `tab_db_create.py` | goal_v5.md §2-8 |
| 7 | `readme.md`, `phase_v5.md`, `project_overview.md` | goal_v5.md §3, §4 |

매 Phase는 위 표에 해당하는 파일만 열어 작업하면 토큰 사용을 최소화할 수 있다.
