# Prompits 예제 설정

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

## 파일

- `plaza.agent`: 로컬 `FileSystemPool`이 포함된 Plaza
- `worker.agent`: Plaza에 자동으로 등록되는 기본 `StandbyAgent`
- `user.agent`: Plaza 브라우저 UI를 노출하는 `UserAgent`

## 실행 순서

저장소 루트에서:
```bash
python3 prompits/create_agent.py --config prompits/examples/plaza.agent
python3 prompits/create_agent.py --config prompits/examples/worker.agent
python3 prompits/create_agent.py --config prompits/examples/user.agent
```

그 다음 `http://127.0.0.1:8214/`를 방문하세요.

## 저장

예제 설정은 로컬 상태를 다음 위치에 기록합니다:
```text
prompits/examples/storage/
```

해당 디렉토리는 `FileSystemPool`에 의해 자동으로 생성됩니다.
