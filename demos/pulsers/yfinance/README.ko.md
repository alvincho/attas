# YFinance Pulser 데모

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

- `plaza.agent`: 이 데모를 위한 로컬 Plaza
- `yfinance.pulser`: `YFinancePulser`를 위한 로컬 데모 설정
- `start-plaza.sh`: Plaza 실행
- `start-pulser.sh`: pulser 실행
- `run-demo.sh`: 하나의 터미널에서 전체 데모를 실행하고 브라우저 가이드 및 pulser UI를 엽니다

## 단일 명령 실행

저장소 루트에서:
```bash
./demos/pulsers/yfinance/run-demo.sh
```

이 명령은 하나의 터미널에서 Plaza 및 `YFinancePulser`를 시작하고, 브라우저 가이드 페이지를 열며, pulser UI를 자동으로 엽니다.

런처가 터미널에만 머물기를 원하는 경우 `DEMO_OPEN_BROWSER=0`을 설정하십시오.

## 플랫폼 빠른 시작

### macOS 및 Linux

저장소 루트에서:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/yfinance/run-demo.sh
```

### Windows

Ubuntu 또는 다른 Linux 배포판과 함께 WSL2를 사용하세요. WSL 내부의 저장소 루트에서:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/yfinance/run-demo.sh
```

WSL에서 브라우저 탭이 자동으로 열리지 않는 경우, 런처를 계속 실행 상태로 두고 출력된 `guide=` URL을 Windows 브라우저에서 여십시오.

네이티브 PowerShell / Command Prompt 래퍼는 아직 포함되지 않았으므로, 현재 지원되는 Windows 경로는 WSL2입니다.

## 빠른 시작

저장소 루트에서 두 개의 터미널을 엽니다.

### 터미널 1: Plaza 시작
```bash
./demos/pulsers/yfinance/start-plaza.sh
```

예상 결과:

- Plaza가 `http://127.0.0.1:8251`에서 시작됩니다

### 터미널 2: pulser 시작
```bash
./demos/pulsers/yfinance/start-pulser.sh
```

예상 결과:

- pulser가 `http://127.0.0.1:8252`에서 시작됩니다
- `http://12rypt.0.0.1:8251`에 있는 Plaza에 자신을 등록합니다

참고:

- 이 데모는 pulser가 `yfinance`를 통해 실시간 데이터를 가져오기 때문에 외부 인터넷 접속이 필요합니다
- Yahoo Finance는 요청에 대해 속도 제한을 걸거나 간헐적으로 거부할 수 있습니다

## 브라우저에서 시도해 보세요

열기:

- `http://127.0.0.1:8252/`

추천하는 첫 번째 pulses:

1. `last_price`
2. `company_profile`
3. `ohlc_bar_series`

`last_price`에 권장되는 파라미터:
```json
{
  "symbol": "AAPL"
}
```

`ohlc_bar_series`에 권장되는 매개변수:
```json
{
  "symbol": "AAPL",
  "interval": "1d",
  "start_date": "2026-01-01",
  "end_date": "2026-03-31"
}
```

## Curl로 테스트하기

견적 요청:
```bash
curl -sS http://127.0.0.1:8252/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"last_price","params":{"symbol":"AAPL"}}'
```

OHLC 시리즈 요청:
```bash
curl -sS http://127.0.0.1:8252/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"ohlc_bar_series","params":{"symbol":"AAPL","interval":"1d","start_date":"2026-01-01","end_date":"2026-03-31"}}'
```

## 주요 사항

- 동일한 pulser가 snapshot-style 및 time-series-style pulses를 모두 제공합니다
- `ohlc_bar_series`는 workbench chart demo 및 technical-analysis path pulser와 호환됩니다
- pulse contract는 동일하게 유지되면서 나중에 내부적으로 live provider를 변경할 수 있습니다

## 나만의 버전 만들기

이 데모를 확장하려면:

1. `yfinance.pulser`를 복사합니다
2. 포트와 저장 경로를 조정합니다
3. 더 작거나 더 특화된 카탈로그를 원하는 경우 지원되는 pulse 정의를 변경하거나 추가합니다
