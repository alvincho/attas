# Phemacast

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

## 에이전트 흐름

1. `CreatorAgent`가 `Phema`(콘텐츠 구조 + 바인딩)를 생성합니다.
2. `PulserAgent`가 각 바인딩 키에 대한 동적 데이터를 가져옵니다.
3. `PhemarAgent`가 펄스 데이터를 `{{binding.path}}` 템플릿에 바인딩합니다.
4. `CastrAgent`가 선택된 형식으로 시청자를 위한 최종 출력을 렌더링합니다.

지원되는 뷰어 형식:
- `json`
- `markdown`
- `text`

## 빠른 예시
```python
from phemacast import PhemacastSystem, Persona

system = PhemacastSystem()

system.register_pulse_source("summary", lambda ctx: {"value": f"Market pulse for {ctx['symbol']}"})
system.register_pulse_source("price", lambda ctx: {"value": 63890.42})

phema = system.create_phema(
    title="BTC Brief",
    prompt="Creator view",
    bindings=["price"],
    default_persona=Persona(name="analyst", tone="professional", style="short"),
)

output, trace = system.cast(
    phema_id=phema.phema_id,
    viewer_format="markdown",
    context={"symbol": "BTC"},
)

print(output)
```

## 동적 바인딩 규칙

- 템플릿 구문: `{{binding.path}}`
- 루트 `binding`은 `PulserAgent`에 의해 반환되는 펄스 키입니다
- 누락된 제공자는 casts의 탄력성을 유지하기 위해 `{ "status": "missing-provider" }`로 반환됩니다

## Phemacast의 계획된 기능

- 인간의 지능, 판단 및 구조화된 해석을 표현하는 데 중점을 둔 더 많은 `Phemar` 에이전트
- PDS, PPTX, 웹 페이지 및 멀티미디어와 같은 형식으로 `Phema`에서 출력을 생성할 수 있는 더 많은 `Castr` 에이전트
- 인간의 피드백, 런타임 효율성 및 비용을 고려한 AI 생성 `Pulse` 생성 및 정제
- `MapPhemar`에서 더 광범위한 다이어그램 지원
