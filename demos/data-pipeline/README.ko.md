# 데이터 파이프라인

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

- 데이터 수집 작업을 위한 디스패처 큐
- 일치하는 기능을 찾기 위해 폴링하는 worker
- 로컬 SQLite에 저장된 정규화된 ADS 테이블
- 작업을 발행하고 모니터링하기 위한 boss UI
- 수집된 데이터를 다시 노출하는 pulser
- 제공된 live collectors를 사용자 정의 소스 어댑터로 교체할 수 있는 경로

## 이 데모가 라이브 수집기에 SQLite를 사용하는 이유

`ads/configs/`의 프로덕션 스타일 ADS 설정은 공유 PostgreSQL 배포를 대상으로 합니다.

이 데모는 라이브 수집기는 유지하지만 저장 측을 단순화합니다:

- SQLite를 사용하여 설정을 로컬로 간단하게 유지합니다
- worker와 dispatcher가 하나의 로컬 ADS 데이터베이스 파일을 공유하므로, 라이브 SEC 벌크 단계가 pulser가 읽는 데모 스토어와 호환성을 유지합니다
- 동일한 아키텍처를 여전히 확인할 수 있으므로, 개발자는 나중에 프로덕션 설정으로 전환할 수 있습니다
- 일부 작업은 공개 인터넷 소스를 호출하므로, 첫 실행 시간은 네트워크 조건 및 소스의 응답성에 따라 달라집니다

## 이 폴더의 파일

- `dispatcher.agent`: SQLite 기반 ADS dispatcher 설정
- `worker.agent`: SQLite 기반 ADS worker 설정
- `pulser.agent`: 데모 데이터 저장소를 읽는 ADS pulser
- `boss.agent`: 작업 발행을 위한 boss UI 설정
- `start-dispatcher.sh`: dispatcher 실행
- `start-worker.sh`: worker 실행
- `start-pulser.sh`: pulser 실행
- `start-boss.sh`: boss UI 실행

관련된 예제 소스 어댑터 및 live-demo 헬퍼는 다음 위치에 있습니다:

- `ads/examples/custom_sources.py`: 사용자 정의 뉴스 및 가격 피드를 위해 임포트 가능한 예제 작업 제한(job caps)
- `ads/examples/live_data_pipeline.py`: 라이브 SEC ADS 파이프라인을 위한 데모용 래퍼

모든 런타임 상태는 `demos/data-pipeline/storage/`에 기록됩니다.

## 사전 요구 사항

저장소 루트에서:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 단일 명령 실행

저장소 루트에서:
```bash
./demos/data-pipeline/run-demo.sh
```

이 명령은 하나의 터미널에서 dispatcher, worker, pulser 및 boss UI를 시작하고, 브라우저 가이드 페이지를 열며, boss plus pulser UI를 자동으로 엽니다.

런처가 터미널에만 유지되기를 원하는 경우 `DEMO_OPEN_BROWSER=0`로 설정하십시오.

## 플랫폼 퀵 스타트

### macOS 및 Linux

저장소 루트에서:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/data-pipeline/run-demo.sh
```

### Windows

Ubuntu 또는 다른 Linux 배포판과 함께 WSL2를 사용하세요. WSL 내부의 저장소 루트에서:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/data-pipeline/run-demo.sh
```

WSL에서 브라우저 탭이 자동으로 열리지 않는 경우, 런처를 계속 실행 상태로 두고 출력된 `guide=` URL을 Windows 브라우저에서 여십시오.

네이티브 PowerShell / Command Prompt 래퍼는 아직 포함되지 않았으므로, 현재 지원되는 Windows 경로는 WSL2입니다.

## 빠른 시작

저장소 루트에서 터미널 4개를 엽니다.

### 터미널 1: dispatcher 시작
```bash
./demos/data-pipeline/start-dispatcher.sh
```

예상 결과:

- dispatcher가 `http://127.0.0.1:9060`에서 시작됩니다

### 터미널 2: worker 시작
```bash
./demos/data-pipeline/start-worker.sh
```

예상 결과:

- worker가 `127.0.0.1:9061`에서 시작됩니다
- 2초마다 dispatcher를 폴링합니다

### 터미널 3: pulser 시작
```bash
./demos/data-pipeline/start-pulser.sh
```

예상 결과:

- ADS pulser가 `http://127.0.0.1:9062`에서 시작됩니다

### 터미널 4: boss UI 시작
```bash
./demos/data-pipeline/start-boss.sh
```

예상 결과:

- boss UI가 `http://127.0.0.1:9063`에서 시작됩니다

## 첫 실행 가이드

다음 주소를 여세요:

- `http://127.0.0.1:9063/`

boss UI에서 다음 작업들을 순서대로 제출하세요:

1. `security_master`
   Nasdaq Trader에서 미국 상장 유니버스를 전체 업데이트하므로 symbol 페이로드가 필요하지 않습니다.
2. `daily_price`
   `AAPL`에 대한 기본 페이로드를 사용하세요.
3. `fundamentals`
   `AAPL`에 대한 기본 페이로드를 사용하세요.
4. `financial_statements`
   `AAPL`에 대한 기본 페이로드를 사용하세요.
5. `news`
   기본 SEC, CFTC 및 BLS RSS 피드 목록을 사용하세요.

템플릿이 나타나면 기본 페이로드 템플릿을 사용하세요. `security_master`, `daily_price` 및 `news`는 보통 빠르게 완료됩니다. SEC 기반의 첫 `fundamentals` 또는 `financial_statements` 실행은 요청된 회사를 매핑하기 전에 `demos/data-pipeline/storage/sec_edgar/` 아래의 캐시된 SEC 아카이브를 업데이트하기 때문에 시간이 더 걸릴 수 있습니다.

그 다음 다음 주소를 여세요:

- `http://127.0.0.1:9062/`

이것은 동일한 데모 데이터 저장소를 위한 ADS pulser입니다. 정규화된 ADS 테이블을 pulses로 노출하며, 이는 수집/오케스트레이션에서 다운스트림 소비로 이어지는 브리지 역할을 합니다.

권장되는 첫 번째 pulser 확인 사항:

1. `{"symbol":"AAPL","limit":1}`로 `security_master_lookup` 실행
2. `{"symbol":"AAPL","limit":5}`로 `daily_price_history` 실행
3. `{"symbol":"AAPL"}`로 `company_profile` 실행
4. `{"symbol":"AAPL","statement_type":"income_statement","limit":3}`로 `financial_statements` 실행
5. `{"number_of_articles":3}`로 `news_article` 실행

이를 통해 전체 ADS 루프를 확인할 수 있습니다: boss UI가 작업을 발행하고, worker가 행을 수집하며, SQLite가 정규화된 데이터를 저장하고, `ADSPulser`가 쿼리 가능한 pulses를 통해 결과를 노출합니다.

## ADSPulster에 자신만의 데이터 소스 추가하기

중요한 멘탈 모델은 다음과 같습니다:

- 소스가 `job_capability`로서 워커에 연결됩니다
- 워커는 정규화된 행을 ADS 테이블에 기록합니다
- `ADSPulser`는 해당 테이블을 읽어 pulse를 통해 노출합니다

소스가 기존 ADS 테이블 구조 중 하나와 일치하는 경우, 일반적으로 `ADSPulser`를 전혀 변경할 필요가 없습니다.

### 가장 쉬운 방법: 기존 ADS 테이블에 쓰기

다음 테이블-to-pulse 쌍 중 하나를 사용하세요:

- `ads_security_master` -> `security_master_lookup`
- `ads_daily_price` -> `daily_price_history`
- `ads_fundamentals` -> `company_profile`
- `ads_financial_statements` -> `financial_statements`
- `ads_news` -> `news_article`
- `ads_raw_data_collected` -> `raw_collection_payload`

### 예시: 커스텀 보도 자료 피드 추가하기

리포지토리에 이제 호출 가능한 예시가 포함되어 있습니다:

- `ads/examples/custom_sources.py`

이를 데모 워커에 연결하려면 `demos/data-pipeline/worker.agent`에 capability 이름과 callable 기반의 job cap을 추가하세요.

이 capability 이름을 추가하세요:
```json
"press_release_feed"
```

이 job-capability 항목을 추가하세요:
```json
{
  "name": "press_release_feed",
  "callable": "ads.examples.custom_sources:demo_press_release_cap"
}
```

그런 다음 worker를 재시작하고 다음과 같은 payload로 boss UI에서 작업을 제출합니다:
```json
{
  "symbol": "AAPL",
  "headline": "AAPL launches a custom source demo",
  "summary": "This row came from a user-defined ADS job cap.",
  "published_at": "2026-04-02T09:30:00+00:00",
  "source_name": "UserFeed",
  "source_url": "https://example.com/user-feed"
}
```

해당 작업이 완료되면 `http://127.0.0.1:9062/`에서 Pulser UI를 열고 다음을 실행하십시오:
```json
{
  "symbol": "AAPL",
  "number_of_articles": 5
}
```

`news_article` pulse에 대해.

확인할 수 있는 내용:

- 사용자 정의 수집기가 정규화된 행을 `ads_news`에 기록합니다
- 원시 입력은 작업의 raw payload에 그대로 유지됩니다
- `ADSPulser`는 기존 `news_article` pulse를 통해 새 기사를 반환합니다

### 두 번째 예시: 커스텀 가격 피드 추가

데이터 소스가 뉴스보다 가격에 더 가깝다면, 동일한 패턴을 다음에도 적용할 수 있습니다:
```json
{
  "name": "alt_price_feed",
  "callable": "ads.examples.custom_sources:demo_alt_price_cap"
}
```

이 예제는 행을 `ads_daily_price`에 기록하므로, 결과가 `daily_price_history`를 통해 즉시 쿼리 가능해집니다.

### ADSPulser 자체를 변경해야 하는 경우

소스가 기존의 정규화된 ADS 테이블 중 하나에 깔끔하게 매핑되지 않거나 완전히 새로운 펄스 형태(pulse shape)가 필요한 경우에만 `ads/pulser.py`를 변경하십시오.

이 경우 일반적인 경로는 다음과 같습니다:

1. 새로운 정규화된 행을 위한 저장 테이블을 추가하거나 선택합니다
2. pulser 설정에 새로운 지원되는 펄스 항목을 추가합니다
3. `ADSPulser.fetch_pulse_payload()`를 확장하여 펄스가 저장된 행을 어떻게 읽고 형성할지 알 수 있도록 합니다

아직 스키마를 설계 중이라면, 먼저 원시 페이로드(raw payload)를 저장하고 `raw_collection_payload`를 통해 먼저 검사하십시오. 이렇게 하면 최종 정규화된 테이블이 어떤 모습이어야 할지 결정하는 동안 소스 통합을 계속 진행할 수 있습니다.

## 데모 콜에서 강조해야 할 사항

- 작업은 비동기적으로 큐에 추가되고 완료됩니다.
- 워커는 Boss UI와 분리되어 있습니다.
- 저장된 행은 단일 범용 blob 저장소가 아닌 정규화된 ADS 테이블에 저장됩니다.
- Pulser는 수집된 데이터 상의 두 번째 인터페이스 계층입니다.
- 새로운 소스를 도입하는 것은 일반적으로 전체 ADS 스택을 재구축하는 것이 아니라 하나의 워커 작업 제한을 추가하는 것을 의미합니다.

## 자신만의 인스턴스 구축하기

이 데모에서 시작할 수 있는 두 가지 자연스러운 업그레이드 경로가 있습니다.

### 로컬 아키텍처를 유지하되 자체 수집기로 교체하기

`worker.agent`를 편집하여 포함된 라이브 데모 job caps를 자체 job caps 또는 기타 ADS job-cap 유형으로 교체하십시오.

예시:

- `ads.examples.custom_sources:demo_press_release_cap`는 커스텀 기사 피드를 `ads_news`로 가져오는 방법을 보여줍니다
- `ads.essentials.custom_sources:demo_alt_price_cap`는 커스텀 가격 소스를 `ads_daily_price`로 가져오는 방법을 보여줍니다
- `ads/configs/worker.agent`의 프로덕션 설정은 SEC, YFinance, TWSE 및 RSS를 위한 라이브 기능이 어떻게 연결되어 있는지 보여줍니다

### SQLite에서 공유 PostgreSQL로 이동하기

로컬 데모를 통해 워크플로우가 검증되면, 다음의 프로덕션 스타일 설정과 이 데모 설정을 비교해 보십시오:

- `ads/configs/dispatcher.agent`
- `ads/configs/worker.agent`
- `ads/configs/pulser.agent`
- `ads/configs/boss.agent`

주요 차이점은 풀(pool) 정의입니다:

- 이 데모는 `SQLitePool`을 사용합니다
- 프로덕션 스타일 설정은 `PostgresPool`을 사용합니다

## 문제 해결

### 작업이 큐에 유지됩니다

다음 세 가지 사항을 확인하세요:

- 디스패처 터미널이 여전히 실행 중입니다
- 워커 터미널이 여전히 실행 중입니다
- Boss UI의 작업 기능 이름이 worker가 광고한 이름과 일치합니다

### Boss UI가 로드되지만 비어 있는 것처럼 보입니다

boss 설정이 여전히 다음을 가리키고 있는지 확인하십시오:

- `dispatcher_address = http://127.0.0.1:9060`

### 깨끗한 실행을 원하거나 오래된 모의 행을 제거해야 하는 경우

다시 시작하기 전에 데모 프로세스를 중지하고 `demos/data-pipeline/storage/`를 제거하십시오.

## 데모 중지

각 터미널 창에서 `Ctrl-C`를 누르세요.
