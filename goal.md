---

## 설계문서 v0.1 — PDF 규격문서 텍스트 추출/구조화/JSON Export UI

### 0. 범위(Scope)

* 입력: 규격 PDF(예: **이동식 해양구조물 규칙_2024**) 
* 출력: **JSONL(권장)** 또는 CSV
* 처리 범위: **차례 이후 본문부터 추출**

  * 차례 표시는 “차 례”로 식별 가능 
  * 본문 시작 예: “제 1 장 총칙 / 제 1 절 일반사항 / 101. 적용 …” 
* UI: Python 기반(탭 + 그룹박스)

---

## 1. 목표 출력 데이터 스펙

### 1.1 레코드 단위

* **한 줄(line) = 한 레코드**
* line에는 “현재 문서의 경로(Path)” 메타데이터를 붙임
  (요청하신 Part > Chapter > Section > Article > Paragraph)

### 1.2 이 PDF에 맞춘 Path 매핑(초안)

이 문서는 “Part”라는 영어 표기가 아니라 **장/절/조항 구조**로 보이므로, 우선 다음처럼 매핑하는 게 자연스럽다.

* Part: (일단 비움 또는 “규칙 본문” 같은 고정값)
* Chapter: `제 n 장 …`  (예: 제 1 장 총칙) 
* Section: `제 n 절 …` (예: 제 1 절 일반사항) 
* Article: `101.`, `202.` 같은 조문 번호 
* Paragraph: `1.`, `(1)`, `(가)` 등 항/호/목

> Part가 꼭 필요하면, “권/편/부” 개념이 없는 문서도 있으니 **part=null** 로 두고, 나중에 협의된 메타 모델로 확장하는 걸 추천.

### 1.3 JSONL 출력 예시(형태)

```json
{
  "doc_id": "MOUS_RULE_2024",
  "page": 7,
  "line_no": 14,
  "path": {
    "part": null,
    "chapter": "제 1 장 총칙",
    "section": "제 1 절 일반사항",
    "article": "101",
    "paragraph": "1"
  },
  "text": "1. 이 규칙은 ... 적용한다.",
  "bbox": [x0, y0, x1, y1],
  "source": {"file": "이동식 해양구조물 규칙_2024.pdf"}
}
```

---

## 2. 전체 처리 파이프라인

### 2.1 단계 요약

1. **PDF Import**
2. **페이지별 텍스트 추출(레이아웃 기반)**
3. **라인 재구성(line rebuild)**
4. **목록(차례) 구간 스킵**
5. **정규화(헤더/푸터 제거, 공백 정리 등)**
6. **구조 파싱(Path 태깅: Chapter/Section/Article/Paragraph)**
7. **JSONL/CSV Export**

---

## 3. 핵심 알고리즘 설계

### 3.1 “목록(차례) 이후부터” 시작점 탐지

* 규칙:

  * `차 례` 라인이 나오면 이후 일정 구간은 “목차 영역”으로 간주 
  * 본문 시작은 `제 1 장` 같은 **장 헤더**가 등장하는 첫 지점으로 확정 

**권장 구현**

* 1차: 라인 텍스트에 `차\s*례` 매칭 → toc_mode=True
* toc_mode 상태에서 `^제\s*\d+\s*장` 매칭이 나오면 toc_mode=False, 그 시점부터 export 시작

### 3.2 라인 추출(중요)

목표가 “한 줄씩”이므로, PDF에서 텍스트를 그냥 `extract_text()`로 뽑으면 품질이 흔들릴 수 있음.
**레이아웃 좌표 기반**으로 “같은 y좌표끼리 묶어 라인”을 만드는 방식이 필요.

* 엔진: **PyMuPDF(fitz)** 권장
* 산출: `(text, bbox, page, line_no, font_size(optional))`

### 3.3 Path 태깅(상태 머신)

라인을 위에서 아래로 순서대로 읽으면서 “현재 위치”를 업데이트.

* `chapter`를 만나면 → chapter 갱신, section/article/paragraph 초기화
* `section`을 만나면 → section 갱신, article/paragraph 초기화
* `article(101.)`을 만나면 → article 갱신, paragraph 초기화
* `paragraph(1., (1), (가))`를 만나면 → paragraph 갱신(또는 누적 규칙 적용)

**이 PDF에서 확인되는 패턴**

* Chapter 예: “제 1 장 총칙” 
* Section 예: “제 1 절 일반사항”, “제 2 절 정의” 
* Article 예: “101. 적용” 

---

## 4. UI 설계 (탭 + 그룹박스)

### 탭 1) PDF Import

**Group: 입력**

* 파일 선택(다중 선택 가능)
* 문서 ID(doc_id) 자동 생성/수정
* 출력 디렉토리 지정

**Group: 처리 범위**

* “차례 이후부터” 체크박스(기본 ON)
* 시작 조건 미리보기:

  * 감지된 `차 례` 위치 / 감지된 첫 `제 n 장` 위치 표시

---

### 탭 2) Extract (텍스트 추출)

**Group: 추출 엔진**

* Engine: PyMuPDF (기본)
* 스캔 PDF일 때 OCR 사용(옵션 토글, v0.1에선 비활성 가능)

**Group: 라인화 옵션**

* y-merge tolerance(기본값)
* 공백 정규화
* 하이픈 줄바꿈 병합

**Group: 실행/로그**

* 실행 버튼
* 진행률(페이지 단위)
* 결과 요약(총 라인 수 / 페이지별 라인 수)

---

### 탭 3) Parse (구조화/Path 태깅)

**Group: 규칙(Rules)**

* 정규식 규칙 세트 선택(문서별 YAML/JSON)
* 실시간 테스트:

  * 샘플 라인 입력 → “이 라인은 chapter/section/article/paragraph 중 무엇으로 인식되는지” 표시

**Group: Path 미리보기**

* 현재 선택 페이지/라인에 대해:

  * `chapter/section/article/paragraph` 값
  * 원문 라인 텍스트

---

### 탭 4) Export (JSON/CSV)

**Group: 포맷**

* JSONL(기본), CSV(옵션)
* 포함 필드 선택(doc_id, page, bbox 등)

**Group: 출력**

* 저장 버튼
* “DB Import 친화 검증” 체크:

  * JSON 파싱 가능 여부
  * 필수 필드 누락 여부

---

## 5. 내부 모듈 구조(권장)

```text
src/
  app.py
  ui/
    main_window.py
    tabs/
      tab_import.py
      tab_extract.py
      tab_parse.py
      tab_export.py
  core/
    extract_pymupdf.py
    line_rebuild.py
    normalize.py
    parse_state_machine.py
    rules.py
    export_jsonl.py
    export_csv.py
```

---

## 6. 규칙 파일(rules) 초안 (이 문서 전용)

(개념 설계만 — 구현은 다음 단계에서 코드로)

* chapter: `^제\s*(\d+)\s*장`
* section: `^제\s*(\d+)\s*절`
* article: `^(\d+)\.\s*`
* paragraph:

  * `^(\d+)\.\s+` (항)
  * `^\((\d+)\)\s+` (호)
  * `^\((가|나|다|라|마|바|사|아|자|차|카|타|파|하)\)\s+` (목)

---

## 7. 품질/검증 기능(필수)

* **샘플링 미리보기**: “선택 페이지”를 라인 단위로 보여주고, 각 라인의 Path를 같이 표시
* **목록 스킵 검증**: 차례 영역에서 export가 시작되지 않았는지 체크(“차 례” 이후 첫 “제 n 장”에서 시작했는지)

---

## 8. v0.1 개발 순서(추천)

1. 탭1: PDF Import + 파일 목록/경로 설정
2. 탭2: PyMuPDF로 페이지별 라인 추출 + JSONL(raw) 저장
3. 탭1 옵션: “차례 이후부터” 동작 구현(시작 인덱스 결정)
4. 탭3: chapter/section/article/paragraph 파싱(state machine) 적용
5. 탭4: JSONL export + 샘플 미리보기

---

