# Phemacast 개인 에이전트

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

## 문서

- [상세 사용자 가이드](./docs/user_guide.md)
- [현재 기능 목록](./docs/current_features.md)

이 패키지는 동일한 로컬 퍼스트(local-first) 구조를 유지합니다:

- FastAPI가 HTML 셸과 JSON API를 제공합니다.
- React가 대화형 클라이언트 UI를 담당합니다.
- Plaza 카탈로그 및 Pulser 실행은 여전히 백엔드 프록시 경로를 통해 흐릅니다.
- 모의(Mock) 대시보드 데이터는 초기 제품 개발을 위해 계속 사용할 수 있습니다.
- 현재 라이브 런타임은 `static/personal_agent.jsx`에서 제공되므로, 프론트엔드 번들을 기다릴 필요 없이 초기 개발 단계에서 즉시 재빌드가 작동합니다.

## 패키지 레이아웃

- `app.py`: FastAPI 엔트리포인트 및 라우트
- `data.py`: 대시보드 스냅샷 액세스
- `plaza.py`: Plaza 카탈로그 및 pulser 프록시 헬퍼
- `templates/index.html`: React 앱을 부트스트랩하는 HTML 쉘
- `static/`: FastAPI에서 제공하는 라이브 JSX 런타임 및 CSS
- `ui/`: 향후 React + TypeScript + Vite 소스 스캐폴드
- `docs/current_features.md`: 레거시 프로토타입에서 캡처된 전체 기능 인벤토리

## 로컬에서 실행

저장소 루트에서:
```bash
uvicorn phemacast.personal_agent.app:app --reload --port 8041
```

라이브 앱은 `static/personal_agent.jsx`에서 직접 실행됩니다.

`ui/` 디렉토리는 나중에 번들 빌드로 승격시키기 위해 의도적으로 준비되었습니다. 라이브 런타임에 영향을 주지 않고 해당 스캐폴드를 실험해보고 싶다면, `phemacast/personal_agent/ui` 내부에서 다음을 실행할 수 있습니다:
```bash
npm install
npm run build
```

결과는 `phemacast/personal_agent/ui/dist`에 출력됩니다.

그 다음 `http://127.0.0.1:8041`을 여세요.
