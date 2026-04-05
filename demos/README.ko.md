# 공개 데모 가이드

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

## 여기서 시작하세요

가장 먼저 시도해 볼 데모를 선택한다면, 다음 순서대로 사용하세요:

1. [`hello-plaza`](./hello-plaza/README.md): 가장 가벼운 멀티 에이전트 디스커버리 데모.
2. [`pulsers`](./pulsers/README.md): 파일 저장소, YFinance, LLM 및 ADS pulsers에 집중된 데모.
3. [`personal-research-workbench`](./personal-research-workbench/README.md): 가장 시각적인 제품 워크스루.
4. [`data-pipeline`](./data-pipeline/README.md): boss UI 및 pulser를 갖춘 로컬 SQLite 기반 ADS 파이프라인.

## 단일 명령 실행기

각 실행 가능한 demo 폴더에는 이제 하나의 터미널에서 필요한 서비스를 시작하고, 언어 선택 기능이 있는 브라우저 가이드 페이지를 열며, 주요 demo UI 페이지를 자동으로 여는 `run-demo.sh` 래퍼가 포함되어 있습니다.

브라우저 탭을 열지 않고 래퍼가 터미널에만 머물기를 원하는 경우 `DEMO_OPEN_BROWSER=0`로 설정하십시오.

## 플랫폼 퀵 스타트

### macOS 및 Linux

저장소 루트에서 가상 환경을 한 번 생성하고 요구 사항을 설치한 다음, `./demos/hello-plaza/run-demo.sh`와 같은 데모 래퍼를 실행하세요.
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/hello-plaza/run-demo.sh
```

### Windows

Ubuntu 또는 다른 Linux 배포판과 함께 WSL2를 사용하세요. WSL 내부의 저장소 루트에서 동일한 명령을 실행합니다:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/hello-plaza/run-demo.sh
```

브라우저 탭이 WSL에서 자동으로 열리지 않는 경우, 런처를 계속 실행 상태로 두고 출력된 `guide=` URL을 Windows 브라우저에서 여십시오.

네이티브 PowerShell / Command Prompt 래퍼는 아직 포함되지 않았으므로, 현재 지원되는 Windows 경로는 WSL2입니다.

## 공용 설정

저장소 루트에서:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

대부분의 데모는 몇 가지 장시간 실행되는 프로세스를 시작하므로, 보통 2~4개의 터미널 창을 열어두는 것이 좋습니다.

이 데모 폴더들은 런타임 상태를 `demos/.../storage/`에 기록합니다. 해당 상태는 git에서 무시되므로 자유롭게 실험할 수 있습니다.

## 데모 카탈로그


### [`hello-plaza`](./hello-plaza/README.md)

- 대상: 초보 개발자
- 런타임: Plaza + worker + 브라우저용 사용자 에이전트
- 외부 서비스: 없음
- 증명 내용: 에이전트 등록, 발견 및 간단한 브라우저 UI

### [`pulsers`](./pulsers/ README.md)

- 대상: 작고 직접적인 pulser 예제를 원하는 개발자
- 런타임: 소규모 Plaza + pulser 스택, 그리고 SQLite 파이프라인을 재사용하는 ADS pulser 가이드
- 외부 서비스: 파일 저장용 없음, YFinance 및 OpenAI를 위한 외부 인터넷, Ollama를 위한 로컬 Ollama 데몬
- 증명 내용: 독립형 pulser 패키징, 테스트, 제공자별 pulse 동작, 분석가가 자신만의 구조화되거나 프롬프트 기반의 인사이트 pulse를 게시하는 방법, 그리고 소비자 관점에서 개인 에이전트 내에서 해당 pulse가 어떻게 보이는지

### [`personal-research-workbench`](./personal-research-workbench/README.md)

- 대상: 더 강력한 제품 데모를 원하는 사람
- 런타임: React/FastAPI 워크벤치 + 로컬 Plaza + 로컬 파일 저장 pulser + 선택적 YFinance pulser + 선택적 technical-analysis pulser + 시드된 다이어그램 저장소
- 외부 서비스: 저장 흐름용 없음, YFinance 차트 흐름 및 실시간 OHLC-to-RSI 다이어그램 흐름을 위한 외부 인터넷
- 증명 내용: 워크스페이스, 레이아웃, Plaza 브라우징, 차트 렌더링 및 더 풍부한 UI를 통한 다이어그램 기반 pulser 실행

### [`data-pipeline`](./data-pipeline/README.md)

- 대상: 오케스트레이션 및 정규화된 데이터 흐름을 평가하는 개발자
- 런타임: ADS dispatcher + worker + pulser + boss UI
- 외부 서비스: 데모 설정에는 없음
- 증명 내용: 큐에 대기 중인 작업, worker 실행, 정규화된 저장, pulser를 통한 재노출, 그리고 자체 데이터 소스를 연결하는 경로

## 공개 호스팅용

이 데모들은 로컬 실행이 성공한 후 쉽게 셀프 호스팅할 수 있도록 설계되었습니다. 공개적으로 게시하는 경우, 가장 안전한 기본 설정은 다음과 같습니다:

- 호스팅된 데모를 읽기 전용으로 만들거나 일정에 따라 재설정합니다
- 첫 번째 공개 버전에서는 API 기반 또는 유료 통합 기능을 꺼두세요
- 사용자가 직접 fork할 수 있도록 데모에서 사용되는 설정 파일을 안내합니다
- live URL 옆에 demo README의 정확한 로컬 명령어를 포함하세요
