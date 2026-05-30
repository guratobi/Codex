"""웹 백엔드 — 브라우저에서 평의회를 연다.

FastAPI 앱이다. 키(ANTHROPIC_API_KEY)가 있으면 진짜 Claude로, 없으면 키 없이
도는 MockLLM 으로 세 자매가 답한다. 같은 인터랙티브 페이지(scene_html)를 서빙하고,
그 페이지는 /api/ask 를 먼저 부르되 백엔드가 없으면 클라이언트 목으로 폴백한다.

띄우기:
    pip install -r requirements.txt
    ANTHROPIC_API_KEY=sk-...  uvicorn three_sisters.server:app --reload
    # 키 없이 체험만:           uvicorn three_sisters.server:app --reload
그다음 http://127.0.0.1:8000 접속.

키는 서버(이 프로세스)에만 있고 브라우저로는 절대 내려가지 않는다.
"""
from .chronicle import Chronicle, Decision, derive_tags, now_iso
from .council import Council
from .llm import LLM, AnthropicLLM, get_llm
from .scene_html import render_interactive_html

DEFAULT_CHRONICLE = "chronicle.jsonl"


def create_app(llm: LLM | None = None, chronicle_path: str = DEFAULT_CHRONICLE):
    """평의회를 감싼 FastAPI 앱을 만든다. llm 을 주입하면 테스트에서 목을 쓸 수 있다."""
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel

    llm = llm or get_llm()
    council = Council(llm, Chronicle(chronicle_path))
    brain = "claude" if isinstance(llm, AnthropicLLM) else "mock"

    app = FastAPI(title="인공지능의 세자매")

    class AskBody(BaseModel):
        dilemma: str

    class SealBody(BaseModel):
        dilemma: str
        choice: str
        rationale: str = ""

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return render_interactive_html()

    @app.get("/api/health")
    def health() -> dict:
        return {"brain": brain, "model": getattr(llm, "model", None)}

    # 동기 def → FastAPI 가 스레드풀에서 실행하므로 Claude 네트워크 대기가
    # 이벤트 루프를 막지 않는다.
    @app.post("/api/ask")
    def ask(body: AskBody):
        dilemma = (body.dilemma or "").strip()
        if not dilemma:
            return JSONResponse({"error": "고민을 입력하라."}, status_code=400)
        result = council.deliberate(dilemma)
        return {
            "dilemma": result.dilemma,
            "dawn": result.counsels.get("여명", ""),
            "dusk": result.counsels.get("황혼", ""),
            "ember": result.counsels.get("잿불", ""),
            "synth": result.synthesis,
            "recalled": [{"dilemma": d.dilemma, "choice": d.choice} for d in result.recalled],
            "brain": brain,
        }

    @app.post("/api/seal")
    def seal(body: SealBody):
        dilemma = (body.dilemma or "").strip()
        choice = (body.choice or "").strip()
        if not (dilemma and choice):
            return JSONResponse({"error": "고민과 결정이 필요하다."}, status_code=400)
        council.chronicle.record(
            Decision(
                ts=now_iso(),
                dilemma=dilemma,
                choice=choice,
                rationale=(body.rationale or "").strip(),
                tags=derive_tags(dilemma),
            )
        )
        return {"ok": True}

    return app


_default_app = None


def __getattr__(name):  # PEP 562: `uvicorn three_sisters.server:app` 일 때만 기본 앱 생성
    """`from three_sisters.server import create_app` 는 fastapi 없이도 되게,
    기본 `app` 은 실제로 참조될 때(서버 실행 시)만 만든다."""
    if name == "app":
        global _default_app
        if _default_app is None:
            _default_app = create_app()
        return _default_app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
