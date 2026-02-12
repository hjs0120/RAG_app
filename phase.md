# PDF 규격문서 텍스트 추출 — 단계별 개발 계획

## UI 프레임워크

- **PySide6** (Qt for Python 6) 기반
- `QMainWindow`, `QTabWidget`, `QGroupBox`, `QPushButton` 등 Qt 위젯 사용

---

## 테스트 데이터

- **경로**: `data/이동식 해양구조물 규칙_2024.pdf`
- **개발 전반**: 이 파일만 사용하여 기능 검증

---

## Phase 진도 요약

| Phase | 내용 | 완료 |
|-------|------|:----:|
| 1 | 프로젝트 구조 및 의존성 설정 | ✅ |
| 2 | 탭 1 — PDF Import | ✅ |
| 3 | 탭 2 — PyMuPDF 라인 추출 | ✅ |
| 4 | 차례 스킵 및 본문 시작점 탐지 | ✅ |
| 5 | 탭 3 — Path 태깅(상태 머신) | ✅ |
| 6 | 탭 4 — JSONL/CSV Export | ✅ |
| 7 | 검수 탭 — PDF·JSONL 로드 및 좌우 분할 뷰 | ✅ |
| 8 | 검수 탭 — 라인 네비게이션 및 진행도 | ✅ |
| 9 | 검수 탭 — 수정 및 저장 | ✅ |
| 10 | 검수 탭 — PDF 뷰어 위 bbox 표시 | ☐ |
| 11 | 표·그림 감지 — 표제목/그림제목만 추출, 본문 제외 | ✅ |
| 12 | 수식 제외, paragraph 페이지 단위 구분(bbox 포함) | ✅ |

(참고: 기존 “Phase 7 통합 검증 및 마무리”는 수동 확인으로 생략 가능하여, 고도화 단계인 검수 탭을 Phase 7부터 진행한다.)

각 Phase의 **진도 체크** 항목을 검증 후 `[ ]` → `[x]`로 바꾸고, 위 표의 완료도 필요 시 ✅로 갱신하면 된다.

---

## Phase 1: 프로젝트 구조 및 의존성 설정

### 목표

전체 디렉터리 구조를 한 번에 생성하고, 실행 가능한 최소 앱 뼈대를 만든다.

### 작업 내용

1. **디렉터리 생성** (한 번에 전체 생성)

```
003.pdfdb/
├── data/                          # (기존) PDF 파일
├── src/
│   ├── app.py                     # 메인 진입점
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── main_window.py         # 메인 윈도우 + 탭 컨테이너
│   │   └── tabs/
│   │       ├── __init__.py
│   │       ├── tab_import.py
│   │       ├── tab_extract.py
│   │       ├── tab_parse.py
│   │       └── tab_export.py
│   └── core/
│       ├── __init__.py
│       ├── extract_pymupdf.py
│       ├── line_rebuild.py
│       ├── normalize.py
│       ├── parse_state_machine.py
│       ├── rules.py
│       ├── export_jsonl.py
│       └── export_csv.py
├── rules/                         # 규칙 YAML/JSON (Phase 4 이후)
├── output/                        # JSONL/CSV 출력 기본 경로
├── requirements.txt
├── goal.md
└── phase.md
```

2. **requirements.txt 작성**

```
PyMuPDF>=1.24.0
PySide6>=6.6.0
```

3. **최소 구현 파일**

- `src/app.py`: PySide6(Qt6) 앱 실행, `QApplication` + 메인 윈도우 표시
- `src/ui/main_window.py`: `QMainWindow` + `QTabWidget` 4개(Import, Extract, Parse, Export)
- 각 `tab_*.py`: `QWidget` + `QGroupBox` 배치 (Qt 위젯 기반)
- 각 `core/*.py`: `pass` 또는 docstring만 있는 스텁

### Phase 1에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `requirements.txt` | 패키지 목록 |
| `src/app.py` | 진입점, QApplication, 메인 루프 |
| `src/ui/main_window.py` | QMainWindow, QTabWidget |
| `src/ui/tabs/tab_import.py` | Import 탭 스켈레톤 |
| `src/ui/tabs/tab_extract.py` | Extract 탭 스켈레톤 |
| `src/ui/tabs/tab_parse.py` | Parse 탭 스켈레톤 |
| `src/ui/tabs/tab_export.py` | Export 탭 스켈레톤 |
| `src/core/*.py` (7개) | 빈 모듈 스텁 |

### 수동 검증 방법

1. `pip install -r requirements.txt` 실행 (PyMuPDF, PySide6 설치)
2. `python src/app.py` 실행
3. 다음 확인:
   - Qt 창이 뜨고 4개 탭(Import, Extract, Parse, Export)이 보이는지
   - 탭 전환이 되고, 각 탭에 QGroupBox가 보이는지
4. 오류 없이 종료되는지 확인

### 진도 체크

- [x] 디렉터리·requirements·스켈레톤 구현 완료
- [x] `pip install -r requirements.txt` 후 `python src/app.py` 실행 확인
- [x] Qt 창 4개 탭 표시·전환·QGroupBox 확인
- [x] 오류 없이 종료 확인

---

## Phase 2: 탭 1 — PDF Import

### 목표

파일 선택, doc_id 설정, 출력 디렉터리 지정, 처리 범위 옵션(차례 이후부터)을 UI에 반영한다.

### 작업 내용

- `tab_import.py`: 파일 선택 버튼, 다중 선택, doc_id 입력, 출력 경로, “차례 이후부터” 체크박스
- `main_window.py`: 탭 간 공유용 전역 상태(선택된 PDF 경로, doc_id, 출력 경로, 옵션) 추가
- `core/extract_pymupdf.py`: 아직 미구현이어도, 호출 시그니처만 준비 (Phase 3용)

### Phase 2에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `src/ui/tabs/tab_import.py` | Import 탭 전체 구현 |
| `src/ui/main_window.py` | 공유 상태 저장소 추가 |


### 수동 검증 방법

1. `python src/app.py` 실행
2. Import 탭에서:
   - “파일 선택” 클릭 → `data/이동식 해양구조물 규칙_2024.pdf` 선택
   - doc_id가 자동 생성(예: `MOUS_RULE_2024`)되는지 확인
   - 출력 디렉터리 선택 시 `output/` 기본값 적용되는지 확인
   - “차례 이후부터” 체크박스가 기본 ON인지 확인
3. 선택한 파일 경로가 UI에 표시되는지 확인

### 진도 체크

- [x] Import 탭: 파일 선택(다중), doc_id, 출력 경로, 차례 이후 체크 구현
- [x] main_window 공유 상태(app_state) 추가
- [x] extract_pymupdf 호출 시그니처 준비
- [x] 수동 검증 완료

---

## Phase 3: 탭 2 — PyMuPDF 라인 추출

### 목표

PyMuPDF로 페이지별 레이아웃 기반 라인 추출을 구현하고, Extract 탭에서 실행·진행률·요약을 보여준다.

### 작업 내용

- `core/extract_pymupdf.py`: 페이지별 `(text, bbox, page, line_no)` 형태 라인 추출
- `core/line_rebuild.py`: 같은 y 좌표 병합, 하이픈 줄바꿈 병합(옵션)
- `core/normalize.py`: 공백 정규화 스텁
- `tab_extract.py`: 실행 버튼, 진행률, 결과 요약(총 라인 수, 페이지별 라인 수)
- `main_window.py`: 추출 결과를 저장하는 상태 필드 추가

### Phase 3에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `src/core/extract_pymupdf.py` | PyMuPDF 라인 추출 |
| `src/core/line_rebuild.py` | 라인 재구성 |
| `src/core/normalize.py` | 정규화 스텁 |
| `src/ui/tabs/tab_extract.py` | Extract 탭 전체 구현 |
| `src/ui/main_window.py` | 추출 결과 저장 필드 |

### 수동 검증 방법

1. Import 탭에서 `data/이동식 해양구조물 규칙_2024.pdf` 선택
2. Extract 탭에서 “실행” 클릭
3. 확인:
   - 진행률이 페이지 단위로 갱신되는지
   - 완료 후 “총 라인 수”, “페이지별 라인 수”가 표시되는지
   - 각 라인에 `text`, `bbox`, `page`, `line_no`가 있는지
4. 콘솔 또는 간단 로그로 첫 3페이지의 라인 몇 개 출력해 구조가 올바른지 확인

### 진도 체크

- [x] extract_pymupdf.py 페이지별 라인 추출 구현
- [x] line_rebuild.py, normalize.py 스텁/옵션 반영
- [x] tab_extract.py 실행·진행률·요약 표시
- [x] main_window 추출 결과 상태 필드
- [x] 수동 검증 완료

---

## Phase 4: 차례 스킵 및 본문 시작점 탐지

### 목표

“차례 이후부터” 옵션이 켜져 있으면, “차 례” 이후 첫 “제 n 장”이 나오는 지점부터 추출 결과를 사용한다.

### 작업 내용

- `core/extract_pymupdf.py` 또는 별도 `core/toc_detector.py`:  
  `차\s*례` 매칭 → toc_mode=True, `^제\s*\d+\s*장` 매칭 → toc_mode=False, 그 인덱스부터 반환
- `main_window.py` / `tab_import.py`: Import 시 “차 례” 위치, 첫 “제 n 장” 위치 미리보기 표시(옵션)
- `tab_extract.py`: 추출 시 “차례 이후부터” 체크 상태에 따라 필터링된 라인만 사용

### Phase 4에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `src/core/extract_pymupdf.py` 또는 `src/core/toc_detector.py` | TOC 탐지 |
| `src/ui/tabs/tab_import.py` | 시작점 미리보기 |
| `src/ui/tabs/tab_extract.py` | TOC 필터 적용 |
| `src/ui/main_window.py` | 시작 인덱스 상태 전달 |

### 수동 검증 방법

1. Import 탭에서 “차례 이후부터” 체크 ON
2. Extract 실행 후:
   - 결과에 “차 례”와 목차에 해당하는 라인들이 제외되어 있는지 확인
   - 첫 번째 추출 라인이 “제 1 장 총칙” 또는 유사한 장 헤더인지 확인
3. “차례 이후부터” 체크 OFF 시, 차례 구간까지 포함되어 출력되는지 비교

### 진도 체크

- [x] TOC 탐지(차\s*례, 제 n 장) 구현
- [x] tab_import/tab_extract 미리보기·필터 연동
- [x] 차례 ON 시 본문만, OFF 시 차례 포함 출력 확인
- [x] 수동 검증 완료

---

## Phase 5: 탭 3 — Path 태깅(상태 머신)

### 목표

chapter / section / article / paragraph 구조를 인식하고 각 라인에 path 메타데이터를 부여한다.

### 작업 내용

- `core/rules.py`: 정규식 규칙 정의  
  - chapter: `^제\s*(\d+)\s*장`, section: `^제\s*(\d+)\s*절`, article: `^(\d+)\.\s*`, paragraph: 항/호/목
- `core/parse_state_machine.py`: 라인을 순서대로 읽으며 path 갱신
- `tab_parse.py`: 규칙 테스트용 샘플 입력, Path 미리보기(선택 페이지/라인별 chapter/section/article/paragraph)
- `main_window.py`: 파싱 결과 저장

### Phase 5에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `src/core/rules.py` | 정규식 규칙 |
| `src/core/parse_state_machine.py` | 상태 머신 파싱 |
| `src/ui/tabs/tab_parse.py` | Parse 탭 전체 구현 |
| `src/ui/main_window.py` | 파싱 결과 저장 |

### 수동 검증 방법

1. Import → Extract 완료 후 Parse 탭 이동
2. “Path 미리보기”에서 페이지/라인 선택
3. 확인:
   - “제 1 장 총칙” → chapter="제 1 장 총칙"
   - “제 1 절 일반사항” → section="제 1 절 일반사항"
   - “101. 적용” → article="101"
   - 일반 본문 → paragraph="1", "(1)", "(가)" 등
4. goal.md 예시와 유사한 path 구조가 나오는지 대조

### 진도 체크

- [x] rules.py 정규식 규칙 정의
- [x] parse_state_machine.py path 갱신 구현
- [x] tab_parse.py Path 미리보기
- [x] main_window 파싱 결과 저장
- [x] 수동 검증 완료

---

## Phase 6: 탭 4 — JSONL/CSV Export

### 목표

Path가 붙은 최종 결과를 JSONL(및 선택 시 CSV)로 저장하고, DB Import용 기본 검증을 수행한다.

### 작업 내용

- `core/export_jsonl.py`: goal.md 형식의 JSONL 출력
- `core/export_csv.py`: CSV 출력(옵션)
- `tab_export.py`: 포맷 선택, 필드 선택, 저장 버튼, 검증 결과 표시
- “DB Import 친화 검증”: JSON 파싱 가능 여부, 필수 필드(doc_id, page, path, text 등) 누락 여부

### Phase 6에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `src/core/export_jsonl.py` | JSONL 내보내기 |
| `src/core/export_csv.py` | CSV 내보내기 |
| `src/ui/tabs/tab_export.py` | Export 탭 전체 구현 |
| `src/ui/main_window.py` | Export 호출 및 경로 전달 |

### 수동 검증 방법

1. Import → Extract → Parse 완료 후 Export 탭 이동
2. JSONL 선택 후 “저장” 클릭 → `output/`에 파일 생성
3. 생성된 JSONL 파일을 텍스트 에디터로 열어:
   - 한 줄이 하나의 유효한 JSON 객체인지 확인
   - `doc_id`, `page`, `path`, `text`, `bbox`, `source` 등 필수 필드 포함 여부 확인
4. goal.md 1.3절 JSONL 예시와 형태가 유사한지 비교
5. 검증 체크박스 ON 시 “JSON 파싱 가능”, “필수 필드 누락 없음” 등이 표시되는지 확인

### 진도 체크

- [x] export_jsonl.py, export_csv.py 구현
- [x] tab_export 포맷·필드·저장·검증 UI
- [x] output/에 JSONL 생성 및 필수 필드 확인
- [x] 수동 검증 완료

---

## Phase 7: 검수 탭 — PDF·JSONL 로드 및 좌우 분할 뷰

### 목표

추출된 JSONL과 원본 PDF를 불러와, 좌측에는 PDF를, 우측에는 JSON 라인 내용을 필드별 텍스트박스로 구분해 표시한다. PDF와 추출 결과를 나란히 비교할 수 있는 검수용 UI의 기반을 만든다.

### 작업 내용

- **탭 추가**: 메인 윈도우에 “검수” 탭 추가 (`tab_review.py` 또는 `tab_inspect.py`)
- **파일 로드**:
  - PDF 파일 선택(또는 경로 입력)
  - JSONL 파일 선택(Export로 생성한 파일)
  - 로드 시 JSONL 한 줄씩 파싱해 레코드 리스트로 보관
- **좌측 패널**: PDF 뷰어
  - PyMuPDF(fitz)로 페이지를 이미지로 렌더링해 표시하거나, `QScrollArea` + `QLabel`(이미지)로 스크롤 가능하게 구성
  - 또는 외부 PDF 뷰어 연동이 어렵다면 “해당 페이지 이미지”만 표시해도 됨
- **우측 패널**: 현재 선택된 **한 라인(한 레코드)**에 대한 필드를 여러 개의 텍스트박스로 구분해 표시
  - 예: `doc_id`, `page`, `line_no`, `path`(chapter/section/article/paragraph), `text`, `bbox`, `source` 등
  - 읽기 전용으로 먼저 구현해 “보기” 동작만 되게 함 (수정은 Phase 9)

### Phase 7에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `src/ui/main_window.py` | 검수 탭 추가, 탭 위젯에 등록 |
| `src/ui/tabs/tab_review.py` (신규) | 검수 탭 UI: 파일 선택, 좌 PDF / 우 JSON 필드 영역 |
| `src/core/` (선택) | JSONL 로드 유틸 있으면 공용화 |

### 수동 검증 방법

1. 앱 실행 후 “검수” 탭 선택
2. PDF 파일 선택 → 좌측에 PDF(또는 페이지 이미지) 표시 확인
3. JSONL 파일 선택 → 우측에 첫 번째 레코드의 doc_id, page, line_no, path, text 등이 텍스트박스별로 표시되는지 확인
4. 레코드가 여러 개일 때, 초기에는 “첫 번째 라인”만 보여도 됨 (넘김은 Phase 8)

### 진도 체크

- [x] 검수 탭 추가 및 PDF·JSONL 파일 선택 UI
- [x] 좌측 PDF(또는 페이지 이미지) 표시
- [x] 우측 현재 라인 필드별 텍스트박스 표시(doc_id, page, line_no, path, text 등)
- [x] 수동 검증 완료

---

## Phase 8: 검수 탭 — 라인 네비게이션 및 진행도

### 목표

여러 JSONL 라인(레코드)을 좌우 화살표 또는 이전/다음 버튼으로 넘겨가며 볼 수 있게 하고, 상단에 “몇 번째 라인 / 전체” 진행도를 표시한다. 가능하면 PDF 쪽도 해당 라인의 페이지로 맞춰 준다.

### 작업 내용

- **상단 진행도 표시**
  - 예: “3 / 1592” 또는 “3번째 라인 (전체 1592개)”
  - `QLabel` 또는 진행률 표시용 위젯
- **라인 넘김**
  - “이전”(◀) / “다음”(▶) 버튼 또는 키보드 좌우 화살표
  - 현재 인덱스(0-based 또는 1-based) 갱신 시 우측 텍스트박스들을 해당 레코드로 갱신
- **PDF 연동**
  - 현재 레코드의 `page` 값에 해당하는 PDF 페이지를 좌측에 표시(이미지로 렌더링한 경우 해당 페이지로 스크롤/전환)
  - 페이지가 바뀔 때만 좌측 뷰 갱신해도 됨
- **경계 처리**: 첫 라인에서 “이전” 비활성, 마지막 라인에서 “다음” 비활성

### Phase 8에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `src/ui/tabs/tab_review.py` | 이전/다음 버튼, 현재 인덱스 상태, 진행도 라벨, PDF 페이지 연동 |

### 수동 검증 방법

1. JSONL 로드 후 “다음” 여러 번 클릭 → 우측 필드와 상단 “N / 전체”가 갱신되는지 확인
2. “이전” 클릭 → 이전 레코드로 돌아가는지 확인
3. 현재 레코드의 `page`가 바뀌면 좌측 PDF(또는 이미지)가 해당 페이지로 전환되는지 확인
4. 첫/끝 라인에서 이전/다음 버튼 비활성 여부 확인

### 진도 체크

- [x] 상단 “N번째 / 전체” 진행도 표시
- [x] 이전/다음(또는 좌우 화살표)으로 라인 넘김
- [x] 현재 라인에 따라 PDF 페이지 연동
- [x] 수동 검증 완료

---

## Phase 9: 검수 탭 — 수정 및 저장

### 목표

우측에 표시된 JSON 필드를 PDF와 비교해 틀린 부분을 수정할 수 있게 하고, 수정된 내용을 JSONL 파일로 저장한다.

### 작업 내용

- **편집 가능 필드**
  - 수정 허용할 필드(예: `text`, `path` 내 chapter/section/article/paragraph)를 `QLineEdit` 또는 `QPlainTextEdit`로 전환
  - `doc_id`, `page`, `line_no` 등은 필요 시 읽기 전용 유지
- **메모리 내 수정**
  - 현재 인덱스의 레코드를 사용자가 편집한 값으로 갱신
  - 이전/다음으로 이동해도 편집 내용이 유지되도록 in-memory 리스트 관리
- **저장**
  - “저장” 버튼 클릭 시 현재 레코드 리스트를 JSONL 형식으로 파일에 덮어쓰기
  - 또는 “다른 이름으로 저장”으로 새 JSONL 생성
- **검증(선택)**: 저장 전 필수 필드·JSON 형식 간단 검증

### Phase 9에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `src/ui/tabs/tab_review.py` | 편집 가능 위젯, 저장/다른 이름으로 저장, 리스트 갱신 로직 |
| `src/core/export_jsonl.py` | 기존 `write_jsonl` 재사용 가능(레코드 리스트 → 파일) |

### 수동 검증 방법

1. 특정 라인에서 `text` 또는 path 일부 수정 후 “다음” → 다시 “이전”으로 돌아와 수정 내용이 유지되는지 확인
2. “저장” 클릭 → 원본 JSONL 덮어쓰기 후 파일을 열어 해당 라인이 수정된 값으로 저장되었는지 확인
3. “다른 이름으로 저장”으로 새 파일 저장 후 동일 검증

### 진도 체크

- [x] 편집 가능 필드(text, path 등) 구현
- [x] 라인 넘김 시 편집 내용 유지
- [x] 저장 / 다른 이름으로 저장
- [x] 수동 검증 완료

---

## Phase 10: 검수 탭 — PDF 뷰어 위 bbox 표시

### 목표

검수 탭 좌측 PDF 뷰어에서 현재 선택된 라인의 bbox(영역)를 페이지 이미지 위에 시각적으로 표시하여, 해당 라인이 PDF 상에서 어디에 해당하는지 한눈에 볼 수 있게 한다.

### 작업 내용

- **bbox 그리기**
  - 현재 레코드의 `bbox` [x0, y0, x1, y1](PDF 포인트 좌표)를 렌더된 페이지 pixmap 좌표로 변환 후, PDF 뷰 위에 사각형으로 그린다.
  - **스타일**: 빨간색(`#cc0000`), 선 두께 3px, 채우기 없음 — 강조되어 잘 보이도록 한다.
- **연동**
  - 이전/다음으로 라인을 넘길 때마다 해당 라인의 bbox만 그려진 상태로 PDF 뷰가 갱신된다.
  - bbox가 없거나 유효하지 않은 레코드는 사각형 없이 페이지만 표시한다.

### Phase 10에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `src/ui/tabs/tab_review.py` | bbox를 pixmap 위에 그리는 함수, `_refresh_pdf_view`에서 현재 레코드 bbox 적용 |

### 수동 검증 방법

1. 검수 탭에서 PDF·JSONL 로드 후, 이전/다음으로 라인을 넘겨가며 좌측 PDF에 빨간 사각형이 해당 라인 영역에 겹쳐 그려지는지 확인한다.
2. bbox가 있는 라인과 없는 라인을 각각 확인해, 있는 경우에만 사각형이 그려지는지 확인한다.
3. 선이 빨간색이고 굵게 보이는지 확인한다.

### 진도 체크

- [x] 현재 라인 bbox를 PDF 뷰 위에 빨간색 굵은 사각형으로 표시
- [x] 수동 검증 완료

---

## Phase 11: 표·그림 감지 — 표제목/그림제목만 추출, 본문 제외

### 목표

추출 단계에서 **표(table)** 구간은 표 제목(표제목)만 추출하고 표 내용(셀 텍스트)은 제외하며, **그림(figure)** 구간은 그림 제목(그림제목)만 넣고 그림 본체(이미지/도해)는 제외한다. 규격문서에서 표·그림이 많을 때 본문 중심의 JSONL을 만들기 위함이다.

### 가능한 방안

#### 표(Table) — 표제목만 추출

| 방안 | 설명 | 장점 | 비고 |
|------|------|------|------|
| **A. 제목 패턴 + 구간 제외** | “표 1”, “별표 1”, “〈표 2〉” 등 정규식으로 표제목 라인만 매칭해 **해당 라인만** 출력하고, 그 다음 연속된 라인들(표 본문으로 추정)은 **일정 조건까지 제외**한다. 표 본문 끝은 “다음 표제목”, “다음 장/절 헤더”, 또는 빈 줄/페이지 구분 등으로 판단. | 구현 단순, 규격문서 패턴이 일정할 때 효과적 | 패턴 목록을 `rules` 또는 설정으로 두고 확장 가능 |
| **B. 레이아웃 기반 표 영역 감지** | PyMuPDF `get_text("dict")`의 블록/라인 bbox를 이용해, **여러 열(비슷한 x 구간 반복)·여러 행(비슷한 y 구간)** 구조를 “표 영역”으로 추정. 그 영역 **직전 1~2라인**을 표제목 후보로 두고, 표제목 패턴에 맞으면 제목만 남기고 표 영역 라인 전체는 제외. | 표가 격자 형태로 나올 때 본문과 구분 가능 | 행/열 정렬 임계값, 최소 행·열 수 등 휴리스틱 필요 |
| **C. Tagged PDF 활용** | PDF가 태깅되어 있으면 표(`/Table`), 캡션(`/Caption`) 등 역할을 읽어, 표 블록은 캡션만 추출. | 정확도 높음 | 비태깅 PDF에는 적용 불가, 폴백으로 A/B 필요 |

**권장**: 먼저 **A**로 표제목 패턴만 추출·표 본문 제외를 구현하고, 필요 시 **B**를 보완(표 영역 감지로 제외 구간 정교화).

#### 그림(Figure) — 그림제목만 추출

| 방안 | 설명 | 장점 | 비고 |
|------|------|------|------|
| **A. 제목 패턴 + 구간 제외** | “그림 1”, “Figure 1”, “〈그림 2〉” 등 정규식으로 **그림제목 라인만** 출력. 그 다음 라인은 “다음 그림제목” 또는 “표제목/장·절 헤더”가 나올 때까지 그림 설명으로 보고 **제외**(또는 한 줄만 넣는 등 정책 선택). | 구현 단순 | 그림이 1줄 캡션인 경우가 많아 표보다 단순 |
| **B. 이미지 블록 인접 텍스트** | PyMuPDF에서 **이미지 블록**(`block["type"]` 또는 이미지 bbox)을 찾고, 그 직전/직후 1~2라인을 그림제목 후보로 간주. 패턴 매칭 시 해당 라인만 추출하고, 이미지 블록 및 그 안의 “텍스트”는 제외. | 이미지와 캡션 위치 관계 활용 | 이미지가 인라인이 아닌 블록으로 있을 때 유리 |
| **C. 큰 bbox + 텍스트 희소** | 텍스트가 거의 없고 bbox가 큰 영역을 “그림/도해”로 추정하고, 그 위/아래 인접 라인을 그림제목 후보로 사용. | 태깅 없는 PDF에서도 적용 가능 | 휴리스틱 튜닝 필요 |

**권장**: 먼저 **A**로 그림제목 패턴만 추출·그림 본문 제외를 구현하고, 필요 시 **B**로 이미지 블록 인접 캡션을 보완.

#### 공통

- **적용 시점**: Extract 직후 또는 Parse 직전에 “표/그림 구간 필터”를 한 번 거치는 방식이 단순하다. 즉, 라인 리스트에서 “표 제목/그림 제목에 해당하는 라인만 남기고, 표 본문·그림 본문으로 판단된 라인은 제거”하는 **필터 모듈**을 두고, Extract → (선택) 표/그림 필터 → Line rebuild → … 순으로 연결.
- **설정**: “표제목만 추출”, “그림제목만 추출”을 Import/Extract 탭 체크박스나 옵션으로 두고, 기본 ON으로 두면 된다.
- **path/메타**: 표제목·그림제목 라인에는 path는 기존 상태 머신대로 두고, **메타 필드**로 `block_type: "table_caption"` / `"figure_caption"` 등을 붙여 두면 검수·후처리 시 유리하다.

### 작업 내용

- **표 제목만 추출**
  - 표제목 패턴(예: `표\s*\d+`, `별표\s*\d+`, `〈표\s*\d+〉`)을 규칙으로 정의하고, 매칭되는 라인만 남긴다. 해당 표제목 “다음”부터 다음 표제목/다음 장·절/빈 줄 등이 나올 때까지의 라인은 **제외**하는 필터 구현.
  - (선택) 레이아웃 기반 표 영역 감지로 제외 구간을 더 정확히 잡기.
- **그림 제목만 추출**
  - 그림제목 패턴(예: `그림\s*\d+`, `Figure\s*\d+`)을 규칙으로 정의하고, 매칭되는 라인만 남긴다. 그림제목 다음 구간(다음 그림/표/헤더까지)은 제외하는 필터 구현.
  - (선택) 이미지 블록 인접 캡션 감지 보완.
- **파이프라인 연동**
  - Extract 탭 또는 별도 옵션에서 “표제목만 추출”, “그림제목만 추출” 옵션을 켜면, 추출 라인 리스트에 위 필터를 적용한 결과를 다음 단계(Line rebuild / TOC 필터 / Parse)에 넘긴다.
- **메타(선택)**: 표제목/그림제목 라인에 `block_type` 등 메타를 붙여 Export 시 구분 가능하게 한다.

### Phase 11에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `src/core/rules.py` 또는 `src/core/table_figure_rules.py` (신규) | 표제목·그림제목 정규식 패턴 |
| `src/core/table_figure_filter.py` (신규) | 표/그림 구간 감지 및 제목만 남기는 필터 |
| `src/core/extract_pymupdf.py` 또는 `src/ui/tabs/tab_extract.py` | 필터 호출 시점, 옵션 전달 |
| `src/ui/tabs/tab_import.py` 또는 `tab_extract.py` | “표제목만 추출”, “그림제목만 추출” 체크박스/옵션 |

### 수동 검증 방법

1. 표·그림이 포함된 테스트 PDF(예: 이동식 해양구조물 규칙)로 Extract 실행 시 “표제목만 추출”, “그림제목만 추출” 옵션 ON.
2. 생성된 JSONL에서 “표 1”, “그림 1” 등 제목에 해당하는 라인만 포함되고, 표 셀 내용·그림 본문 텍스트는 레코드에 없음을 확인.
3. 옵션 OFF일 때는 기존처럼 표/그림 구간 라인도 모두 추출되는지 비교 확인.

### 진도 체크

- [x] 표제목 패턴 정의 및 표 본문 구간 제외 필터
- [x] 그림제목 패턴 정의 및 그림 본문 구간 제외 필터
- [x] Extract(또는 파이프라인) 옵션 연동
- [x] 수동 검증 완료

---

## Phase 12: 수식 제외, paragraph 페이지 단위 구분(bbox 포함)

### 목표

1. **수식 제외**: 추출 단계에서 수식(식, equation) 구간을 감지해 제외한다. 표·그림과 마찬가지로 본문 중심 JSONL을 만들기 위함이다.
2. **같은 paragraph, 페이지 넘김 구분**: Paragraph 단위로 합칠 때, 하나의 paragraph가 여러 페이지에 걸쳐 있으면 **페이지별로 구분**해 각각 별도 레코드로 출력한다. 이때 **bbox도 페이지 단위로 구분**되어, 해당 페이지 안에 있는 부분만의 bbox(union)를 갖도록 한다.

### 작업 내용

#### 1. 수식 제외

- **수식 구간 감지**
  - **패턴**: “식 1”, “(1)”, “식 (1)”, “①” 등 식 번호로 시작하는 라인을 수식 캡션/식 번호로 볼 수 있음. 수식 본문은 그 다음 라인들(다음 식 번호/다음 장·절/표·그림 제목까지)로 추정.
  - **휴리스틱**: 수식이 있는 블록은 라인이 짧고, 특수문자·숫자·그리스문자 비율이 높은 경우가 많음. 해당 라인만 제외하거나, “식 n” 다음 구간을 제외하는 필터 추가.
- **연동**
  - Phase 11의 표·그림 필터와 동일하게, Extract 직후(또는 표/그림 필터 다음)에 “수식 제외” 필터를 적용. 옵션은 “수식 제외” 체크박스(Extract 탭, 기본 ON 가능).
- **메타(선택)**: 수식 캡션만 남기는 정책을 쓸 경우 `block_type: "equation_caption"` 등으로 구분.

#### 2. 같은 paragraph, 페이지 넘김 구분

- **적용 시점**: Paragraph 단위 합치기(merge_paragraphs)를 수행할 때, **먼저 path가 같은 연속 라인을 페이지별로 나눈 뒤**, 페이지 내에서만 텍스트·bbox를 합친다.
  - 즉, (path, page) 쌍이 바뀌는 경계에서 끊어서, “같은 path + 같은 page” 구간만 하나의 merged 레코드로 만든다.
  - 결과: 같은 paragraph라도 페이지가 다르면 **서로 다른 레코드**가 되고, 각 레코드의 `page`는 해당 페이지만, `text`는 그 페이지에 해당하는 문장만, `bbox`는 그 페이지 내 라인들의 union만 갖는다.
- **구체 동작**
  - `merge_paragraphs`(또는 그 전처리) 단계에서: path 키로 그룹을 묶되, **연속 라인 중 page가 바뀌면 그 시점에서 그룹을 끊고** 새 그룹 시작. 각 그룹 = (path, page)가 동일한 구간.
  - 그룹별로 text 합치기, bbox는 해당 그룹 내 라인들의 union. `page`, `line_no`는 해당 그룹의 첫 라인 값 사용.
- **Export**: 기존 JSONL/CSV 형식 유지. 레코드 수가 “페이지가 넘어가는 paragraph”만큼 늘어남.

### Phase 12에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `src/core/equation_filter.py` | 들여쓰기 기반 수식/변수 정의 블록 제외 (`apply_equation_filter`) |
| `src/core/export_jsonl.py` | `merge_paragraphs` 단계에서 (path, page) 단위 구분 및 bbox 페이지별 union |
| `src/ui/tabs/tab_extract.py` | “수식 제외” 수식 제외(들여쓰기 블록·변수 정의 포함) 체크박스 및 옵션 전달 |

### 수동 검증 방법

1. **수식 제외**: 수식이 포함된 PDF로 Extract 실행 시 “수식 제외” ON → 수식 본문 라인이 JSONL에 없음을 확인. OFF 시 기존처럼 포함되는지 비교.
2. **페이지 구분**: Paragraph 합치기 ON 상태에서, 여러 페이지에 걸친 paragraph가 있는 문서로 Export → 같은 path여도 페이지가 다르면 별도 레코드로 나뉘고, 각 레코드의 `page`·`text`·`bbox`가 해당 페이지에만 해당하는지 확인.

### 진도 체크

- [x] 수식 제외(들여쓰기 기반) 필터 및 Extract 옵션 연동
- [x] merge_paragraphs에서 (path, page) 단위 구분 및 페이지별 bbox union
- [ ] 수동 검증 완료

---

## 토큰 최소화 가이드

| Phase | 집중할 디렉터리/파일 | 참고 문서 |
|-------|----------------------|-----------|
| 1 | `src/` 전체, `requirements.txt` | goal.md §5 |
| 2 | `src/ui/tabs/tab_import.py`, `main_window.py` | goal.md §4 탭1 |
| 3 | `src/core/extract_pymupdf.py`, `line_rebuild.py`, `tab_extract.py` | goal.md §2.1, §3.2 |
| 4 | `extract_pymupdf.py` 또는 `toc_detector.py`, `tab_import.py`, `tab_extract.py` | goal.md §3.1 |
| 5 | `src/core/rules.py`, `parse_state_machine.py`, `tab_parse.py` | goal.md §3.3, §6 |
| 6 | `src/core/export_jsonl.py`, `export_csv.py`, `tab_export.py` | goal.md §1.3, §4 탭4 |
| 7 | `main_window.py`, `tab_review.py` (신규), PDF 렌더/로드 | phase.md Phase 7 |
| 8 | `src/ui/tabs/tab_review.py` | phase.md Phase 8 |
| 9 | `src/ui/tabs/tab_review.py`, `export_jsonl.py` | phase.md Phase 9 |
| 10 | `src/ui/tabs/tab_review.py` | phase.md Phase 10 |
| 11 | `table_figure_rules.py`, `table_figure_filter.py`, `extract_pymupdf.py`, `tab_extract.py` | phase.md Phase 11 |
| 12 | `equation_filter.py`, `export_jsonl.py`(merge_paragraphs), `tab_extract.py` | phase.md Phase 12 |

매 Phase는 위 표에 해당하는 파일만 열어 작업하면 토큰 사용을 최소화할 수 있다.
