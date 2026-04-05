# ADS Pulser 데모

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

## 이 데모의 범위

- `ADSPulser`가 정규화된 ADS 테이블 위에 어떻게 구축되는지
- 디스패처(dispatcher) 및 워커(worker)의 활동이 어떻게 pulser에서 볼 수 있는 데이터로 변환되는지
- 사용자 정의 컬렉터(collectors)가 어떻게 ADS 테이블에 데이터를 저장하고 기존의 pulses를 통해 표시될 수 있는지

## 설정

다음의 퀵스타트를 참조하세요:

- [`../../data-pipeline/README.md`](../../data-pipeline/README.md)

또는 저장소 루트에서 pulser에 집중된 단일 명령 래퍼를 사용하세요:
```bash
./demos/pulsers/ads/run-demo.sh
```

이 래퍼는 `data-pipeline`과 동일한 SQLite ADS 스택을 실행하지만, pulser-first 단계별 안내에 집중된 브라우저 가이드와 탭을 엽니다.

다음이 시작됩니다:

1. ADS dispatcher
2. ADS worker
3. ADS pulser
4. boss UI

## 플랫폼 빠른 시작

### macOS 및 Linux

저장소 루트에서:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/ads/run-demo.sh
```

### Windows

Ubuntu 또는 다른 Linux 배포판과 함께 WSL2를 사용하세요. WSL 내부의 저장소 루트에서:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/ads/run-demo.sh
```

브라우저 탭이 WSL에서 자동으로 열리지 않는 경우, 런처를 계속 실행 상태로 두고 출력된 `guide=` URL을 Windows 브라우저에서 여십시오.

네이티브 PowerShell / Command Prompt 래퍼는 아직 체크인되지 않았으므로, 현재 지원되는 Windows 경로는 WSL2입니다.

## 첫 Pulser 확인

샘플 작업이 완료되면 다음을 여세요:

- `http://127.0.0.1:9062/`

그런 다음 테스트합니다:

1. `{"symbol":"AAPL","limit":1}`를 사용한 `security_master_lookup`
2. `{"symbol":"AAPL","limit":5}`를 사용한 `daily_price_history`
3. `{"symbol":"AAPL"}`를 사용한 `company_profile`
4. `{"symbol":"AAPL","number_of_articles":3}`를 사용한 `news_article`

## ADS가 다른 이유

다른 pulser 데모는 대부분 라이브 제공업체 또는 로컬 스토리지 백엔드에서 직접 읽어옵니다.

`ADSPulser`는 대신 ADS 파이프라인에 의해 작성된 정규화된 테이블에서 읽어옵니다:

- workers가 소스 데이터를 수집하거나 변환합니다
- dispatcher가 정규화된 행을 영구 저장합니다
- `ADSPulser`는 해당 행을 쿼리 가능한 pulses로 노출합니다

이로 인해 사용자 정의 소스 어댑터를 추가하는 방법을 설명하기에 가장 적합한 데모가 됩니다.

## 자신만의 소스 추가하기

상세한 단계별 안내는 다음에서 확인할 수 있습니다:

- [`../../data-pipeline/README.md`](../../data-pipeline/README.md)

여기에 있는 사용자 정의 예제를 사용하세요:

- [`../../../ads/examples/custom_sources.py`](../../../ads/examples/custom_sources.py)

이 예제들은 사용자 정의 수집기가 다음과 같은 곳에 데이터를 작성하는 방법을 보여줍니다:

- `ads_news` (`news_article`을 통해 사용 가능)
- `ads_daily_price` (`daily_price_history`를 통해 사용 가능)
