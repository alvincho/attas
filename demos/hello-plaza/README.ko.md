# Hello Plaza

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

- 로컬에서 실행되는 Plaza 레지스트리
- Plaza에 자동으로 등록되는 에이전트
- 해당 Plaza에 연결된 브라우저용 사용자 UI
- 개발자가 자신의 프로젝트에 복사하여 사용할 수 있는 최소한의 설정 세트

## 이 폴더의 파일

- `plaza.agent`: Plaza 설정 데모
- `worker.agent`: worker 설정 데모
- `user.agent`: user-agent 설정 데모
- `start-plaza.sh`: Plaza 실행
- `start-worker.sh`: worker 실행
- `start-user.sh`: 브라우저용 user agent 실행

모든 런타임 상태는 `demos/hello-plaza/storage/`에 기록됩니다.

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
./demos/hello-plaza/run-demo.sh
```

이 명령은 하나의 터미널에서 Plaza, worker 및 사용자 UI를 시작하고, 브라우저 가이드 페이지를 열며, 사용자 UI를 자동으로 엽니다.

런처가 터미널에만 머물기를 원하는 경우 `DEMO_OPEN_BROWSER=0`로 설정하십시오.

## 플랫폼 빠른 시작

### macOS 및 Linux

저장소 루트에서:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/hello-plaza/run-demo.sh
```

### Windows

Ubuntu 또는 다른 Linux 배포판과 함께 WSL2를 사용하세요. WSL 내부의 저장소 루트에서:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/hello-plaza/run-demo.sh
```

브라우저 탭이 WSL에서 자동으로 열리지 않는 경우, 런처를 계속 실행 상태로 두고 출력된 `guide=` URL을 Windows 브라우저에서 여십시오.

네이티브 PowerShell / Command Prompt 래퍼는 아직 포함되지 않았으므로, 현재 지원되는 Windows 경로는 WSL2입니다.

## 빠른 시작

저장소 루트에서 세 개의 터미널을 엽니다.

### 터미널 1: Plaza 시작
```bash
./demos/hello-plaza/start-plaza.sh
```

예상 결과:

- Plaza가 `http://127.0.0.1:8211`에서 시작됩니다
- `http://127.0.0.1:8211/health`가 정상 상태를 반환합니다

### 터미널 2: 워커 시작
```bash
./demos/hello-plaza/start-worker.sh
```

예상 결과:

- worker가 `127.0.0.1:8212`에서 시작됩니다
- it은 Terminal 1에서 Plaza에 자동으로 등록됩니다

### 터미널 3: 사용자 UI 시작

```bash
./demos/hello-plaza/start-user.sh
```

예상 결과:

- 브라우저용 사용자 에이전트가 `http://127.0.0.1:8214/`에서 시작됩니다

## 스택 확인

네 번째 터미널에서, 또는 서비스가 시작된 후에:
```bash
curl http://127.0.0.1:8211/health
curl http://127.0.0.1:8214/api/plazas_status
```

확인할 내용:

- 첫 번째 명령은 정상적인 Plaza 응답을 반환합니다
- 두 번째 명령은 로컬 Plaza와 등록된 `demo-worker`를 보여줍니다

그 다음 아래 주소를 여세요:

- `http://127.0.0.1:8214/`

이것은 로컬 시연이나 화면 녹화 시 공유할 수 있는 공개 데모 URL입니다.

## 데모 콜에서 강조해야 할 사항

- Plaza는 디스커버리 레이어입니다.
- 워커(worker)는 독립적으로 시작할 수 있으며 공유 디렉토리에 여전히 나타납니다.
- 사용자용 UI는 워커에 대한 하드코딩된 지식이 필요하지 않습니다. Plaza를 통해 워커를 발견합니다.

## 자신만의 인스턴스 구축하기

이것을 자신만의 인스턴스로 변환하는 가장 간단한 방법은 다음과 같습니다.

1. `plaza.agent`, `worker.agent`, `user.agent`를 새 폴더로 복사합니다.
2. 에이전트의 이름을 변경합니다.
3. 필요한 경우 포트를 변경합니다.
4. 각 `root_path`를 자체 저장 위치로 지정합니다.
5. Plaza의 URL 또는 포트를 변경하는 경우 `worker.agent` 및 `user.agent`의 `plaza_url`을 업데이트합니다.

사용자 정의해야 할 가장 중요한 세 가지 필드는 다음과 같습니다.

- `name`: 에이전트가 자신의 정체성으로 광고하는 이름
- `port`: HTTP 서비스가 리스닝하는 위치
- `root_path`: 로컬 상태가 저장되는 위치

파일 설정이 올바르면 다음을 실행하십시오.
```bash
python3 prompits/create_agent.py --config path/to/your/plaza.agent
python3 prompits/create_agent.py --config path/to/your/worker.agent
python3 prompits/create_agent.py --config path/to/your/user.agent
```

## 문제 해결

### 포트가 이미 사용 중입니다

관련된 `.agent` 파일을 편집하여 사용 가능한 포트를 선택하세요. Plaza를 새로운 포트로 이동하는 경우, 종속된 두 설정 모두에서 `plaza_url`을 업데이트해야 합니다.

### 사용자 UI에 Plaza 디렉토리가 비어 있는 것으로 표시됩니다

다음 세 가지 사항을 확인하세요:

- Plaza가 `http://127.0.0.1:8211`에서 실행 중인지 확인
- worker 터미널이 여전히 실행 중인지 확인
- `worker.agent`가 여전히 `http://127.0.0.1:8211`을 가리키고 있는지 확인

### 새로운 데모 상태로 시작하고 싶습니다

가장 안전한 초기화 방법은 데이터를 직접 삭제하는 대신 `root_path` 값을 새로운 폴더 이름으로 지정하는 것입니다.

## 데모 중지

각 터미널 창에서 `Ctrl-C`를 누르세요.
