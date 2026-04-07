# 데모 다이어그램 라이브러리

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

## 플랫폼 참고 사항

이 폴더에는 JSON 에셋이 포함되어 있으며, 독립 실행형 런처가 아닙니다.

### macOS 및 Linux

먼저 쌍으로 된 데모 중 하나를 실행한 다음, 이 파일들을 MapPhemar 또는 Personal Agent로 로드하십시오:
```bash
./demos/personal-research-workbench/run-demo.sh
```

다음과 같이 실행할 수도 있습니다:
```bash
./demos/pulsers/analyst-insights/run-demo.sh
./demos/pulsers/finance-briefings/run-demo.sh
```

### Windows

쌍으로 된 demo 런처에 대해 네이티브 Windows Python 환경을 사용하세요. 예: `py -3 -m scripts.demo_launcher analyst-insights` 및 `py -3 -m scripts.demo_launcher finance-briefings`. 스택이 실행된 후 탭이 자동으로 열리지 않으면 출력된 `guide=` URL을 Windows 브라우저에서 여십시오.

## 이 폴더에 포함된 내용

두 가지 그룹의 예시가 있습니다:

- 기술적 분석 다이어그램: OHLC 시장 데이터를 지표 시리즈로 변환합니다
- LLM 중심의 분석가 다이어그램: 가공되지 않은 시장 뉴스를 구조화된 연구 노트로 변환합니다
- 금융 워크플로우 다이어그램: 정규화된 연구 입력을 브리핑, 출판 및 NotebookLM 내보내기 번들로 변환합니다

## 이 폴더의 파일

### 기술적 분석

- `ohlc-to-sma-20-diagram.json`: `입력 -> OHLC 봉 -> SMA 20 -> 출력`
- `ohlc-to-ema-50-diagram.json`: `입력 -> OHLC 봉 -> EMA 50 -> 출력`
- `ohlc-to-macd-histogram-diagram.json`: `입력 -> OHLC 봉 -> MACD 히스토그램 -> 출력`
- `ohlc-to-bollinger-bandwidth-diagram.json`: `입력 -> OHLC 봉 -> 볼린저 밴드 폭 -> 출력`
- `ohlc-to-adx-14-diagram.json`: `입력 -> OHLC 봉 -> ADX 14 -> 출력`
- `ohlc-to-obv-diagram.json`: `입력 -> OHLC 봉 -> OBV -> 출력`

### LLM / 애널리스트 리서치

- `analyst-news-desk-brief-diagram.json`: `입력 -> 뉴스 데스크 브리프 -> 출력`
- `analyst-news-monitoring-points-diagram.json`: `입력 -> 모니터링 포인트 -> 출력`
- `analyst-news-client-note-diagram.json`: `입력 -> 클라이언트 노트 -> 출력`

### 금융 워크플로우 팩

- `finance-morning-desk-briefing-notebooklm-diagram.json`: `입력 -> 모닝 컨텍스트 준비 -> 금융 단계 Pulses -> 브리핑 조립 -> Report Phema + NotebookLM 팩 -> 출력`
- `finance-watchlist-check-notebooklm-diagram.json`: `입력 -> 관심 종목 컨텍스트 준비 -> 금융 단계 Pulses -> 브리핑 조립 -> Report Phema + NotebookLM 팩 -> 출력`
- `finance-research-roundup-notebooklm-diagram.json`: `입력 -> 리서치 컨텍스트 준비 -> 금융 단계 Pulses -> 브리핑 조립 -> Report Phema + NotebookLM 팩 -> 출력`

이 세 개의 저장된 Phemas는 편집을 위해 별도로 유지되지만, 동일한 workflow-entry pulse를 공유하며 노드 `paramsText.workflow_name`을 통해 워크플로우를 구분합니다.

## 런타임 가정

이 다이어그램들은 구체적인 로컬 주소로 저장되어 있으므로, 예상되는 데모 스택을 사용할 수 있을 때 추가 편집 없이 실행할 수 있습니다.

### 기술적 분석 다이어그램

지표 다이어그램은 다음을 가정합니다:

- Plaza: `http://127.0.0.1:8011`
- `YFinancePulser`: `http://127.0.0.1:8020`
- ``TechnicalAnalysisPulser`: `http://127.0.0.1:8033`

이 다이어그램들이 참조하는 pulser 설정은 다음 위치에 있습니다:

- `attas/configs/yfinance.pulser`
- `attas/configs/ta.pulser`

### LLM / 분석가 다이어그램

LLM 지향 다이어그램은 다음을 가정합니다:

- Plaza: `http://127.0.0.1:8266`
- `DemoAnalystPromptedNewsPulser`: `http://127.0.0.1:8270`

해당 prompted analyst pulser 자체는 다음을 의존합니다:

- `news-wire.pulser`: `http://127.0.0.1:8268`
- `ollama.pulser`: `http://127.0.0.1:8269`

해당 데모 파일들은 다음 위치에 있습니다:

- `demos/pulsers/analyst-insights/`

### 금융 워크플로우 다이어그램

금융 워크플로우 다이어그램은 다음을 가정합니다:

- Plaza: `http://127.0.0.1:8266`
- `DemoFinancialBriefingPulser`: `http://127.0.0.1:8271`

해당 데모 pulser는 다음을 백엔드로 하는 Attas 소유의 `FinancialBriefingPulser`입니다:

- `demos/pulsers/finance-briefings/finance-briefings.pulser`
- `attas/pulsers/financial_briefing_pulser.py`
- `attas/workflows/briefings.py`

이 다이어그램들은 일반적인 다이어그램 기반 Phema JSON 파일이므로 MapPhemar와 임베디드된 Personal Agent MapPhemar 경로 모두에서 편집할 수 있습니다.

## 퀵스타트

### 옵션 1: 파일을 MapPhemar에 로드하기

1. MapPhemar 에디터 인스턴스를 엽니다.
2. 이 폴더에 있는 JSON 파일 중 하나를 로드합니다.
3. 저장된 `plazaUrl` 및 pulser 주소가 로컬 환경과 일치하는지 확인합니다.
4. 아래 샘플 페이로드 중 하나를 사용하여 `Test Run`을 실행합니다.

서비스에서 다른 포트나 이름을 사용하는 경우 다음을 수정하십시오:

- `meta.map_phemar.diagram.plazaUrl`
- 각 노드의 `pulserName`
- 각 노드의 `pulserAddress`

### 옵션 2: 시드 파일로 사용하기

이 JSON 파일들을 `phemas/` 디렉토리 아래의 모든 MapPhemar 풀에 복사하고, personal-research-workbench 데모와 동일한 방식으로 에이전트 UI를 통해 로드할 수도 있습니다.

## 샘플 입력

### 기술적 분석 다이어그램

다음과 같은 페이로드를 사용하세요:
```json
{
  "symbol": "AAPL",
  "interval": "1d",
  "start_date": "2026-01-01",
  "end_date": "2026-03-31"
}
```

예상 결과:

- `OHLC Bars` 단계에서 과거 바 시리즈를 가져옵니다
- 지표 노드에서 `values` 배열을 계산합니다
- 최종 출력은 타임스탬프/값 쌍을 반환합니다

### LLM / 분석가 다이어그램

다음과 같은 페이로드를 사용하세요:
```json
{
  "symbol": "NVDA",
  "number_of_articles": 2,
  "model": "qwen3:8b"
}
```

예상 결과:

- 프롬프트로 구동되는 analyst pulser가 원시 뉴스를 가져옵니다
- prompt pack이 해당 뉴스를 구조화된 분석가 뷰로 변환합니다
- 출력에는 `desk_note`, `monitor_now` 또는 `client_note`와 같이 바로 연구에 사용할 수 있는 필드가 포함됩니다

### 금융 워크플로우 다이어그램

다음과 같은 페이로드를 사용하세요:
```json
{
  "subject": "NVDA",
  "search_results": {
    "query": "NVDA sovereign AI demand",
    "sources": []
  },
  "fetched_documents": [],
  "watchlist": [],
  "as_of": "2026-04-04T08:00:00Z",
  "output_dir": "/tmp/notebooklm-pack",
  "include_pdf": false
}
```

예상 결과:

- 워크플로 컨텍스트 노드가 선택된 금융 워크플로를 시딩합니다
- 중간 금융 노드는 소스, 인용, 사실, 리스크, 촉매제, 충돌, 핵심 요점, 질문 및 요약 블록을 구축합니다
- 어셈블리 노드는 `attas.finance_briefing` 페이로드를 구축합니다
- 리포트 노드는 해당 페이로드를 정적 Phema으로 변환합니다
- NotebookLM 노드는 동일한 페이로드에서 내보내기 아티팩트를 생성합니다
- 최종 출력은 MapPhemar 또는 Personal Agent에서 검토할 수 있도록 세 가지 결과를 모두 병합합니다

## 현재 에디터 제한

이 금융 워크플로우는 새로운 노드 유형을 추가하지 않고도 현재의 MapPhemar 모델에 적합합니다.

여전히 두 가지 중요한 런타임 규칙이 적용됩니다:

- `Input`은 정확히 하나의 다운스트림 도형에 연결되어야 합니다
- 모든 실행 가능한 비분기 노드는 pulse와 도달 가능한 pulser를 참조해야 합니다

즉, 워크플로우의 팬아웃(fan-out)은 첫 번째 실행 가능한 노드 이후에 발생해야 하며, 다이어그램을 엔드 투 엔드로 실행하려면 워크플로우 단계가 여전히 pulser에서 호스팅되는 pulse로 노출되어야 합니다.

## 관련 데모

다이어그램을 검토하는 것뿐만 아니라 지원 서비스를 실행하려면 다음을 참조하세요:

- `demos/personal-research-workbench/README.md`: 시드된 RSI 예제가 포함된 시각적 다이어그램 워크플로
- `demos/pulsers/analyst-insights/README.md`: LLM 지향 다이어그램에서 사용되는 프롬프트된 분석가 뉴스 스택
- `demos/pulsers/llm/README.md`: OpenAI 및 Ollama를 위한 독립형 `llm_chat` pulser 데모

## 검증

이 파일들은 저장소 테스트에 포함되어 있습니다:
```bash
pytest phemacast/tests/test_demo_file_diagrams.py phemacast/tests/test_demo_llm_file_diagrams.py attas/tests/test_finance_briefing_demo_diagram.py
```

이 테스트 스위트는 저장된 다이어그램이 모의 또는 참조 pulser 흐름에 대해 엔드 투 엔드로 실행되는지 확인합니다.
