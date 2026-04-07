# Pulser 데모 세트

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

pulser 모델을 처음 배우는 경우 다음 순서대로 사용하세요:

1. [`file-storage`](./file-storage/README.md): 가장 안전한 로컬 전용 pulser 데모
2. [`analyst-insights`](./analyst-insights/README.md): 분석가가 소유하고 재사용 가능한 인사이트 뷰로 공개된 pulser
3. [`finance-briefings`](./finance-briefings/README.md): MapPhemar 및 Personal Agent가 실행할 수 있는 형식으로 게시된 금융 워크플로우 pulses
4. [`yfinance`](./yfinance/README:): 시계열 출력을 제공하는 실시간 시장 데이터 pulser
5. [`llm`](./llm/README.md): 로컬 Ollama 및 클라우드 OpenAI 채팅 pulser
6. [`ads`](./ads/README.md): SQLite 파이프라인 데모의 일부인 ADS pulser

## 단일 명령 실행기

각 실행 가능한 pulser demo 폴더에는 하나의 터미널에서 필요한 로컬 서비스를 시작하고, 언어 선택이 가능한 브라우저 가이드 페이지를 열며, 기본 demo UI 페이지를 자동으로 여는 `run-demo.sh` 래퍼가 포함되어 있습니다.

브라우저 탭을 열지 않고 래퍼를 터미널에 유지하려면 `DEMO_OPEN_BROWSER=0`을 설정하세요.

## 플랫폼 빠른 시작

### macOS 및 Linux

저장소 루트에서 가상 환경을 한 번 생성하고, 요구 사항을 설치한 다음, `./demos/pulsers/file-storage/run-demo.sh`와 같은 pulser 래퍼를 실행합니다.
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/file-storage/run-demo.sh
```

### Windows

네이티브 Windows Python 환경을 사용하십시오. PowerShell에서 저장소 루트에서 다음을 실행하십시오:
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher file-storage
```

브라우저 탭이 자동으로 열리지 않으면 런처를 계속 실행 상태로 두고, 출력된 `guide=` URL을 Windows 브라우저에서 여십시오.

## 이 데모 세트의 범위

- pulser가 Plaza에 등록되는 방법
- 브라우저 또는 `curl`을 사용하여 펄스를 테스트하는 방법
- pulser를 소규모 셀프 호스팅 서비스로 패키징하는 방법
- 다양한 pulser 제품군의 동작: 스토리지, 분석가 인사이트, 금융, LLM 및 데이터 서비스

## 공용 설정

저장소 루트에서:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

각 demo 폴더는 로컬 런타임 상태를 `demos/pulsers/.../storage/` 아래에 기록합니다.

## 데모 카탈로그

### [`file-storage`](./file-storage/README.md)

- 런타임: Plaza + `SystemPulser`
- 외부 서비스: 없음
- 증명 내용: 버킷 생성, 객체 저장/로드, 그리고 로컬 전용 pulser 상태

### [`analyst-imigths`](./analyst-insights/README.md)

- 런타임: Plaza + `PathPulser`
- 외부 서비스: 구조화된 뷰를 위한 외부 서비스 없음, 프롬프트 기반 뉴스 플로우를 위한 로컬 Ollama
- 증명 내용: 한 명의 분석가가 여러 재사용 가능한 pulses를 통해 고정된 리서치 뷰와 프롬프트 소유의 Ollama 출력을 모두 게시하고, 이를 개인 에이전트를 통해 다른 사용자에게 노출하는 방법

### [`finance-briefings`](./finance-briefings/README.md)

- 런타임: Plaza + `FinancialBriefingPulser`
- 외부 서비스: 로컬 데모 경로에는 없음
- 증명 내용: Attas 소유의 pulser가 금융 워크플로우 단계를 pulse로 주소 지정 가능한 빌딩 블록으로 게시하여, MapPhemar diagrams와 Personal Agent가 동일한 워록플로우 그래프를 저장, 편집 및 실행할 수 있는 방법

### [`yfinance`](./yfinance/README.md)

- 런타임: Plaza + `YFinancePulser`
- 외부 서비스: Yahoo Finance로의 외부 인터넷 연결
- 증명 내용: 스냅샷 pulses, OHLC 시리즈 pulses 및 차트에 적합한 출력 페이로드

### [`llm`](./llm/README.md)

- 런타임: OpenAI 또는 Ollama용으로 구성된 Plaza + `OpenAIPulser`
- 외부 서비스: 클라우드 모드의 경우 OpenAI API, 로컬 모드의 경우 로컬 Ollama 데몬
- 증명 내용: `llm_chat`, 공유 pulser 에디터 UI 및 공급자 교체가 가능한 LLM 파이프라인

### [`ads`](./ads/README.md)

- 런타임: ADS dispatcher + worker + pulser + boss UI
- 외부 서비스: SQLite 데모 경로에는 없음
- 증명 내용: 정규화된 데이터 테이블 위의 `ADSPulser` 및 사용자의 자체 수집기가 해당 pulses로 흐르는 방법
