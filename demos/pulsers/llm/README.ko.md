# LLM Pulser 데모

## 번역본

- [English](README.md)
- [繁體中文](README.zh-Hant.md)
- [简体中文](README.zh-Hans.md)
- [Español](README.es.md)
- [Français](README.fr.md)
- [Italiano](README.it.md)
- [Deutsch](README.de.md)
- [日本語](README.ja.md)
- [한국어](README.ko.md)

## 이 폴더의 파일

- `plaza.agent`: 두 가지 LLM pulser 변형 모두를 위한 로컬 Plaza
- `openai.pulser`: OpenAI 지원 pulser 설정
- `ollama.pulser`: Ollama 기반 pulser 설정
- `start-plaza.sh`: Plaza 실행
- `start-openai-pulser.sh`: OpenAI demo pulser를 실행합니다
- `start-ollama-pulser.sh`: Ollama 데모 pulser를 실행합니다
- `run-demo.sh`: 하나의 터미널에서 전체 데모를 실행하고 브라우저 가이드와 선택한 pulser UI를 엽니다

## 단일 명령 실행

저장소 루트에서:
```bash
./demos/pulsers/llm/run-demo.sh
```

기본적으로 `OPENAI_API_KEY`가 있으면 OpenAI를 사용하고, 그렇지 않으면 Ollama로 대체됩니다.

명시적인 제공자 예시:
```bash
DEMO_LLM_PROVIDER=openai ./demos/pulsers/llm/run-demo.sh
DEMO_LLM_PROVIDER=ollama ./demos/pulsers/llm/run-demo.sh
```

런처가 터미널에만 유지되기를 원하는 경우 `DEMO_OPEN `DEMO_OPEN_BROWSER=0`을 설정하십시오.

## 플랫폼 퀵 스타트

### macOS 및 Linux

저장소 루트에서:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/llm/run-demo.sh
```

### Windows

Ubuntu 또는 다른 Linux 배포판과 함께 WSL2를 사용하세요. WSL 내부의 저장소 루트에서:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/llm/run-demo.sh
```

WSL에서 브라우저 탭이 자동으로 열리지 않는 경우, 런처를 계속 실행 상태로 두고 출력된 `guide=` URL을 Windows 브라우저에서 여십시오.

네이티브 PowerShell / Command Prompt 래퍼는 아직 포함되지 않았으므로, 현재 지원되는 Windows 경로는 WSL2입니다.

## 빠른 시작

### Plaza 시작하기

저장소 루트에서 터미널을 엽니다:
```bash
./demos/pulsers/llm/start-plaza.sh
```

예상 결과:

- Plaza가 `http://127.0.0.1:8261`에서 시작됩니다

그 다음 제공업체를 하나 선택하세요.

## 옵션 1: OpenAI

먼저 API 키를 설정하세요:
```bash
export OPENAI_API_KEY=your-key-here
```

그런 다음 pulser를 시작합니다:
```bash
./demos/pulsers/llm/start-openai-pulser.sh
```

예상 결과:

- pulser가 `http://127.0.0.1:8262`에서 시작됩니다
- `http://127.0.0.1:8261`에 있는 Plaza에 자신을 등록합니다

권장 테스트 페이로드:
```json
{
  "prompt": "Summarize why pulse interfaces are useful in one short paragraph.",
  "model": "gpt-4o-mini"
}
```

Curl 예시:
```bash
curl -sS http://127.0.0.1:8262/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"llm_chat","params":{"prompt":"Say hello in one sentence.","model":"gpt-4o-mini"}}'
```

## 옵션 2: Ollama

Ollama가 로컬에서 실행 중이며 구성된 모델을 사용할 수 있는지 확인하세요:
```bash
ollama serve
ollama pull qwen3:8b
```

그 다음 pulser를 시작하세요:
```bash
./demos/pulsers/llm/start-ollama-pulser.sh
```

예상 결과:

- pulser가 `http://127.0.0.1:8263`에서 시작됩니다
- `http://127.0.0.1:8261`에 있는 Plaza에 자신을 등록합니다

권장되는 curl 예시:
```bash
curl -sS http://127.0.0.1:8263/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"llm_chat","params":{"prompt":"Say hello in one sentence.","model":"qwen3:8b"}}'
```

## 브라우저에서 시도해 보세요

다음 중 하나를 여세요:

- OpenAI용: `http://120.0.0.1:8262/`
- Ollama용: `http://127.0.0.1:8263/`

UI를 통해 다음을 수행할 수 있습니다:

- pulser 설정 검사
- `llm_chat` 실행
- 모델 목록 로드
- 로컬 제공자를 사용할 때 Ollama 모델 정보 검사

## 주목해야 할 사항

- 동일한 pulse 계약을 클라우드 또는 로컬 추론 위에 구축할 수 있습니다
- OpenAI와 Ollama 사이의 전환은 인터페이스 재설계가 아닌 주로 설정의 문제입니다
- 이것은 저장소에 있는 pulser 기반 LLM 도구를 설명하기 위한 가장 간단한 데모입니다

## 나만의 버전 만들기

데모를 사용자 정의하려면:

1. `openai.pulser` 또는 `ollama.pulser`를 복사합니다
2. `model`, `base_url`, 포트 및 저장 경로 변경
3. 다른 도구나 UI가 이에 의존하는 경우 `llm_chat` pulse를 안정적으로 유지하십시오
