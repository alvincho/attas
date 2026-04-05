# System Pulser 데모

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

## 이 폴더의 파일들

- `plaza.agent`: 이 pulser 데모를 위한 로컬 Plaza
- `file-storage.pulser`: 로컬 파일 시스템 기반의 스토리지 pulser
- `start-plaza.sh`: Plaza 실행
- `start-pulser.sh`: pulser 실행
- `run-demo.sh`: 하나의 터미널에서 전체 데모를 실행하고 브라우저 가이드와 pulser UI를 엽니다

## 단일 명령 실행

저장소 루트에서:
```bash
./demos/pulsers/file-storage/run-demo.sh
```

이 명령은 하나의 터미널에서 Plaza 및 `SystemPulser`를 시작하고, 브라우저 가이드 페이지를 열며, pulser UI를 자동으로 엽니다.

런처가 터미널에만 유지되기를 원하는 경우 `DEMO_OPEN_BROWSER=0`을 설정하십시오.

## 플랫폼 퀵 스타트

### macOS 및 Linux

저장소 루트에서:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/file-storage/run-demo.sh
```

### Windows

Ubuntu 또는 다른 Linux 배포판과 함께 WSL2를 사용하세요. WSL 내부의 저장소 루트에서:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/file-storage/run-demo.sh
```

브라우저 탭이 WSL에서 자동으로 열리지 않는 경우, 런처를 계속 실행 상태로 두고 출력된 `guide=` URL을 Windows 브라우저에서 여십시오.

네이티브 PowerShell / Command Prompt 래퍼는 아직 포함되지 않았으므로, 현재 지원되는 Windows 경로는 WSL2입니다.

## 빠른 시작

저장소 루트에서 두 개의 터미널을 엽니다.

### 터미널 1: Plaza 시작
```bash
./demos/pulsers/file-storage/start-plaza.sh
```

예상 결과:

- Plaza가 `http://127.0.0.1:8256`에서 시작됩니다

### 터미널 2: pulser 시작
```bash
./demos/pulsers/file-storage/start-pulser.sh
```

예상 결과:

- pulser가 `http://127.0.0.1:8257`에서 시작됩니다
- `http://127.0.0.1:8256`에 있는 Plaza에 자신을 등록합니다

## 브라우저에서 시도해 보기

열기:

- `http://127.0.0.1:8257/`

그런 다음 다음의 pulses를 순서대로 테스트하세요:

1. `bucket_create`
2. `object_save`
3. `object_load`
4. `list_bucket`

`bucket_create`에 권장되는 파라미터:
```json
{
  "bucket_name": "demo-assets",
  "visibility": "public"
}
```

`object_save`에 권장되는 매개변수:
```json
{
  "bucket_name": "demo-assets",
  "object_key": "notes/hello.txt",
  "text": "hello from the system pulser demo"
}
```

`object_load`에 권장되는 매개변수:
```json
{
  "bucket_name": "demo-assets",
  "object_key": "notes/hello.txt"
}
```

## Curl로 테스트하기

버킷을 생성합니다:
```bash
curl -sS http://127.0.0.1:8257/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"bucket_create","params":{"bucket_name":"demo-assets","visibility":"public"}}'
```

객체 저장하기:
```bash
curl -sS http://127.0.0.1:8257/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"object_save","params":{"bucket_name":"demo-assets","object_key":"notes/hello.txt","text":"hello from curl"}}'
```

다시 불러오기:
```bash
curl -sS http://127.0.0.1:8257/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"object_load","params":{"bucket_name":"demo-assets","object_key":"notes/hello.txt"}}'
```

## 주요 특징

- 이 pulser는 완전히 로컬에서 실행되며 클라우드 자격 증명이 필요하지 않습니다
- 페이로드(payloads)는 매우 간단하여 추가 도구 없이도 이해할 수 있습니다
- 스토리지 백엔드는 나중에 파일 시스템에서 다른 제공업체로 교체할 수 있으며, pulse 인터페이스의 안정성을 유지합니다

## 직접 만들기

사용자 정의를 원하는 경우:

1. `file-storage.pulser`를 복사합니다
2. 포트와 스토리지 `root_path`를 변경합니다
3. workbench 및 기존 예제와 호환성을 유지하려면 동일한 pulse surface를 유지하십시오
