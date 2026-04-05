# Retis 금융 인텔리전스 워크스페이스

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

이 저장소는 금융 인텔리전스 시스템을 위한 멀티 에이전트 워크스페이스입니다.

자세한 내용은 [retis.ai](https://retis.ai)에서 확인할 수 있으며, Attas 제품 페이지는 [retis.ai/products/attas](https://retis.ai/products/attas)입니다.

이 저장소는 현재 서로 관련된 여러 코드베이스를 함께 담고 있습니다:

- `prompits`: HTTP 네이티브 에이전트, Plaza 탐색, 풀, 원격 practice 실행을 위한 Python 인프라
- `phemacast`: Prompits 위에 구축된 협업형 콘텐츠 파이프라인
- `attas`: 더 상위 수준의 금융 지향 에이전트 패턴과 Pulse 정의
- `ads`: 정규화된 금융 데이터셋을 더 넓은 시스템에 공급하는 데이터 서비스 및 수집 구성 요소

## 상태

이 저장소는 활발히 개발 중이며 계속해서 진화하고 있습니다. 프로젝트가 분할, 안정화 또는 더 공식적으로 패키징됨에 따라 API, 구성 형식 및 예시 흐름이 변경될 수 있습니다.

두 영역은 특히 이른 단계에 있으며, 활발히 개발되는 동안 빠르게 바뀔 수 있습니다:

- `prompits.teamwork`
- `phemacast` `BossPulser`

공개 저장소의 용도는 다음과 같습니다:

- 로컬 개발
- 평가
- 프로토타입 워크플로우
- 아키텍처 탐색

아직 완성된 제품이나 단일 명령으로 가능한 프로덕션 배포 단계는 아닙니다.

## 신규 클론 퀵스타트

완전히 새로운 체크아웃 상태에서:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
bash scripts/public_clone_smoke.sh
```

smoke 스크립트는 커밋된 repo 상태를 임시 디렉토리에 클론하고, 자체 virtualenv를 생성하며, 종속성을 설치하고, 공개용 테스트 스위트를 실행합니다. 이는 GitHub 사용자가 실제로 pull하게 될 상태와 가장 유사합니다.

대신 최신 미커밋 로컬 변경 사항을 테스트하려면 다음을 사용하십시오:
```bash
attas_smoke --worktree
```

이 모드는 커밋되지 않은 변경 사항과 무시되지 않은 추적되지 않는 파일을 포함하여 현재의 작업 트리를 임시 테스트 디렉토리로 복사합니다.

저장소 루트에서 다음을 실행할 수도 있습니다:
```bash
bash attas_smoke
```

레포지토리 트리 내의 어떤 하위 디렉터리에서도 다음을 실행할 수 있습니다:
```bash
bash "$(git rev-parse --show-toplevel)/attas_smoke"
```

이 런처는 리포지토리 루트를 찾아 동일한 스모크 테스트 흐름을 시작합니다. `attas_smoke`를 `PATH`에 있는 디렉토리에 심볼릭 링크로 연결하면, 어디에서나 재사용 가능한 명령으로 호출할 수 있으며, 리포지토리 트리 외부에서 작업할 때 선택적으로 `FINMAS_REPO_ROOT`를 설정할 수 있습니다.

## 로컬 퍼스트 퀵스타트

오늘날 가장 안전한 로컬 경로는 Prompits 예제 스택입니다. Supabase 또는 기타 프라이빗 인프라가 필요하지 않으며, 이제 기본 데스크톱 스택을 위한 단일 명령 로컬 부트스트랩 흐름을 제공합니다:
```bash
python3 -m prompits.cli up desk
```

다음이 시작됩니다:

- `http://127.0.0.1:8211`의 Plaza
- `http://127.0.0.1:8212`의 베이스라인 worker
- `http://127.0.0.1:8214/`의 브라우저용 사용자 UI

래퍼 스크립트를 사용할 수도 있습니다:
```bash
bash run_plaza_local.sh
```

유용한 후속 명령:
```bash
python3 -m prompits.cli status desk
python3 -m prompits.cli down desk
```

한 번에 하나의 서비스만 디버깅하기 위해 이전의 수동 흐름이 필요한 경우:
```bash
python3 prompits/create_agent.py --config prompits/examples/plaza.agent
python3 prompits/create_agent.py --config prompits/examples/worker.agent
python3 prompits/create_agent.py --config prompits/examples/user.agent
```

이전의 Supabase 기반 Plaza 설정을 사용하려면 `PROMPITS_AGENT_CONFIG`를
`attas/configs/plaza.agent`로 지정하고 필요한 환경 변수를 제공하십시오.

## 원격 연습 정책 및 감사

Prompits는 이제 원격 `UsePractice(...)` 호출에 대한 경량 크로스 에이전트 정책 및 감사 레이어를 지원합니다. 계약은 에이전트 구성 JSON의 최상위 수준에 존재하며 `prompits` 내부에서만 소비됩니다:
```json
{
  "remote_use_practice_policy": {
    "outbound_default": "allow",
    "inbound_default": "allow",
    "outbound": {
      "deny": [
        { "practice_id": "get_pulse_data", "target_address": "http://127.0.0.1:9999" }
      ]
    },
    "inbound": {
      "allow": [
        { "practice_id": "get_pulse_data", "caller_agent_id": "plaza" }
      ]
    }
  },
  "remote_use_practice_audit": {
    "enabled": true,
    "persist": true,
    "emit_logs": true,
    "table_name": "cross_agent_practice_audit"
  }
}
```

정책 참고 사항:

- `outbound` 규칙은 `practice_id`, `target_agent_id`, `target_name`, `target_address`, `target_role` 및 `target_pit_type`을 사용하여 대상을 일치시킵니다.
- `inbound` 규칙은 `practice_id`, `caller_agent_id`, `callee_name`, `caller_address`, `auth_mode` 및 `plaza_url`을 사용하여 호출자를 일치시킵니다.
- 거부 규칙이 우선합니다. 허용 목록이 있는 경우 원격 호출은 해당 목록과 일치해야 하며, 그렇지 않으면 `403`으로 거부됩니다.
- 감사 행은 로그에 기록되며, 에이전트에 풀(pool)이 있는 경우 요청 및 결과 이벤트 간의 상관 관계를 위해 공유된 `request_id`와 함께 구성된 감사 테이블에 추가됩니다.

## 저장소 구조
```text
attas/       Finance-oriented agent, pulse, and personal-agent work
ads/         Data-service agents, workers, and normalized dataset pipelines
docs/        Project notes and architecture documents
deploy/      Deployment helpers
mcp_servers/ Local MCP server implementations
phemacast/   Dynamic content generation pipeline
prompits/    Core multi-agent runtime and Plaza coordination layer
scripts/     Local helper scripts, including public-clone smoke checks
tests/       Cross-project tests and fixtures
```

## 오리엔테이션

- 핵심 런타임 모델은 `prompits/README.md`부터 시작하세요.
- 콘텐츠 파이프라인 레이어는 `phemacast/README.md`를 읽어보세요.
- 금융 네트워크 프레임워크 및 상위 수준 개념은 `attas/README.md`를 읽어보세요.
- 데이터 서비스 구성 요소는 `ads/README.md`를 읽어보세요.

## 컴포넌트 상태

| 영역 | 현재 공개 상태 | 비고 |
| --- | --- | --- |
| `prompits` | 가장 좋은 시작점 | Local-first 예제와 핵심 런타임이 가장 쉬운 공개 진입점입니다. `prompits.teamwork` 패키지는 아직 초기 단계이며 빠르게 변경될 수 있습니다. |
| `attas` | 초기 공개 | 핵심 개념과 사용자 에이전트 작업은 공개되어 있지만, 일부 미완성된 컴포넌트는 기본 흐름에서 의도적으로 숨겨져 있습니다. |
| `phemacast` | 초기 공개 | 핵심 파이프라인 코드는 공개되어 있습니다. 일부 보고/렌더링 컴포넌트는 아직 정리 및 안정화 작업 중입니다. `BossPulser`는 현재도 활발히 개발 중입니다. |
| `ads` | 고급 | 개발 및 연구에 유용하지만, 일부 데이터 워크플로는 추가 설정이 필요하며 첫 실행 경로가 아닙니다. |
| `deploy/` | 예제 전용 | 배포 도우미는 환경에 따라 다르며, 완성된 공개 배포 솔루션으로 취급해서는 안 됩니다. |
| `mcp_servers/` | 공개 소스 | 로컬 MCP 서버 구현은 공개 소스 트리의 일부입니다. |

## 알려진 제한 사항

- 일부 워크플로우는 여전히 선택적 환경 변수 또는 타사 서비스를 가정합니다.
- `tests/storage/`에는 유용한 피스처(fixtures)가 포함되어 있지만, 이상적인 공개 피스처 세트보다 결정론적 테스트 데이터와 더 가변적인 로컬 스타일의 상태가 혼합되어 있습니다.
- 배포 스크립트는 예시일 뿐이며, 지원되는 프로덕션 플랫폼이 아닙니다.
- 저장소는 빠르게 진화하고 있으므로 일부 구성 및 모듈 경계가 변경될 수 있습니다.

## 로드맵

단기 공개 로드맵은 `docs/ROADMAP.md`에서 추적됩니다.

계획된 `prompits` 기능에는 에이전트 간의 인증 및 권한이 부여된 `UsePractice(...)` 호출이 포함되며, 실행 전에 비용 협상 및 결제 처리가 이루어집니다.

계획된 `phemacast` 기능에는 더 풍부한 인간 지능의 `Phemar` 표현, 더 광범위한 `Castr` 출력 형식, 피드백, 효율성 및 비용을 기반으로 한 AI 생성 `Pulse` 정교화, 그리고 `MapPhemar`에서의 더 광범위한 다이어그램 지원이 포함됩니다.

계획된 `attas` 기능에는 더 협업적인 투자 및 재무 워크플로, 금융 전문가를 위해 조정된 에이전트 모델, 그리고 벤더 및 서비스 제공업체를 위한 API 엔드포인트에서 `Pulse`로의 자동 매핑이 포함됩니다.

## 공개 저장소 노트

- 비밀 정보는 커밋된 파일이 아닌 환경 변수 및 로컬 설정을 통해 제공되어야 합니다.
- 로컬 데이터베이스, 브라우저 아티팩트 및 임시 스냅샷은 의도적으로 버전 관리에서 제외되었습니다.
- 현재 코드베이스는 정교한 최종 사용자용 패키징보다는 평가, 로컬 개발 및 프로토타입 워크플로우를 대상으로 합니다.

## 기여하기

이 프로젝트는 현재 단일 주요 유지 관리자가 관리하는 공개 저장소입니다. Issue와 Pull Request는 환영하지만, 로드맵 및 병합 결정은 현재 유지 관리자가 주도합니다. 현재의 워크플로우는 `CONTRIBUTING.md`를 참조하십시오.

## 라이선스

이 저장소는 Apache License 2.0에 따라 라이선스가 부여됩니다. 전체 텍스트는 `LICENSE`를 참조하십시오.
