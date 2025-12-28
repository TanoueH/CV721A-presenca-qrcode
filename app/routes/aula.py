import secrets
from datetime import datetime, timedelta
from typing import Optional, Set

from fastapi import APIRouter, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, Response, RedirectResponse

from app.core.public_urls import checkin_url
from app.services.qrcode_service import QRCodeService

from app.services.sheets import registrar_presenca
from pathlib import Path
from urllib.parse import quote

from app.domain.aula_state import AulaState #Novo

import json

DISCIPLINA = "Fundações (CV721A)"
TURMA = "Engenharia Civil FEC – 2026"
AULAS_DIR = Path("app/static/aulas")
ROTEIRO_PATH = Path("app/static/roteiro.json")

STATE = AulaState(ttl_minutes=15)

# Router do professor (tudo em /prof/...)
router = APIRouter(prefix="/prof", tags=["Professor"])

# Router público (check-in do aluno)
public_router = APIRouter(tags=["Check-in"])

qr_service = QRCodeService()


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
            "ativa": STATE.qr_ativo(),
            "qtd_presentes": len(STATE.presentes),
            "prof_k": request.query_params.get("k", ""),
        },
    )

@router.get("/aulas", response_class=HTMLResponse)
def lista_aulas(request: Request):
    _check_prof_key(request)

    itens = []
    if AULAS_DIR.exists():
        for p in sorted(AULAS_DIR.iterdir()):
            if p.is_file() and p.suffix.lower() in [".pdf", ".pptx", ".ppt"]:
                itens.append({
                    "nome": p.name,
                    "url": f"/static/aulas/{quote(p.name)}",
                    "tipo": p.suffix.lower().replace(".", "").upper(),
                })

    return request.app.state.templates.TemplateResponse(
        "aulas.html",
        {"request": request, "itens": itens, "prof_k": request.query_params.get("k", "")},
    )

@router.post("/aula/iniciar")
def iniciar_aula(request: Request):
    _check_prof_key(request)
    STATE.iniciar()
    k = request.query_params.get("k", "")
    return RedirectResponse(url=f"/prof/?k={k}", status_code=303)

@router.get("/roteiro", response_class=HTMLResponse)
def roteiro(request: Request):
    _check_prof_key(request)

    data = {"titulo": "Roteiro de Aulas", "itens": []}
    if ROTEIRO_PATH.exists():
        data = json.loads(ROTEIRO_PATH.read_text(encoding="utf-8"))

    # resolve URL + existência do arquivo
    for it in data.get("itens", []):
        arq = (it.get("arquivo") or "").strip()
        it["url"] = f"/static/aulas/{arq}" if arq else ""
        it["existe"] = bool(arq) and (AULAS_DIR / arq).exists()

    return request.app.state.templates.TemplateResponse(
        "roteiro.html",
        {"request": request, "data": data, "prof_k": request.query_params.get("k", "")},
    )


@router.post("/aula/gerar_qr")
def gerar_qr_final(request: Request):
    _check_prof_key(request)
    STATE.gerar_qr()

    k = request.query_params.get("k", "")

    BASE_URL = os.getenv("BASE_URL", "https://cv721a-presenca-qrcode.onrender.com")
    base_url = BASE_URL.rstrip("/")
    url = f"{base_url}/prof/projecao?k={k}"

    return RedirectResponse(url=url, status_code=303)

@router.post("/aula/encerrar")
def encerrar_aula(request: Request):
    _check_prof_key(request)
    STATE.encerrar()
    k = request.query_params.get("k", "")
    return RedirectResponse(url=f"/prof/?k={k}", status_code=303)


@router.post("/aula/renovar")
def renovar_aula(request: Request):
    _check_prof_key(request)
    STATE.renovar_qr()
    k = request.query_params.get("k", "")
    return RedirectResponse(url=f"/prof/projecao?k={k}", status_code=303)

@router.get("/projecao", response_class=HTMLResponse)
def projecao(request: Request):
    _check_prof_key(request)

    return request.app.state.templates.TemplateResponse(
        "projecao.html",
        {
            "request": request,
            "disciplina": DISCIPLINA,
            "turma": TURMA,
            "ativa": STATE.qr_ativo(),
            "token": STATE.token,                 # importante para standby
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
         content=b"",
         status_code=204
    )

    url_checkin = checkin_url(STATE.token)
    png = qr_service.png_for_url(url_checkin)

    resp = Response(content=png, media_type="image/png")
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return resp

@router.get("/status")
def status(request: Request):
    _check_prof_key(request)

    return {
        "token_ativo": bool(STATE.token),
        "ativa": STATE.qr_ativo(),
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
    if (not STATE.qr_ativo()) or token != STATE.token:
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
    if (not STATE.qr_ativo()) or token != STATE.token:
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
            "<p>Tente novamente. Avise o professor.</p>",
            status_code=502,
        )

    STATE.presentes.add(ra)
    return HTMLResponse("<h3>Presença registrada com sucesso!</h3>")  