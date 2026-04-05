# Attas Data Services

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

## 커버리지

현재 정규화된 데이터셋 테이블은 다음과 같습니다:

- `ads_security_master`
- `ads_daily_price`
- `ads_fundamentals`
- `ads_financial_statements`
- `ads_news`
- `ads_sec_companyfacts`
- `ads_sec_submissions`
- `ads_raw_data_collected`

디스패처(dispatcher)는 다음도 관리합니다:

- `ads_jobs`
- `ads_worker_capabilities`

구현 시 리터럴한 `ads-*` 이름 대신 `ads_` 테이블 접두사를 사용하므로, 동일한 식별자가 SQLite, Postgres 및 Supabase 기반 SQL에서 원활하게 작동합니다.

## 런타임 형태

Dispatcher:

- `prompits` 에이전트입니다
- 공유 큐와 정규화된 저장 테이블을 소유합니다
- `ads-submit-job`, `ads-get-job`, `ads-register-worker` 및 `ads-post-job-result`를 노출합니다
- 워커가 작업을 요청할 때 타입이 지정된 `JobDetail` 페이로드를 전달합니다
- 타입이 지정된 `JobResult` 페이로드를 수락하여 작업을 완료하고 수집된 행과 원시 페이로드를 영구 저장합니다

Worker:

- `prompits` 에이전트입니다
- 에이전트 메타데이터와 디스패처 기능 테이블을 통해 자신의 기능을 광고합니다
- 설정에서 `job_capabilities`를 로드하고 해당 기능 이름을 Plaza 메타데이터에 등록합니다
- 요청된 작업의 기본 실행 경로로 `JobCap` 객체를 사용합니다
- 단일 실행 또는 폴링 루프에서 실행될 수 있으며, 기본 간격은 10초입니다
- 재정의된 `process_job()` 또는 외부 핸들러 콜백을 수락합니다

Pulser:

- `phemacast` pulser입니다
- 공유 풀에서 정규화된 ADS 테이블을 읽습니다
- security master, 일일 가격, 기본적 분석, 재무제표, 뉴스 및 원시 페이로드 조회를 위한 펄스(pulses)를 노출합니다

## 파일

- `ads/agents.py`: 디스패처 및 워커 에이전트
- `ads/jobcap.py`: `JobCap` 추상화 및 callable 기반 기능 로더
- `ads/models.py`: `JobDetail` 및 `JobResult`
- `ads/pulser.py`: ADS pulser 구현
- `ads/boss.py`: boss operator UI 에이전트
- `ads/practices.py`: 디스패처 관행
- `ads/schema.py`: 공유 테이블 스키마
- `ads/iex.py`: IEX 장 마감 작업 기능
- `ads/twse.py`: 대만 증권거래소 장 마감 작업 기능
- `ads/rss_news.py`: 멀티 피드 RSS 뉴스 수집 기능
- `ads/sec.py`: SEC EDGAR 벌크 원시 데이터 가져오기 및 기업별 매핑 기능
- `ads/us_listed.py`: Nasdaq Trader 미국 상장 증권 마스터 기능
- `ads/yfinance.py`: Yahoo Finance 장 마감 작업 기능
- `ads/runtime.py`: 정규화 도우미
- `ads/configs/*.agent`: ADS 설정 예시
- `ads/sql/ads_tables.sql`: Postgres/Supabase DDL

## 로컬 예제

제공된 ADS 설정은 이제 공유 PostgreSQL 데이터베이스를 사용하는 것으로 가정합니다.
에이전트를 시작하기 전에 `POSTGRES_DSN` 또는 `DATABASE_URL`을 설정하십시오.
선택 사항으로 `public` 이외의 스키마를 사용하려면 `ADS_POSTGRES_SCHEMA`를 설정할 수 있으며,
관리형 PostgreSQL에 SSL이 필요한 경우 기본 로컬 친화적 `disable` 동작을 재정의하려면
`ADS_POSTGRES_SSLMODE`를 설정할 수 있습니다.

디스패처를 시작합니다:
```bash
python3 prompits/create_agent.py --config ads/configs/dispatcher.agent
```

워커 시작하기:
```bash
python3 prompits/create_agent.py --config ads/configs/worker.agent
```

샘플 워커 설정에는 `ads.us_listed:USListedSecJobCap`로 지원되는 라이브 `US Listed Sec to security master` 기능, `fundamentals`, `financial_statements`, `news`를 위한 모의 핸들러가 포함되어 있으며, 라이브 종가 수집을 위한 `TWSE Market EOD` (`ads.twse:TWSEMarketEODJobCap`) 및 멀티 피드 뉴스 수집을 위한 `RSS News` (`ads.rss_news:RSSNewsJobCap`), 그리고 `US Filing Bulk` (`ads.sec:USFilingBulkJobCap`), `US Filing Mapping` (`ads.sec:USFilingMappingJobCap`), `YFinance EOD` (`ads.yfinance:YFinanceEODJobCap`), `YFinance US Market EOD` (`ads.yfinance:YFinanceUSMarketEODJobCap`)를 사용합니다. `YFinance EOD`는 설치된 `yfinance` 모듈을 사용하며 별도의 API 키가 필요하지 않습니다. `YFinance US Market EOD`는 `ads_security_master`를 스캔하여 활성 `USD` 심볼을 찾고, `metadata.yfinance.eod_at`에 따라 정렬한 후, 심볼별로 해당 타임스탬프를 업데이트하며, 가장 오래된 심볼이 먼저 새로고침되도록 단일 심볼 `YFinance EOD` 작업을 큐에 추가합니다. `TWSE Market EOD`는 공식 TWSE `MI_INDEX` 일일 시세 보고서를 읽고 전체 시장 시세 테이블을 정규화된 `ads_daily_price` 행에 저장합니다. `ads_daily_price`가 비어 있는 경우, 다년 단위의 전체 시장 백필을 시도하는 대신 기본적으로 짧은 최근 기간을 부트스트랩합니다. TWSE 과거 데이터를 커버하려면 명시적인 `start_date`를 사용하십시오. `USListedSecJobCap`은 Nasdaq Trader 심볼 디렉토리 파일인 `nasdaqlisted.txt` 및 `otherlisted.txt`를 읽고, FTP 폴백 기능이 있는 웹 호스팅 `https://www.nasdaqtrader.com/dynamic/SymDir/` 복사본을 우선적으로 사용하며, 테스트 심볼을 필터링하고 현재 미국 상장 유니버스를 `ads_security_master`에 업서트합니다. `RSS News`는 구성된 SEC, CFTC 및 BLS 피드를 하나의 작업으로 가져와 정규화된 피드 항목을 `ads_news`에 저장합니다. `US Filing Bulk`는 매일 밤 SEC EDGAR을 다운로드합니다
`companyfacts.zip` 및 `submissions.zip` 아카이브에서 기업별 원시 JSON 행을 `ads_sec_companyfacts` 및 `ads_sec_submissions`에 기록하고, 선언된 SEC `User-Agent` 헤더를 전송합니다. `US Filing Mapping`은 해당 원시 SEC 테이블에서 한 회사를 읽어 submissions 메타데이터에서 심볼을 사용할 수 있는 경우 `ads_fundamentals` 및 `ads_financial_statements`로 매핑합니다.
pulser를 시작합니다:
```bash
python3 prompits/create_agent.py --config ads/configs/pulser.agent
```

boss UI를 시작합니다:
```bash
python3 prompits/create_agent.py --config ads/configs/boss.agent
```

Boss UI에는 이제 페이지 상단에 실시간 Plaza 연결 스트립,
대기 중, 할당됨, 완료 및 실패한 ADS 작업과 해당 원시 페이로드 레코드를 브라우징할 수 있는 `/monitor` 뷰,
그리고 boss 측 디스패처 기본값 및 모니터 새로 고침 기본 설정을 위한 `Settings` 페이지가 포함됩니다.

## 참고 사항
<<<LANG:ko>>>
- 제공되는 예시 설정은 `PostgresPool`을 사용하므로 dispatcher, workers, pulser, boss가 에이전트별 SQLite 파일 대신 동일한 ADS 데이터베이스를 가리킵니다.
- `PostgresPool`은 `POSTGRES_DSN`, `DATABASE_URL`, `SUPABASE_DB_URL` 또는 표준 libpq `PG*` 환경 변수에서 연결 설정을 해결합니다.
- 새로운 JobCaps가 도입될 때 `ads/configs/boss.agent`, `ads/configs/dispatcher.agent` 및 `ads/configs/worker.agent`는 일관성을 유지해야 합니다. 제공되는 설정에는 `US Listed Sec to security master`, `US Filing Bulk`, `US Filing Mapping`, `YFinance EOD`, `YFinance US Market EOD`, `TWSE Market EOD` 및 `RSS News`가 포함되어 있습니다.
- Worker 설정은 기능 이름과 `ads.examples.job_caps:mock_daily_price_cap`와 같은 호출 가능한 경로를 사용하여 `ads.job_capabilities` 항목을 선언할 수 있습니다.
- Worker 설정은 또한 `type`을 사용하여 클래스 기반 기능을 선언할 수 있습니다(예: `ads.iex:IEXEODJobCap`, `ads.rss_news:RSSNewsJobCap`, `ads.sec:USFilingBulkJobCap`, `ads.sec:USFilingMappingJobCap`, `ads.twse:TWSEMarketEODJobCap`, `ads.us_listed:USListedSecJobCap` 또는 `ads.yfinance:YFinanceEODJobCap`). 이는 dispatcher 영속성을 위해 정규화된 행과 원시 페이로드를 반환합니다.
- Worker `ads.job_capabilities` 항목은 `disabled: true`를 지원하여 설정 항목을 삭제하지 않고도 구성된 job cap을 일시적으로 비활성화할 수 있습니다.
- Worker 설정에서 `ads.yfinance_request_cooldown_sec`(기본값 `120`)를 설정하여 Yahoo의 속도 제한 응답 후 worker가 YFinance 관련 기능을 일시적으로 광고하는 것을 중지할 수 있습니다.
- `ads/sql/ads_tables.sql`은 Postgres 또는 Supabase 배포를 위해 포함되어 있습니다.
- Dispatcher와 worker는 기본적으로 공유 로컬 직접 토큰을 사용하므로 Plaza 인증이 구성되기 전에도 원격 `UsePractice(...)` 호출이 한 대의 머신에서 작동합니다.
- 세 가지 구성 요소 모두 기존 리포지토리 컨벤션에 부합하므로, 설정 시 여전히 Plaza 등록 및 원격 `UsePractice(...)` 호출에 참여할 수 있습니다.
