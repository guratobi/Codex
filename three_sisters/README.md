# 인공지능의 세자매 (The Three Sisters)

> 낙관·비관·실용, 세 AI 자매가 그대의 현실 결정을 함께 본다. 자매들은 조언할 뿐, 선택은 그대의 몫.

현실의 고민(*이직? 구매? 설계?*)을 **평의회의 청원**으로 올리면, 세 자매가 각자의 천성으로 조언하고, 서기가 트레이드오프를 종합한다. 최종 선택은 그대가 내리고 — 그 결정은 **연대기(Chronicle)**에 새겨져 다음 비슷한 고민 때 회상된다.

> 영상 아이디어 **#5(자문 회의)** 를 **#1(중세 판타지 연출 + 연대기)** 로 게임화한 결과물.

| 자매 | 천성 | 보는 것 |
|---|---|---|
| **여명** (Dawn) | 낙관 | 기회·가능성·상승 여지 |
| **황혼** (Dusk) | 비관 | 위험·최악·잃을 것 |
| **잿불** (Ember) | 실용 | 비용·실행·다음 한 걸음 |

## 실행

```bash
python -m three_sisters
```

- **진짜 Claude로** (자매가 실제로 추론): 환경에 `ANTHROPIC_API_KEY` 를 설정하고 `pip install anthropic`.
  채팅창에 키를 붙여넣지 말 것 — 환경변수/시크릿으로 설정한다.
- **키 없이**: 그대로 실행하면 `MockLLM`(정해진 대사)으로 구조만 체험한다.

### 설정

| 환경변수 | 기본값 | 설명 |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | 있으면 진짜 Claude, 없으면 목 |
| `THREE_SISTERS_MODEL` | `claude-opus-4-8` | 비용을 줄이려면 `claude-sonnet-4-6` |

연대기는 작업 디렉터리의 `chronicle.jsonl` 에 쌓인다.

## 두뇌(LLM)와 캐싱

`get_llm()` 한 곳이 백엔드를 고른다. 공용 서문(평의회 규칙)은 모든 자매·종합 호출이 공유하는 **고정 시스템 블록**이라 `prompt caching`(`cache_control`)을 건다 — 서문이 모델의 최소 캐시 길이(Opus ~4096 / Sonnet ~2048 토큰)를 넘으면 자매·결정·세션을 가로질러 캐시 적중한다. 페르소나/고민은 그 뒤에 붙어 자매별로 갈린다.

## 구조

```
three_sisters/
  llm.py        # 두뇌: Message/LLM/MockLLM/AnthropicLLM(caching)/get_llm
  sisters.py    # 세 자매 페르소나 (여명·황혼·잿불)
  council.py    # 평의회: 회상 → 세 조언 → 종합 → 인장(기록)
  chronicle.py  # 연대기: 결정 기록·태그 회상
  narrate.py    # 터미널 연출
  cli.py        # 대화 루프 (I/O 주입 가능)
```

## 테스트

```bash
python -m unittest discover -v   # MockLLM 기반, 네트워크/키 불필요
```
