# Analyst Insight Pulser 데모

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

## 이 데모가 보여주는 내용

- 여러 개의 구조화된 인사이트 pulse를 포함하는 분석가 소유의 pulser 1개
- 별도의 뉴스 에이전트 및 로컬 Ollama 에이전트 상에서 작동하는 분석가 소유의 두 번째 pulser
- 원시 소스 데이터와 분석가가 작성한 Prompits 및 최종 소비자용 출력을 분리하는 깔끔한 방법
- 다른 사용자의 관점에서 동일한 스택을 보여주는 개인 에이전트 워크스루
- 분석가나 PM이 자신의 견해를 게시하기 위해 편집하게 될 정확한 파일들

## 이 폴더의 파일

- `plaza.agent`: 애널리스트 pulser 데모를 위한 로컬 Plaza
- `analyst-insights.pulser`: 공개 pulse 카탈로그를 정의하는 `PathPulser` 설정
- `analyst_insight_step.py`: 공유 변환 로직 및 시드된 애널리스트 커버리지 패킷
- `news-wire.pulser`: 시드된 `news_article` 패킷을 게시하는 로컬 업스트림 뉴스 에이전트
- `news_wire_step.py`: 업스트림 뉴스 에이전트에서 반환되는 시드된 원시 뉴스 패킷
- `ollama.pulser`: 애널리스트 프롬프트 데모를 위한 로컬 Ollama 기반 `llm_chat` pulser
- `analyst-news-ollama.pulser`: 뉴스를 가져오고, 애널리스트 소유의 프롬프트를 적용하며, Ollama를 호출하고, 결과를 여러 pulses로 정규화하는 구성된 애널리스트 pulser
- `analyst_news_ollama_step.py`: 애널리스트 소유의 프롬프트 팩 및 JSON 정규화 로직
- `start-plaza.sh`: Plaza 실행
- `start-pulser.sh`: 고정된 구조화된 애널리스트 pulser 실행
- `start-news-pulser.sh`: 업스트림 시드된 뉴스 에이전트 실행
- `start-ollama-pulser.sh`: 로컬 Ollama pulser 실행
- `start-analyst-news-pulser.sh`: 프롬프트가 적용된 애널리스트 pulser 실행
- `start-personal-agent.sh`: 컨슈머 뷰 워크스루를 위한 개인 에이전트 UI 실행
- `run-demo.sh`: 하나의 터미널에서 데모를 실행하고 브라우저 가이드 및 메인 UI 페이지를 엽니다

## 단일 명령 실행

저장소 루트에서:
```bash
./demos/pulsers/analyst-insights/run-demo.sh
```

이 래퍼는 기본적으로 경량화된 구조화된 흐름을 시작합니다.

대신 고급 뉴스 + Ollama + 개인 에이전트 흐름을 실행하려면:
```bash
DEMO_ANALYST_MODE=advanced ./demos/pulsers/analyst-insights/run-demo.sh
```

런처가 터미널에만 유지되기를 원하는 경우 `DEMO_OPEN_BROWSER=0`을 설정하십시오.

## 플랫폼 퀵 스타트

### macOS 및 Linux

저장소 루트에서:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/analyst-insights/run-demo.sh
```

고급 경로의 경우:
```bash
DEMO_ANALYST_MODE=advanced ./demos/pulsers/analyst-insights/run-demo.sh
```

### Windows

네이티브 Windows Python 환경을 사용하십시오. PowerShell에서 리포지토리 루트로 이동하여 다음을 실행하십시오:
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher analyst-insights
```

고급 경로의 경우:
```powershell
$env:DEMO_ANALYST_MODE = "advanced"
.venv\Scripts\python.exe -m scripts.demo_launcher analyst-insights
```

브라우저 탭이 자동으로 열리지 않으면 런처를 계속 실행 상태로 두고 출력된 `guide=` URL을 Windows 브라우저에서 여십시오.

## 데모 1: 구조화된 분석가 뷰

이것은 LLM을 사용하지 않는 로컬 전용 경로입니다.

저장소 루트에서 두 개의 터미널을 엽니다.

### 터미널 1: Plaza 시작
```bash
./demos/pulsers/analyst-insights/start-plaza.sh
```

예상 결과:

- Plaza가 `http://127.0.0.1:8266`에서 시작됩니다

### 터미널 2: pulser 시작
```bash
./demos/pulsers/analyst-insights/start-pulser.sh
```

예상 결과:

- pulser가 `http://127.0.0.1:8267`에서 시작됩니다
- `http://127.0.0.1:8266`에 있는 Plaza에 자신을 등록합니다

## 브라우저에서 시도해 보세요

열기:

- `http://127.0.0.1:8267/`

그런 다음 `NVDA`로 다음 pulse들을 테스트하세요:

1. `rating_summary`
2. `thesis_bullets`
3. `risk_watch`
4. `scenario_grid`

4개 모두에 권장되는 파라미터:
```json
{
  "symbol": "NVDA"
}
```

표시되는 내용:

- `rating_summary`는 주요 판단, 목표, 신뢰도 및 짧은 요약을 반환합니다
- `thesis_bullets`는 긍정적인 논거를 불렛 포인트 형식으로 반환합니다
- `risk_watch`는 주요 리스크와 모니터링해야 할 사항을 반환합니다
- `scenario_grid`는 강세, 기본, 약세 시나리오를 하나의 구조화된 페이로드로 반환합니다

## Curl로 테스트하기

헤드라인 점수:
```bash
curl -sS http://127.0.0.1:8267/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"rating_summary","params":{"symbol":"NVDA"}}'
```

논문 요점:
```bash
curl -sS http://127.0.0.1:8267/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"thesis_bullets","params":{"symbol":"NVDA"}}'
```

리스크 모니터링:
```bash
curl -sS http://127.0.0.1:8267/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"risk_watch","params":{"symbol":"NVDA"}}'
```

## 분석가가 이 데모를 커스텀하는 방법

두 가지 주요 편집 지점이 있습니다.

### 1. 실제 리서치 뷰 변경

편집:

- `demos/pulsers/analyst-insights/analyst_insight_step.py`

이 파일에는 초기화된 `ANALYST_COVERAGE` 패킷이 포함되어 있습니다. 여기서 다음 항목을 변경할 수 있습니다:

- 커버되는 심볼
- 분석가 이름
- 등급 라벨
- 목표 가격
- 테제 불렛 포인트
- 주요 리스크
- 강세/기본/약세 시나리오

### 2. 공개 pulse 카탈로그 변경

편집:

- `demos/pulsers/analyst-insights/analyst-insights.pulser`

이 파일은 다음을 제어합니다:

- 존재하는 pulse
- 각 pulse의 이름 및 설명
- 입력 및 출력 스키마
- 태그 및 주소

새로운 인사이트 pulse를 추가하려면 기존 항목 중 하나를 복사하여 새로운 `insight_view`를 가리키도록 설정하십시오.

## 이 패턴이 유용한 이유

- 포트폴리오 도구는 `rating_summary`만 요청할 수 있습니다
- 리포트 빌더는 `thesis_bullets`를 요청할 수 있습니다
- 리스크 대시보드는 `risk_watch`를 요청할 수 있습니다
- 밸류에이션 도구는 `scenario_grid`를 요청할 수 있습니다

즉, 분석가는 하나의 서비스만 게시하지만, 서로 다른 소비자들은 자신에게 필요한 부분만 정확하게 가져올 수 있습니다.

## 다음 단계

이 로컬 pulser 형태가 타당해지면, 다음 단계는 다음과 같습니다:

1. 애널리스트 커버리지 패킷에 더 많은 대상 심볼을 추가합니다
2. 자신의 관점을 YFinance, ADS 또는 LLM 출력과 혼합하려는 경우 마지막 Python 단계 전에 소스 단계를 추가합니다
3. 로컬 demo Plaza 대신 공유 Plaza를 통해 pulser를 노출합니다

## 데모 2: Analyst Prompt Pack + Ollama + 개인 에이전트

이 두 번째 흐름은 더 현실적인 분석가 설정을 보여줍니다:

- 하나의 에이전트가 원시 `news_article` 데이터를 게시합니다
- 두 번째 에이전트가 Ollama를 통해 `llm_chat`을 노출합니다
- 분석가 소유의 pulser는 자체 prompt pack을 사용하여 해당 가공되지 않은 뉴스를 여러 번 재사용 가능한 pulses로 변환합니다
- 개인 에이전트가 다른 사용자의 관점에서 완료된 pulses를 소비합니다

### 프롬프트 흐름을 위한 사전 요구 사항

Ollama가 로컬에서 실행 중이며 모델이 존재하는지 확인하세요:

```bash
ollama serve
ollama pull qwen3:8b
```

그 다음 저장소 루트에서 터미널 5개를 엽니다.

### 터미널 1: Plaza 시작

Demo 1이 여전히 실행 중인 경우, 동일한 Plaza를 계속 사용하십시오.
```bash
./demos/pulsers/analyst-insights/start-plaza.sh
```

예상 결과:

- Plaza가 `http://127.0.0.1:8266`에서 시작됩니다

### 터미널 2: 업스트림 뉴스 에이전트 시작
```bash
./demos/pulsers/analyst-insights/start-news-pulser.sh
```

예상 결과:

- news pulser가 `http://127.0.0.1:8268`에서 시작됩니다
- `http://127.0.0.1:8266`에 있는 Plaza에 자신을 등록합니다

### 터미널 3: Ollama pulser 시작
```bash
./demos/pulsers/analyst-insights/start-ollama-pulser.sh
```

예상 결과:

- Ollama pulser가 `http://127.0.0.1:8269`에서 시작됩니다
- `http://127.0.0.1:8266`에 있는 Plaza에 자신을 등록합니다

### 터미널 4: prompted analyst pulser 시작

뉴스 및 Ollama 에이전트가 이미 실행 중인 상태에서 이를 시작하십시오. pulser는 시작 중에 샘플 체인을 검증하기 때문입니다.
```bash
./demos/pulsers/analyst-insights/start-analyst-news-pulser.sh
```

예상 결과:

- 프롬프트된 분석가 pulser가 `http://127.0.0.1:8270`에서 시작됩니다
- `http://127.0.0.1:8266`에 있는 Plaza에 자신을 등록합니다

### 터미널 5: 개인 에이전트 시작
```bash
./demos/pulsers/analyst-insights/start-personal-agent.sh
```

예상 결과:

- 개인 에이전트가 `http://127.0.0.1:8061`에서 시작됩니다

### Prompted Analyst Pulser 직접 시도하기

열기:

- `http://127.0.0.1:8270/`

그런 다음 `NVDA`로 다음 pulses를 테스트하십시오:

1. `news_desk_brief`
2. `news_monitoring_points`
3. `news_client_note`

권장 파라미터:
```json
{
  "symbol": "NVDA",
  "number_of_articles": 2,
  "model": "qwen3:8b"
}
```

표시되는 내용:

- `news_desk_brief`는 업스트림 기사를 PM 스타일의 입장 및 짧은 노트로 변환합니다
- `news_monitoring_points`는 동일한 원시 기사를 모니터링 항목 및 위험 플래그로 변환합니다
- `news_client_note`는 동일한 원시 기사를 더 깔끔한 고객용 노트로 변환합니다

중요한 점은 분석가가 하나의 파일에서 Prompits를 제어하는 반면, 다운스트림 사용자는 안정적인 pulse 인터페이스만 보게 된다는 것입니다.

### 다른 사용자의 관점에서 개인 에이전트 사용하기

열기:

- `http://127.0.0.1:8061/`

그런 다음 다음 경로를 따르십시오:

1. `Settings`를 엽니다.
2. `Connection` 탭으로 이동합니다.
3. Plaza URL을 `http://127.0.0.1:8266`으로 설정합니다.
4. `Refresh Plaza Catalog`를 클릭합니다.
5. `New Browser Window`를 생성합니다.
6. 브라우저 창을 `edit` 모드로 전환합니다.
7. 첫 번째 plain pane을 추가하고 `DemoAnalystNewsWirePulser -> news_article`를 가리키도록 합니다.
8. pane params를 사용합니다:
```json
{
  "symbol": "NVDA",
  "number_of_articles": 2
}
```

9. 사용자가 원문 기사를 볼 수 있도록 `Get Data`를 클릭합니다.
10. 두 번째 플레인 창을 추가하고 `DemoAnalystPromptedNewsPulser -> news_desk_brief`를 가리키도록 합니다.
11. 동일한 파라미터를 재사용하고 `Get Data`를 클릭합니다.
12. `news_monitoring_points` 또는 `news_client_note`를 사용하여 세 번째 창을 추가합니다.

확인할 수 있는 내용:

- 한 창에는 다른 에이전트로부터 가져온 원시 업스트림 뉴스가 표시됩니다
- 다음 창에는 분석가가 처리한 뷰가 표시됩니다
- 세 번째 창에는 동일한 분석가 프롬프트 팩이 어떻게 다른 대상에게 다른 서피스를 게시할 수 있는지 보여줍니다

이것이 핵심적인 소비자 스토리입니다. 다른 사용자는 내부 체인을 알 필요가 없습니다. 그저 Plaza를 탐색하고, pulse를 선택하여 완성된 분석 결과물을 소비하기만 하면 됩니다.

## 분석가가 프롬프트 흐름을 커스텀하는 방법

데모 2에는 세 가지 주요 편집 지점이 있습니다.

### 1. 업스트림 뉴스 패킷 변경

편집:

- `demos/pulsers/analyst-insights/news_wire_step.py`

여기에서 업스트림 소스 에이전트가 게시하는 시드 기사를 변경합니다.

### 2. 분석가 자신의 프롬프트 변경

편집:

- `demos/pulserv/analyst-insights/analyst_news_ollama_step.py`

이 파일에는 다음을 포함하여 분석가가 소유한 프롬프트 팩이 포함되어 있습니다:

- 프롬프트 프로필 이름
- 대상 및 목표
- 어조 및 작성 스타일
- 요구되는 JSON 출력 계약

동일한 원시 뉴스에서 다른 연구 목소리를 만들어내는 가장 빠른 방법입니다.

### 3. 공개 펄스 카탈로그 변경

편집:

- `demos/pulsers/analyst-insights/analyst-news-ollama.pulser`

이 파일은 다음을 제어합니다:

- 어떤 prompted pulses가 존재하는지
- 각 pulse가 어떤 프롬프트 프로필을 사용하는지
- 어떤 업스트림 에이전트를 호출하는지
- 다운스트림 사용자에게 표시되는 입력 및 출력 스키마

## 이 고급 패턴이 유용한 이유

- 업스트림 뉴스 에이전트는 나중에 YFinance, ADS 또는 내부 수집기로 교체할 수 있습니다
- 분석가는 UI에 일회성 노트를 하드코딩하는 대신 프롬프트 팩(prompt pack)에 대한 소유권을 유지합니다
- 서로 다른 컨슈머는 뒤에 있는 전체 체인을 알 필요 없이 서로 다른 pulses를 사용할 수 있습니다
- 개인 에이전트는 로직이 존재하는 곳이 아니라 깔끔한 컨슈머 인터페이스가 됩니다
