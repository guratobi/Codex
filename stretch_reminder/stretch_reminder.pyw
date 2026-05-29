"""
목·어깨 스트레칭 알리미  (Windows 백그라운드 실행용)
----------------------------------------------------
- 평소엔 창 없이 백그라운드에서 대기 (작업표시줄에 안 보임)
- 설정한 주기마다 모든 창보다 앞에 전체화면 알림이 뜸
- '완료' 또는 '미루기(5/10/15분)' 버튼 제공
- pythonw.exe(.pyw)로 실행하면 콘솔 창도 안 뜸
- 같은 PC에서 두 번 실행해도 중복으로 뜨지 않음 (단일 인스턴스 보장)

설정값은 아래 CONFIG에서 바꾸세요.

끄고 싶을 때:
  · 알림창에서  Ctrl+Q  누르거나 우측 '종료' 버튼 클릭
  · 또는 작업 관리자(Ctrl+Shift+Esc)에서 pythonw.exe 종료
"""

import socket
import sys
import time
import tkinter as tk

# ===================== 설정 =====================
CONFIG = {
    "interval_min": 60,             # 알림 주기 (분)
    "snooze_options": [5, 10, 15],  # 미루기 버튼 (분)
}

STRETCHES = [
    {
        "title": "목 뒷근육 강화",
        "tag": "강화",
        "color": "#5fd6a8",
        "items": [
            "고개를 뒤로 천천히 떨군 뒤 그 자세로 버티기  ·  10초 × 3회",
        ],
    },
    {
        "title": "목 앞근육 늘리기",
        "tag": "스트레칭",
        "color": "#f4a261",
        "items": [
            "양손 포개 가슴 정중앙 → 고개 뒤로 젖히기  ·  15초",
            "양손 포개 좌측 쇄골 → 고개 우측으로 살짝 돌려 뒤로  ·  15초",
            "양손 포개 우측 쇄골 → 고개 좌측으로 살짝 돌려 뒤로  ·  15초",
        ],
    },
    {
        "title": "라운드숄더 스트레칭",
        "tag": "자세 교정",
        "color": "#7aa5e0",
        "items": [
            "벽 모서리에 팔꿈치 기대고 가슴 앞으로 밀어 늘리기  ·  20초 × 양쪽",
        ],
    },
]

BG = "#0f1419"
PANEL = "#1a2129"
TEXT = "#e8eef2"
MUTED = "#8a99a6"
ACCENT = "#5fd6a8"
WARM = "#f4a261"

# 중복 실행 방지용 포트 (아무도 안 쓰는 높은 번호면 됨)
SINGLE_INSTANCE_PORT = 50573
# ================================================


def lighten(hex_color, amount=0.14):
    """버튼 호버용으로 색을 살짝 밝게 만든다."""
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    r = int(r + (255 - r) * amount)
    g = int(g + (255 - g) * amount)
    b = int(b + (255 - b) * amount)
    return f"#{r:02x}{g:02x}{b:02x}"


def acquire_single_instance_lock(port=SINGLE_INSTANCE_PORT):
    """이미 실행 중이면 None, 아니면 점유한 소켓을 반환(프로세스 동안 살려둔다)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
    except OSError:
        sock.close()
        return None
    return sock


class StretchReminder:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()  # 시작 시 창 숨김 (백그라운드)
        self.alarm_window = None
        self.next_seconds = max(1, int(CONFIG["interval_min"] * 60))
        self._schedule()
        # 타이머: 별도 스레드 대신 메인 스레드에서 after 로 폴링한다.
        # (tkinter 객체는 메인 스레드에서만 안전하게 다룰 수 있음)
        self.root.after(1000, self._tick)

    def _schedule(self):
        self.target_time = time.time() + self.next_seconds

    def _tick(self):
        # 절전/최대절전에서 깨어나 시각이 한참 지나 있어도 그때 한 번만 뜬다.
        if self.alarm_window is None and time.time() >= self.target_time:
            self.show_alarm()
        self.root.after(1000, self._tick)

    def show_alarm(self):
        if self.alarm_window is not None:
            return
        w = tk.Toplevel(self.root)
        self.alarm_window = w
        w.configure(bg=BG)
        w.attributes("-fullscreen", True)
        w.attributes("-topmost", True)  # 모든 창보다 앞
        w.protocol("WM_DELETE_WINDOW",
                   lambda: self.dismiss(CONFIG["interval_min"]))
        w.deiconify()
        w.lift()
        w.focus_force()

        # ESC = 완료 / Ctrl+Q = 프로그램 완전 종료
        w.bind("<Escape>", lambda e: self.dismiss(CONFIG["interval_min"]))
        w.bind("<Control-q>", lambda e: self.quit_app())

        wrap = tk.Frame(w, bg=BG)
        wrap.pack(expand=True, fill="both", padx=60, pady=40)

        # 헤더
        tk.Label(wrap, text="🧘", font=("Segoe UI Emoji", 48), bg=BG, fg=TEXT).pack()
        tk.Label(wrap, text="스트레칭 시간이에요!",
                 font=("Malgun Gothic", 30, "bold"), bg=BG, fg=ACCENT).pack(pady=(4, 0))
        tk.Label(wrap, text="천천히, 호흡하면서. 아프면 멈추기.",
                 font=("Malgun Gothic", 13), bg=BG, fg=MUTED).pack(pady=(2, 28))

        # 카드 영역
        cards = tk.Frame(wrap, bg=BG)
        cards.pack(expand=True, fill="x")
        for i, s in enumerate(STRETCHES):
            cards.columnconfigure(i, weight=1, uniform="card")
            self._make_card(cards, s, i)

        # 버튼 영역
        btns = tk.Frame(wrap, bg=BG)
        btns.pack(pady=(34, 0))

        self._make_button(btns, "✅  완료 — 다음 알림 예약", ACCENT, "#0a1410",
                           lambda: self.dismiss(CONFIG["interval_min"])).pack(side="left", padx=8)

        for m in CONFIG["snooze_options"]:
            self._make_button(btns, f"{m}분 미루기", WARM, "#2a1605",
                              lambda mm=m: self.dismiss(mm)).pack(side="left", padx=6)

        # 완전 종료 — 실수로 누르지 않도록 우측에 눈에 안 띄게
        self._make_button(btns, "종료", PANEL, MUTED,
                          self.quit_app).pack(side="left", padx=(40, 0))

        # 막 떠오른 직후 한 번 더 최상단으로 끌어올린다(다른 topmost 창 대비).
        w.after(200, self._reassert_top)

    def _reassert_top(self):
        if self.alarm_window is not None:
            self.alarm_window.lift()
            self.alarm_window.attributes("-topmost", True)
            self.alarm_window.focus_force()

    def _make_card(self, parent, s, col):
        card = tk.Frame(parent, bg=PANEL, highlightthickness=0)
        card.grid(row=0, column=col, sticky="nsew", padx=10, pady=10)
        # 좌측 색 막대
        bar = tk.Frame(card, bg=s["color"], width=5)
        bar.pack(side="left", fill="y")
        inner = tk.Frame(card, bg=PANEL)
        inner.pack(side="left", fill="both", expand=True, padx=18, pady=18)

        tk.Label(inner, text=s["title"], font=("Malgun Gothic", 15, "bold"),
                 bg=PANEL, fg=TEXT, anchor="w").pack(anchor="w")
        tk.Label(inner, text=s["tag"], font=("Malgun Gothic", 9),
                 bg=PANEL, fg=MUTED, anchor="w").pack(anchor="w", pady=(2, 12))
        for it in s["items"]:
            row = tk.Frame(inner, bg=PANEL)
            row.pack(anchor="w", fill="x", pady=4)
            tk.Label(row, text="●", font=("Malgun Gothic", 8), bg=PANEL,
                     fg=s["color"]).pack(side="left", padx=(0, 8), anchor="n")
            tk.Label(row, text=it, font=("Malgun Gothic", 11), bg=PANEL, fg=TEXT,
                     justify="left", wraplength=260, anchor="w").pack(side="left")

    def _make_button(self, parent, text, bg, fg, cmd):
        hover = lighten(bg)
        b = tk.Button(parent, text=text, command=cmd,
                      font=("Malgun Gothic", 12, "bold"),
                      bg=bg, fg=fg, activebackground=hover, activeforeground=fg,
                      relief="flat", padx=20, pady=12, cursor="hand2", bd=0,
                      highlightthickness=0)
        # 마우스를 올리면 살짝 밝아지는 호버 효과
        b.bind("<Enter>", lambda e: b.configure(bg=hover))
        b.bind("<Leave>", lambda e: b.configure(bg=bg))
        return b

    def dismiss(self, next_min):
        if self.alarm_window is not None:
            self.alarm_window.destroy()
            self.alarm_window = None
        self.next_seconds = max(1, int(next_min * 60))
        self._schedule()

    def quit_app(self):
        """알림을 닫고 프로그램을 완전히 종료한다."""
        if self.alarm_window is not None:
            self.alarm_window.destroy()
            self.alarm_window = None
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    # 중복 실행 방지: 이미 떠 있으면 조용히 종료
    _lock = acquire_single_instance_lock()
    if _lock is None:
        sys.exit(0)
    StretchReminder().run()
