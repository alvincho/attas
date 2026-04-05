# Prompits Dispatcher

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

## 포함된 구성 요소

- `DispatcherAgent`: 큐 기반 작업 디스패처
- `DispatcherWorkerAgent`: 일치하는 작업을 폴링하고 결과를 보고하는 워커
- `DispatcherBossAgent`: 작업을 발행하고 런타임 상태를 검사하기 위한 브라우저 UI
- `JobCap`: 플러그 가능한 작업 핸들러를 위한 기능 추상화
- 공유 관행, 스키마, 런타임 헬퍼 및 예시 구성

## 내부 테이블

- `dispatcher_jobs`
- `dispatcher_worker_capabilities`
- `dispatcher_worker_history`
- `dispatcher_job_results`
- `dispatcher_raw_payloads`

worker가 구체적인 `target_table`에 대한 행을 반환하고 스키마를 제공하는 경우, dispatcher는 해당 테이블을 생성하고 영구적으로 저장할 수도 있습니다. 스키마가 제공되지 않으면 행은 `dispatcher_job_results`에 범용적으로 저장됩니다.

## 실습 방법

- `dispatcher-submit-job`
- `dispatcher-get-job`
- `dispatcher-register-worker`
- `dispatcher-post-job-result`
- `dispatcher-control-job`

## 사용 예시

dispatcher를 시작합니다:
```bash
python3 prompits/create_agent.py --config prompits/dispatcher/configs/dispatcher.agent
```

워커 시작하기:
```bash
python3 prompits/create_agent.py --config prompits/dispatcher/configs/worker.agent
```

boss UI를 시작합니다:
```bash
python3 prompits/create_agent.py --config prompits/dispatcher/configs/boss.agent
```

샘플 worker 설정은 다음의 최소 예제 기능을 사용합니다
`prompits.dispatcher.examples.job_caps`.

## 참고 사항

- 이 패키지는 기본적으로 공유 로컬 직접 토큰을 사용하므로, Plaza 인증이 구성되기 전에도 `UsePractice(...)` 호출이 로컬에서 작동합니다.
- 예제 설정은 `PostgresPool`을 사용하지만, 테스트에는 SQLite도 포함됩니다.
- 워커는 `dispatcher.job_capabilities` 설정 섹션을 통해 호출 가능하거나 클래스 기반인 기능을 광고할 수 있습니다.
