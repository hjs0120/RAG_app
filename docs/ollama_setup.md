# Ollama 설치 및 설정 (Windows)

RAG 앱의 LLM 답변 생성 기능을 사용하려면 로컬에서 **Ollama**를 실행해야 합니다.

---

## 1. Ollama 설치

### Windows

1. [Ollama 공식 사이트](https://ollama.com) 접속
2. **Download for Windows** 클릭
3. 다운로드된 `OllamaSetup.exe` 실행
4. 설치 완료 후 Ollama가 백그라운드 서비스로 자동 실행됨

### 설치 확인

PowerShell 또는 CMD에서:

```bash
ollama --version
```

설치되면 버전 정보가 출력됩니다.

---

## 2. 모델 다운로드

RAG 앱 기본 모델은 `qwen2.5:7b-instruct`입니다. 다음 명령으로 다운로드합니다.

```bash
ollama pull qwen2.5:7b-instruct
```

### GPU/VRAM별 권장 모델

| 환경 | 모델 |
|------|------|
| 8GB VRAM (3070 등) | `qwen2.5:7b-instruct`, `llama3.1:8b-instruct` |
| 12GB+ VRAM (4070 등) | `qwen2.5:14b-instruct` |
| CPU 전용 | `qwen2.5:7b-instruct` (느리지만 동작) |

추가 모델 다운로드 예시:

```bash
ollama pull qwen2.5:14b-instruct
ollama pull llama3.1:8b-instruct
```

다운로드된 모델 목록 확인:

```bash
ollama list
```

---

## 3. 실행 확인

Ollama가 설치되면 기본적으로 **시스템 트레이**에서 백그라운드로 실행됩니다.

### 수동 실행 (필요 시)

Ollama를 직접 실행하려면:

```bash
ollama serve
```

또는 **시작 메뉴**에서 "Ollama" 앱을 실행합니다.

### 연결 테스트

RAG 앱 실행 전, Ollama API가 응답하는지 확인합니다.

```bash
curl http://localhost:11434/api/tags
```

정상이면 설치된 모델 목록 JSON이 반환됩니다.

---

## 4. API 호출 예시

### Python에서 health_check

```python
import requests
r = requests.get("http://localhost:11434/api/tags", timeout=5)
print(r.status_code == 200)  # True: 정상
```

### 채팅 API 호출 (/api/chat)

```python
import requests

url = "http://localhost:11434/api/chat"
payload = {
    "model": "qwen2.5:7b-instruct",
    "messages": [
        {"role": "system", "content": "당신은 규격문서 전문가입니다."},
        {"role": "user", "content": "안녕하세요"}
    ],
    "stream": False
}
r = requests.post(url, json=payload, timeout=60)
data = r.json()
answer = data.get("message", {}).get("content", "")
print(answer)
```

### 생성 API 호출 (/api/generate)

```python
import requests

url = "http://localhost:11434/api/generate"
payload = {
    "model": "qwen2.5:7b-instruct",
    "prompt": "이동식 해양구조물 규칙에 대해 간단히 설명해 주세요.",
    "stream": False
}
r = requests.post(url, json=payload, timeout=60)
data = r.json()
response = data.get("response", "")
print(response)
```

---

## 5. 문제 해결

### "Ollama가 실행되지 않았습니다"

- **시작 메뉴**에서 "Ollama"를 실행하거나, CMD에서 `ollama serve` 실행
- 방화벽에서 `localhost:11434` 차단 여부 확인
- 다른 프로그램이 11434 포트를 사용 중인지 확인

### 모델 로딩이 오래 걸림

- 첫 요청 시 모델이 메모리에 로드되어 지연될 수 있음
- RAG 탭의 **"모델 사전 로드"** 버튼으로 미리 로드 가능

### VRAM 부족 (OOM)

- 더 작은 모델 사용: `ollama pull qwen2.5:7b-instruct`
- 또는 `ollama pull qwen2.5:3b` 등 경량 모델 시도

### 다른 포트 사용

기본 `http://localhost:11434`가 아닌 경우, 환경 변수로 설정:

```bash
set OLLAMA_HOST=http://127.0.0.1:12345
```

(현재 RAG 앱은 `OllamaClient`에서 기본 URL만 지원. 다른 포트 필요 시 `ollama_client.py` 수정)

---

## 참고 링크

- [Ollama 공식 문서](https://github.com/ollama/ollama/blob/main/docs/api.md)
- [Ollama 모델 라이브러리](https://ollama.com/library)
