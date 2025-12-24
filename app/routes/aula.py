import secrets
from datetime import datetime, timedelta
from typing import Optional, Set

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, Response, RedirectResponse

from app.services.qr import gerar_qr_png
from app.services.sheets import registrar_presenca

router = APIRouter(tags=["Aula"])

DISCIPLINA = "Fundações (CV721A)"
TURMA = "Engenharia Civil FEC – 2026"
TTL_MIN = int(__import__("os").getenv("QR_TTL_MIN", "3"))

class AulaState:
    def __init__(self):
        self.token: Optional[str] = None
        self.expira_em: Optional[datetime] = None
        self.presentes: Set[str] = set()

    def iniciar(self):
        self.token = secrets.token_urlsafe(16)
        self.expira_em = datetime.now() + timedelta(minutes=TTL_MIN)
        self.presentes.clear()

    def encerrar(self):
        self.token = None
        self.expira_em = None
        self.presentes.clear()

    def ativa(self) -> bool:
        return bool(self.token and self.expira_em and datetime.now() <= self.expira_em)

STATE = AulaState()


def base_url(request: Request) -> str:
    # Render: use BASE_URL se existir; local: usa host
    import os
    BASE_URL = os.getenv("BASE_URL", "").rstrip("/")
    if BASE_URL:
        return BASE_URL
    scheme = request.headers.get("x-forwarded-proto", "http")
    host = request.headers.get("host") or "localhost"
    return f"{scheme}://{host}".rstrip("/")


@router.get("/", response_class=HTMLResponse)
def painel_professor(request: Request):
    return request.app.state.templates.TemplateResponse(
        "aula_hoje.html",
        {
            "request": request,
            "disciplina": DISCIPLINA,
            "turma": TURMA,
            "ttl_min": TTL_MIN,
            "token": STATE.token,
            "expira_em": STATE.expira_em,
            "ativa": STATE.ativa(),
            "qtd_presentes": len(STATE.presentes),
        },
    )


@router.post("/aula/iniciar")
def iniciar_aula():
    STATE.iniciar()
    # redireciona direto para projeção
    return RedirectResponse(url="/projecao", status_code=303)


@router.post("/aula/encerrar")
def encerrar_aula():
    STATE.encerrar()
    return RedirectResponse(url="/", status_code=303)

@router.post("/aula/renovar")
def renovar_aula():
    STATE.iniciar()
    return {"ok": True, "expira_em": STATE.expira_em.isoformat() if STATE.expira_em else None}


@router.get("/projecao", response_class=HTMLResponse)
def projecao(request: Request):
    # Se ainda não iniciou aula, manda para o painel
    if not STATE.token:
        return RedirectResponse(url="/", status_code=303)

    return request.app.state.templates.TemplateResponse(
        "projecao.html",
        {
            "request": request,
            "disciplina": DISCIPLINA,
            "turma": TURMA,
            "ativa": STATE.ativa(),
            "expira_em": STATE.expira_em,
            "qtd_presentes": len(STATE.presentes),
        },
    )


@router.get("/qr.png")
def qr_png(request: Request):
    if not STATE.token:
        return Response(status_code=404, content="QR ainda não gerado.", media_type="text/plain; charset=utf-8")

    url_checkin = f"{base_url(request)}/checkin/{STATE.token}"
    png = gerar_qr_png(url_checkin)
    return Response(content=png, media_type="image/png")


@router.get("/status")
def status():
    # endpoint para a tela de projeção atualizar contador/timer via JS
    return {
        "token_ativo": bool(STATE.token),
        "ativa": STATE.ativa(),
        "expira_em": STATE.expira_em.isoformat() if STATE.expira_em else None,
        "qtd_presentes": len(STATE.presentes),
        "ttl_min": TTL_MIN,
    }


@router.get("/checkin/{token}", response_class=HTMLResponse)
def checkin_form(token: str):
    if not STATE.ativa() or token != STATE.token:
        return HTMLResponse("<h3>QR inválido ou expirado.</h3>", status_code=401)

    return HTMLResponse("""
        <h2 style="font-family:system-ui">Registro de Presença</h2>
        <form method="post">
            <input name="ra" placeholder="RA" required style="font-size:18px;padding:12px;width:100%;max-width:420px"><br><br>
            <input name="nome" placeholder="Nome completo" required style="font-size:18px;padding:12px;width:100%;max-width:420px"><br><br>
            <button type="submit" style="font-size:18px;padding:12px 18px">Confirmar presença</button>
        </form>
    """)


@router.post("/checkin/{token}", response_class=HTMLResponse)
def checkin_submit(token: str, ra: str = Form(...), nome: str = Form(...)):
    if not STATE.ativa() or token != STATE.token:
        return HTMLResponse("QR inválido ou expirado.", status_code=401)

    ra = ra.strip()
    nome = nome.strip()

    if ra in STATE.presentes:
        return HTMLResponse("<h3>Presença já registrada.</h3>")

    registrar_presenca(ra, nome)
    STATE.presentes.add(ra)

    return HTMLResponse("<h3>Presença registrada com sucesso!</h3>")
