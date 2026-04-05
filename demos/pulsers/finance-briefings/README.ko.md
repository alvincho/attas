# 금융 브리핑 워크플로 데모

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

## 이 데모가 보여주는 것

- Attas 소유의 `FinancialBriefingPulser`를 통해 workflow-seed pulses 및 finance briefing step pulses를 공개합니다
- 워크플로 진입 컨텍스트 펄스:
  - `prepare_finance_briefing_context`
  - `workflow_name`을 사용하여 워크플로 구분: `morning_desk_briefing`, `watchlist_check` 또는 `research_roundup`
- 공유 금융 단계 펄스:
  - `build_finance_source_bundle`
  - `build_finance_citations`
  - `build_finance_facts`
  - `build_finance_risks`
  - `build_finance_catalysts`
  - `build_finance_conflicting_evidence`
  - `build_finance_takeaways`
  - `build_finance_open_questions`
  - `build_finance_summary`
  - `assemble_finance_briefing_payload`
- 다운스트림 게시/내보내기 펄스:
  - `briefing_to_phema`
  - `notebooklm_export_pack`

## 존재 이유

MapPhemar는 pulsers와 pulses를 호출하여 다이어그램을 실행합니다. finance briefing 워크플로우는 처음에 `attas`의 단순한 Python 함수로 시작되었으나, 현재의 다이어그램은 이러한 워크플로우를 편집 가능한 단계 노드로 분해하므로, 이제 런타임은 범용 MCP 래퍼 대신 Attas 네이티브 pulser를 사용합니다.

런타임 인터페이스는 다음과 같습니다:

- [finance-briefings.pulser](./finance-briefings.pulser): `attas.pulsers.financial_briefing_pulser.FinancialBriefingPulser`를 위한 데모 구성
- [financial_briefing_pulser.py](../../../attas/pulsers/financial_briefing_pulser.py): 워크플로우 시드 및 단계 pulses를 호스팅하는 Attas 소유의 pulser 클래스
- [briefings.py](../../../attas/workflows/briefings.py): pulser에서 사용하는 공개 finance briefing 단계 헬퍼

## 런타임 가정

- Plaza: `http://127.0.0.1:8272`
- `DemoFinancialBriefingPulser`: `http://127.0.0.1:8271`

## 단일 명령 실행

저장소 루트에서:
```bash
./demos/pulsers/finance-briefings/run-demo.sh
```

이 명령은 하나의 터미널에서 로컬 Plaza와 금융 브리핑 pulser를 시작하고, 브라우저 가이드 페이지를 열며, pulser UI를 자동으로 엽니다.

런처가 터미널에만 머물기를 원하면 `DEMO_OPEN_BROWSER=0`을 설정하십시오.

## 플랫폼 빠른 시작

### macOS 및 Linux

저장소 루트에서:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/finance-briefings/run-demo.sh
```

### Windows

Ubuntu 또는 다른 Linux 배포판과 함께 WSL2를 사용하세요. WSL 내부의 저장소 루트에서:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/finance-briefings/run-demo.sh
```

브라우저 탭이 WSL에서 자동으로 열리지 않는 경우, 런처를 실행 상태로 유지하고 출력된 `guide=` URL을 Windows 브라우저에서 여십시오.

네이티브 PowerShell / 명령 프롬프트 래퍼는 아직 체크인되지 않았으므로, 현재 지원되는 Windows 경로는 WSL2입니다.

## 수동 실행

저장소 루트에서:
```bash
./demos/pulsers/finance-briefings/start-plaza.sh
./demos/pulsers/finance-briefings/start-pulser.sh
```

## 관련 다이어그램 파일

이 다이어그램들은 `demos/files/diagrams/`에 있습니다:

- `finance-morning-desk-briefing-notebooklm-diagram.json`
- `finance-watchlist-check-notebooklm-diagram.json`
- `finance-research-roundup-notebooklm-diagram.json`

각 다이어그램은 동일한 편집 가능한 구조를 따릅니다:

`Input -> Workflow Context -> Finance Step Pulses -> Assemble Briefing -> Report Phema + NotebookLM Pack -> Output`

## 현재 MapPhemar 적합성

이 워크플로우들은 새로운 노드 유형이나 스키마를 추가하지 않고도 현재의 MapPhemar 모델에 적합합니다:

- 실행 가능한 단계는 일반적인 `rectangle` 노드입니다
- 경계는 `pill`을 사용합니다
- 분기는 `branch`를 통해 계속 사용할 수 있습니다
- 아티팩트 팬아웃(fan-out)은 워크플로우 노드에서 나가는 여러 개의 에지(edge)를 통해 처리됩니다

현재 런타임 제한 사항:

- `Input`은 정확히 하나의 다운스트림 노드에 연결될 수 있으므로, 팬아웃은 `Input`에서 직접 발생하는 것이 아니라 첫 번째 실행 가능한 워크플로우 노드 이후에 발생해야 합니다

이러한 단계별 금융 워크플로우를 위해 새로운 MapPhemar 노드 유형이나 스키마 확장은 필요하지 않았습니다. 일반적인 실행 가능 노드와 Attas pulser 인터페이스만으로도 현재의 저장, 편집 및 실행에 충분합니다.
