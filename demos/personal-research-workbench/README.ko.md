# 개인 연구 워크벤치

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

- 로컬에서 실행되는 개인용 워크벤치 UI
- 워크벤치가 탐색할 수 있는 Plaza
- 실제 실행 가능한 펄스(pulses)를 포함한 로컬 및 라이브 데이터 pulser
- 시장 데이터를 계산된 지표 시리즈로 변환하는 다이어그램 우선의 `Test Run` 흐름
- 완성도 높은 데모에서 셀프 호스팅 인스턴스로 이어지는 경로

## 이 폴더의 파일

- `plaza.agent`: 이 데모 전용으로 사용되는 로컬 Plaza
- `file-storage.pulser`: 파일 시스템을 기반으로 하는 로컬 pulser
- `yfinance.pulser`: `yfinance` Python 모듈을 기반으로 하는 선택 사항인 시장 데이터 pulser
- `technical-analysis.pulser`: OHLC 데이터에서 RSI를 계산하는 선택 사항인 경로 pulser
- `map_phemar.phemar`: 내장된 다이어그램 에디터에서 사용하는 데모용 로컬 MapPhemar 설정
- `map_phemar_pool/`: 즉시 실행 가능한 OHLC-to-RSI 맵이 포함된 시드된 다이어그램 저장소
- `start-plaza.sh`: 데모 Plaza 실행
- `start-file-storage-pulser.sh`: pulser 실행
- `start-yfinance-pulser.sh`: YFinance pulser 실행
- `start-technical-analysis-pulser.sh`: 기술 분석 pulser 실행
- `start-workbench.sh`: React/FastAPI 워크벤치 실행

모든 런타임 상태는 `demos/personal-research-workbench/storage/`에 기록됩니다. 런처는 내장된 다이어그램 에디터가 이 폴더의 시드된 `map_phemar.phelar` 및 `map_phemar_pool/` 파일을 가리키도록 합니다.

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
./demos/personal-research-workbench/run-demo.sh
```

이 명령은 하나의 터미널에서 workbench 스택을 시작하고, 브라우저 가이드 페이지를 열며, 메인 workbench UI와 핵심 워크스루에 사용되는 임베디드 `MapPhemar` 경로를 모두 엽니다.

런처가 터미널에만 머물기를 원하면 `DEMO_OPEN_BROWSER=0`로 설정하세요.

## 플랫폼 빠른 시작

### macOS 및 Linux

저장소 루트에서:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/personal-research-workbench/run-demo.sh
```

### Windows

네이티브 Windows Python 환경을 사용하세요. PowerShell에서 저장소 루트에서 다음을 실행합니다:
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher personal-research-workbench
```

브라우저 탭이 자동으로 열리지 않으면 런처를 계속 실행 상태로 두고, 출력된 `guide=` URL을 Windows 브라우저에서 여십시오.

## 빠른 시작

YFinance 차트 흐름과 다이어그램 테스트 실행 흐름을 포함한 전체 데모를 원하시면 저장소 루트에서 터미널 5개를 여십시오.

### 터미널 1: 로컬 Plaza 시작하기

```bash
./demos/personal-research-workbench/start-plaza.sh
```

예상 결과:

- Plaza가 `http://127.0.0.1:8241`에서 시작됩니다

### 터미널 2: 로컬 파일 저장 pulser 시작
```bash
./demos/personal-research-workbench/start-file-storage-pulser.sh
```

예상 결과:

- pulser가 `http://127.0.0.1:8242`에서 시작됩니다
- Terminal 1에서 Plaza에 자신을 등록합니다

### Terminal 3: YFinance pulser 시작
```bash
./demos/personal-research-workbench/start-yfinance-pulser.sh
```

예상 결과:

- pulser가 `http://127.0.0.1:8243`에서 시작됩니다
- Terminal 1에서 Plaza에 자신을 등록합니다

참고:

- 이 단계에는 외부 인터넷 접속이 필요합니다. pulser가 `yfinance` 모듈을 통해 Yahoo Finance에서 실시간 데이터를 가져오기 때문입니다
- Yahoo에서 가끔 요청 속도를 제한할 수 있으므로, 이 흐름은 엄격한 고정 절차라기보다는 라이브 데모로 취급하는 것이 좋습니다

### Terminal 4: 기술적 분석 pulser 시작
```bash
./demos/personal-research-workbench/start-technical-analysis-pulser.sh
```

예상 결과:

- pulser가 `http://127.0.0.1:8244`에서 시작됩니다
- Terminal 1에서 Plaza에 자신을 등록합니다

이 pulser는 들어오는 `ohlc_series`에서 `rsi`를 계산하거나, symbol, interval, date range만 제공하는 경우 demo YFinance pulser에서 OHLC bars를 가져옵니다.

### Terminal 5: 워크벤치 시작
```bash
./demos/personal-research-workbench/start-workbench.sh
```

예상 결과:

- 워크벤치가 `http://127.0.0.1:8041`에서 시작됩니다

## 첫 실행 가이드

이 데모에는 현재 세 가지 워크벤치 흐름이 있습니다:

1. file-storage pulser를 사용한 로컬 저장소 흐름
2. YFinance pulser를 사용한 실시간 시장 데이터 흐름
3. YFinance 및 technical-analysis pulsers를 사용한 다이어그램 테스트 실행 흐름

열기:

- `http://127.0.0.1:8041/`
- `http://127.0.0.1:8041/map-phemar/`

### 흐름 1: 로컬 데이터 찾아보고 저장하기

그 다음 다음의 짧은 경로를 따라 진행하세요:

1. 워크벤치에서 설정 흐름을 엽니다.
2. `Connection` 섹션으로 이동합니다.
3. 기본 Plaza URL을 `http://127.0.0.1:8241`로 설정합니다.
4. Plaza 카탈로그를 새로고침합니다.
5. 워크벤치에서 브라우저 창을 열거나 생성합니다.
6. 등록된 file-storage pulser를 선택합니다.
7. `list_bucket`, `bucket_create` 또는 `bucket_browse`와 같은 내장된 pulse 중 하나를 실행합니다.

권장되는 첫 상호작작용:

- `demo-assets`라는 이름의 공개 bucket 생성
- 해당 bucket 찾아보기
- 작은 텍스트 객체 저장
- 다시 불러오기

이를 통해 풍부한 UI, Plaza 발견, pulser 실행 및 유지되는 로컬 상태라는 완전한 루프를 경험할 수 있습니다.

### 흐름 2: YFinance pulser에서 데이터를 보고 차트 그리기

동일한 워크벤치 세션을 사용한 후 다음을 수행합니다:

1. Plaza 카탈로그를 다시 새로고침하여 YFinance pulser가 나타나게 합니다.
2. 새로운 브라우저 창을 추가하거나 기존 데이터 창을 재구성합니다.
3. `ohlc_bar_series` pulse를 선택합니다.
4. 워크벤치에서 자동으로 선택되지 않은 경우 `DemoYFinancePulser` pulser를 선택합니다.
5. `Pane Params JSON`을 열고 다음과 같은 페이로드를 사용합니다:
```json
{
  "symbol": "AAPL",
  "interval": "1d",
  "start_date": "2026-01-01",
  "end_date": "2026-03-31"
}
```

6. `Get Data`를 클릭합니다.
7. `Display Fields`에서 `ohlc_series`를 켭니다. 다른 필드가 이미 선택되어 있다면, 프리뷰가 시계열 자체를 가리키도록 해당 필드를 끕니다.
8. `Format`을 `chart`로 변경합니다.
9. `Chart Style`을 OHLC 캔들의 경우 `candle`로, 단순한 추세 보기의 경우 `line`으로 설정합니다.

확인할 내용:

- 패널이 요청된 심볼 및 날짜 범위에 대한 바 데이터를 가져옵니다
- 프리뷰가 구조화된 데이터에서 차트로 변경됩니다
- 심볼 또는 날짜 범위를 변경해도 워크벤치를 떠나지 않고 새로운 차트를 얻을 수 있습니다

권장 변형:

- `AAPL`을 `MSFT` 또는 `NVDA`로 전환합니다
- 최근 뷰를 더 타이트하게 보기 위해 날짜 범위를 단축합니다
- 동일한 `ohlc_bar_series` 응답을 사용하여 `line`과 `candle`을 비교합니다

### 흐름 3: 다이어그램을 로드하고 Test Run을 사용하여 RSI 시리즈를 계산합니다

다이어그램 에디터 경로를 엽니다:

- `http://127.0.0.1:8041/map-phemar/`

그런 다음 다음 경로를 따릅니다:

1. 다이어그램 에디터의 Plaza URL이 `http://127.0.0.1:8241`인지 확인합니다.
2. `Load Phema`를 클릭합니다.
3. `OHLC To RSI Diagram`을 선택합니다.
4. 초기 그래프를 검사합니다. `Input -> OHLC Bars -> RSI 14 -> Output`으로 표시되어야 합니다.
5. `Test Run`을 클릭합니다.
6. 다음 입력 페이로드를 사용합니다:
```json
{
  "symbol": "AAPL",
  "interval": "1d",
  "start_date": "2026-01-01",
  "end_date": "2026-03-31"
}
```

7. 맵을 실행하고 단계 출력을 확장합니다.

확인할 내용:

- `OHLC Bars` 단계가 데모 YFinance pulser를 호출하고 `ohlc_series`를 반환합니다
- `RSI 14` 단계가 해당 bars를 `window: 14`와 함께 technical-analysis pulser로 전달합니다
- 최종 `Output` 페이로드에는 `timestamp` 및 `value` 항목이 포함된 계산된 `values` 배열이 포함됩니다

시드를 로드하는 대신 처음부터 동일한 다이어그램을 다시 만들려면:

1. `OHLC Bars`라는 이름의 둥근 노드를 추가합니다.
2. `DemoYFinancePulser` 및 `ohlc_bar_series` pulse에 바인딩합니다.
3. `RSI 14`라는 이름의 둥근 노드를 추가합니다.
4. `DemoTechnicalAnalysisPulser` 및 `rsi` pulse에 바인딩합니다.
5. RSI 노드 파라미터를 다음과 같이 설정합니다:
```json
{
  "window": 14,
  "price_field": "close"
}
```

6. `Input -> OHLC Bars -> RSI 14 -> Output`를 연결합니다.
7. 엣지 매핑을 `{}`로 남겨두어 일치하는 필드 이름이 자동으로 흐르도록 합니다.

## 데모 콜에서 강조해야 할 사항

- 라이브 연결을 추가하기 전에도 워크벤치에는 유용한 모의 대시보드 데이터가 로드됩니다.
- Plaza 통합은 선택 사항이며 로컬 또는 원격 환경을 가리킬 수 있습니다.
- 파일 저장 pulser는 로컬 전용이므로 공개 데모를 안전하고 재현 가능하게 만듭니다.
- YFinance pulser는 두 번째 이야기를 추가합니다. 동일한 워크벤치에서 라이브 시장 데이터를 탐색하고 이를 차트로 렌더링할 수 있습니다.
- 다이어그램 에디터는 세 번째 이야기를 추가합니다. 동일한 백엔드에서 다단계 흐름을 오케스트레이션하고 `Test Run`을 통해 각 단계를 노출할 수 있습니다.

## 자신만의 인스턴스 구축하기

세 가지 일반적인 커스텀 경로가 있습니다:

### 시드된 대시보드 및 워크스페이스 데이터 변경

워크벤치는 다음 위치에서 대시보드 스냅샷을 읽어옵니다:

- `attas/personal_agent/data.py`

자신만의 관심 목록, 메트릭 또는 워크스페이스 기본값을 교체하는 가장 빠른 방법입니다.

### 비주얼 셸 변경

현재 라이브 워크벤치 런타임은 다음에서 제공됩니다:

- `phemacast/personal_agent/static/personal_agent.jsx`
- `phemacast/personal_agent/static/personal_agent.css`

데모의 테마를 다시 설정하거나 사용자를 위해 UI를 단순화하려면 여기서 시작하세요.

### 연결된 Plaza 및 pulsers 변경

다른 백엔드를 원하는 경우:

1. `plaza.agent`, `file-storage.pulser`, `yfinance.pulser` 및 `technical-analysis.pulser`를 복사합니다
2. 서비스를 이름 변경합니다
3. 포트 및 저장 경로를 업데이트합니다
4. `map_phemar_pool/phemas/demo-ohlc-to-rsi-diagram.json`에 있는 시드 다이어그램을 편집하거나 워크벤치에서 직접 만듭니다
5. 준비가 되면 데모 pulsers를 자신의 agents로 교체합니다

## 선택적 Workbench 설정

런처 스크립트는 몇 가지 유용한 환경 변수를 지원합니다:
```bash
PHEMACAST_PERSONAL_AGENT_PORT=8055 ./demos/personal-research-workbench/start-workbench.sh
PHEMACAST_PERSONAL_AGENT_RELOAD=1 ./demos/personal-research-workbench/start-workbench.sh
```

개발 중에 FastAPI 앱을 활발하게 편집할 때는 `PHEMACAST_PERSONAL_AGENT_RELOAD=1`을 사용하십시오.

## 문제 해결

### 워크벤치는 로드되지만 Plaza 결과가 비어 있습니다

다음 세 가지를 확인하십시오:

- `http://127.0.0.1:8241/health`에 접속 가능한지
- 해당 흐름이 필요할 때 file-storage, YFinance, technical-analysis pulser 터미널이 여전히 실행 중인지
- 워크벤치의 `Connection` 설정이 `http://127.0.0.1:8241`을 가리키고 있는지

### pulser에 아직 아무런 객체가 표시되지 않습니다

이는 처음 부팅할 때 정상적인 현상입니다. 데모 스토리지 백엔드는 비어 있는 상태로 시작됩니다.

### YFinance 패널에 차트가 그려지지 않습니다

다음 사항을 확인하십시오:

- YFinance pulser 터미널이 실행 중인지
- 선택된 pulse가 `ohlc_bar_series`인지
- `Display Fields`에 `ohlc_series`가 포함되어 있는지
- `Format`이 `chart`로 설정되어 있는지
- `Chart Style`이 `line` 또는 `candle`인지

요청 자체가 실패하는 경우, 다른 심볼을 시도하거나 잠시 기다린 후 다시 실행하십시오. Yahoo에서 간헐적으로 요청 속도를 제한하거나 거부할 수 있습니다.

### 다이어그램 `Test Run`이 실패합니다

다음 사항을 확인하십시오:

- `http://127.0.0.1:8241/health`에 접속 가능한지
- YFinance pulser가 `http://127.0.0.1:8243`에서 실행 중인지
- technical-analysis pulser가 `http://127.0.0.1:8244`에서 실행 중인지
- 로드된 다이어그램이 `OHLC To RSI Diagram`인지
- 입력 페이로드에 `symbol`, `interval`, `start_date`, `end_date`가 포함되어 있는지

`OHLC Bars` 단계가 먼저 실패하는 경우, 문제는 대개 실시간 Yahoo 액세스 또는 속도 제한 때문입니다. `RSI 14` 단계가 실패하는 경우, 가장 일반적인 원인은 technical-analysis pulser가 실행 중이 아니거나 상위 OHLC 응답에 `ohlc_series`가 포함되지 않았기 때문입니다입니다.

### 데모를 초기화하고 싶습니다

가장 안전한 초기화 방법은 `root_path` 값을 새로운 폴더 이름으로 지정하거나, 데모 프로세스가 실행 중이지 않을 때 `demos/personal-research-workbench/storage/` 폴더를 삭제하는 것입니다.

## 데모 중지

각 터미널 창에서 `Ctrl-C`를 누르세요.
