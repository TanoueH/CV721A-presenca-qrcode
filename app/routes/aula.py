import os
import secrets
from datetime import datetime, timedelta
from typing import Optional, Set

from fastapi import APIRouter, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, Response, RedirectResponse

from app.services.qr import gerar_qr_png
from app.services.sheets import registrar_presenca

from starlette.datastructures import URL

DISCIPLINA = "Fundações (CV721A)"
TURMA = "Engenharia Civil FEC – 2026"
TTL_MIN = int(os.getenv("QR_TTL_MIN", "3"))

# Se definido no Render, exige ?k=PROF_TOKEN nas rotas /prof
PROF_TOKEN = os.getenv("PROF_TOKEN", "").strip()

# Router do professor (tudo em /prof/...)
router = APIRouter(prefix="/prof", tags=["Professor"])

# Router público (check-in do aluno)
public_router = APIRouter(tags=["Check-in"])

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

def _check_prof_key(request: Request) -> None:
    """
    Proteção simples: exige ?k=PROF_TOKEN nas rotas do professor.
    Se PROF_TOKEN não estiver configurado, não bloqueia (modo dev).
    """
    if not PROF_TOKEN:
        return
    k = (request.query_params.get("k") or "").strip()
    if k != PROF_TOKEN:
        # Mantive simples; se preferir, trocamos por uma página HTML.
        raise HTTPException(status_code=403, detail="Acesso restrito (chave inválida).")

def base_url(request: Request) -> str:
    """
    Render: usa BASE_URL se existir; local: deriva da URL/headers preservando porta.
    """
    BASE_URL = os.getenv("BASE_URL", "").rstrip("/")
    if BASE_URL:
        return BASE_URL

    # Preferir a URL já parseada (inclui host:porta) e respeitar proxy quando existir
    url = URL(str(request.url))
    scheme = request.headers.get("x-forwarded-proto", url.scheme)
    host = request.headers.get("x-forwarded-host", request.headers.get("host", url.netloc))
    return f"{scheme}://{host}".rstrip("/")

# =========================
# PROFESSOR (/prof)
# =========================
@router.get("/", response_class=HTMLResponse)
def painel_professor(request: Request):
    _check_prof_key(request)
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
            "prof_k": request.query_params.get("k", ""),
        },
    )

@router.post("/aula/iniciar")
def iniciar_aula(request: Request):
    _check_prof_key(request)
    STATE.iniciar()
    k = request.query_params.get("k", "")
    return RedirectResponse(url=f"/prof/projecao?k={k}", status_code=303)

@router.post("/aula/encerrar")
def encerrar_aula(request: Request):
    _check_prof_key(request)
    STATE.encerrar()
    k = request.query_params.get("k", "")
    return RedirectResponse(url=f"/prof/?k={k}", status_code=303)


@router.post("/aula/renovar")
def renovar_aula(request: Request):
    _check_prof_key(request)
    STATE.iniciar()
    return {
        "ok": True,
        "expira_em": STATE.expira_em.isoformat() if STATE.expira_em else None,
        "expira_epoch_ms": int(STATE.expira_em.timestamp() * 1000) if STATE.expira_em else None,
        "ttl_min": TTL_MIN,
    }


@router.get("/projecao", response_class=HTMLResponse)
def projecao(request: Request):
    _check_prof_key(request)

    if not STATE.token:
        k = request.query_params.get("k", "")
        return RedirectResponse(url=f"/prof/?k={k}", status_code=303)

    return request.app.state.templates.TemplateResponse(
        "projecao.html",
        {
            "request": request,
            "disciplina": DISCIPLINA,
            "turma": TURMA,
            "ativa": STATE.ativa(),
            "expira_em": STATE.expira_em,
            "qtd_presentes": len(STATE.presentes),
            "prof_k": request.query_params.get("k", ""),
        },
    )


@router.get("/qr.png")
def qr_png(request: Request):
    _check_prof_key(request)

    if not STATE.token:
        return Response(
            status_code=404,
            content="QR ainda não gerado.",
            media_type="text/plain; charset=utf-8",
        )

    url_checkin = f"{base_url(request)}/checkin/{STATE.token}"
    print("CHECKIN_URL =", url_checkin)

    png = gerar_qr_png(url_checkin)

    resp = Response(content=png, media_type="image/png")
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return resp

@router.get("/status")
def status(request: Request):
    _check_prof_key(request)

    return {
        "token_ativo": bool(STATE.token),
        "ativa": STATE.ativa(),
        "expira_em": STATE.expira_em.isoformat() if STATE.expira_em else None,
        "expira_epoch_ms": int(STATE.expira_em.timestamp() * 1000) if STATE.expira_em else None,
        "qtd_presentes": len(STATE.presentes),
        "ttl_min": TTL_MIN,
    }


# =========================
# CHECK-IN PÚBLICO (/checkin)
# =========================
@public_router.get("/checkin/{token}", response_class=HTMLResponse)
def checkin_form(request: Request, token: str):
    if not STATE.ativa() or token != STATE.token:
        return HTMLResponse("<h3>QR inválido ou expirado.</h3>", status_code=401)

    aviso = ""
    host = (request.headers.get("host") or "").lower()
    if host.startswith("localhost") or host.startswith("127."):
        aviso = (
            "<p style='color:#b00'>"
            "<strong>Atenção:</strong> abra pelo IP do notebook "
            "(ex.: http://192.168.x.y:8000).</p>"
        )

    return request.app.state.templates.TemplateResponse(
        "checkin.html",
        {
            "request": request,
            "aviso": aviso,
        },
    )

import logging
logger = logging.getLogger("uvicorn.error")

@public_router.post("/checkin/{token}", response_class=HTMLResponse)
def checkin_submit(request: Request, token: str, ra: str = Form(...), nome: str = Form(...)):
    if not STATE.ativa() or token != STATE.token:
        return HTMLResponse("QR inválido ou expirado.", status_code=401)

    ra = ra.strip()
    nome = nome.strip()

    if ra in STATE.presentes:
        return HTMLResponse("<h3>Presença já registrada.</h3>")

    try:
        registrar_presenca(ra, nome)
    except Exception:
        logger.exception("Falha ao registrar presença no Sheets")
        return HTMLResponse(
            "<h3>Não foi possível registrar agora.</h3>"
            "<p>Avise o professor e tente novamente.</p>",
            status_code=502,
        )

    STATE.presentes.add(ra)
    return HTMLResponse("<h3>Presença registrada com sucesso!</h3>")

    return {"build": "v-2025-12-26-01",
    }
