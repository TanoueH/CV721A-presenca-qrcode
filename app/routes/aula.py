from __future__ import annotations

import json
import logging
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.core.public_urls import checkin_url
from app.domain.aula_state import AulaState
from app.services.qrcode_service import QRCodeService
from app.services.sheets import registrar_presenca

logger = logging.getLogger("uvicorn.error")

DISCIPLINA = "Fundações (CV721A)"
TURMA = "Engenharia Civil FEC – 2026"

AULAS_DIR = Path("app/static/aulas")
ROTEIRO_PATH = Path("app/static/roteiro.json")

# Estado de aula (TTL por enquanto fixo; depois volta a vir de settings/env)
STATE = AulaState(ttl_minutes=15)

# Serviço de QR (único)
qr_service = QRCodeService()

# Routers
router = APIRouter(prefix="/prof", tags=["Professor"])
public_router = APIRouter(tags=["Check-in"])


# =========================
# PROFESSOR (/prof)
# =========================

@router.get("/", response_class=HTMLResponse)
def painel_professor(request: Request):
    return request.app.state.templates.TemplateResponse(
        "aula_hoje.html",
        {
            "request": request,
            "disciplina": DISCIPLINA,
            "turma": TURMA,
            "ativa": STATE.is_active() if hasattr(STATE, "is_active") else STATE.qr_ativo(),
            "token": getattr(STATE, "token", None),
            "expira_em": getattr(STATE, "expires_at", None) or getattr(STATE, "expira_em", None),
            "qtd_presentes": len(getattr(STATE, "presentes", set())),
        },
    )


@router.get("/aulas", response_class=HTMLResponse)
def lista_aulas(request: Request):
    itens = []
    if AULAS_DIR.exists():
        for p in sorted(AULAS_DIR.iterdir()):
            if p.is_file() and p.suffix.lower() in [".pdf", ".pptx", ".ppt"]:
                itens.append(
                    {
                        "nome": p.name,
                        "url": f"/static/aulas/{quote(p.name)}",
                        "tipo": p.suffix.lower().replace(".", "").upper(),
                    }
                )

    return request.app.state.templates.TemplateResponse(
        "aulas.html",
        {"request": request, "itens": itens},
    )


@router.get("/roteiro", response_class=HTMLResponse)
def roteiro(request: Request):
    data = {"titulo": "Roteiro de Aulas", "itens": []}
    if ROTEIRO_PATH.exists():
        data = json.loads(ROTEIRO_PATH.read_text(encoding="utf-8"))

    for it in data.get("itens", []):
        arq = (it.get("arquivo") or "").strip()
        it["url"] = f"/static/aulas/{quote(arq)}" if arq else ""
        it["existe"] = bool(arq) and (AULAS_DIR / arq).exists()

    return request.app.state.templates.TemplateResponse(
        "roteiro.html",
        {"request": request, "data": data},
    )


@router.post("/aula/iniciar")
def iniciar_aula():
    # Inicia e já cria um token (estado consistente)
    if hasattr(STATE, "start"):
        STATE.start()
    else:
        # compatibilidade com métodos antigos, se ainda existirem
        STATE.iniciar()
        if hasattr(STATE, "gerar_qr"):
            STATE.gerar_qr()

    return RedirectResponse(url="/prof/projecao", status_code=303)


@router.post("/aula/gerar_qr")
def gerar_qr():
    # Força criação/renovação de token
    if hasattr(STATE, "start"):
        STATE.start()
    elif hasattr(STATE, "gerar_qr"):
        STATE.gerar_qr()
    else:
        # fallback mínimo
        raise RuntimeError("AulaState não possui método start() nem gerar_qr().")

    return RedirectResponse(url="/prof/projecao", status_code=303)


@router.post("/aula/renovar")
def renovar():
    # Renova token (se houver método dedicado) senão recria
    if hasattr(STATE, "renew"):
        STATE.renew()
    elif hasattr(STATE, "renovar_qr"):
        STATE.renovar_qr()
    elif hasattr(STATE, "start"):
        STATE.start()
    else:
        raise RuntimeError("AulaState não possui método de renovação.")

    return RedirectResponse(url="/prof/projecao", status_code=303)


@router.post("/aula/encerrar")
def encerrar_aula():
    if hasattr(STATE, "encerrar"):
        STATE.encerrar()
    elif hasattr(STATE, "end"):
        STATE.end()
    else:
        # mínimo: zera token se existir
        if hasattr(STATE, "token"):
            STATE.token = None
        if hasattr(STATE, "expires_at"):
            STATE.expires_at = None
        if hasattr(STATE, "expira_em"):
            STATE.expira_em = None
        if hasattr(STATE, "presentes"):
            STATE.presentes = set()

    return RedirectResponse(url="/prof/", status_code=303)


@router.get("/projecao", response_class=HTMLResponse)
def projecao(request: Request):
    token = getattr(STATE, "token", None)
    expira_em = getattr(STATE, "expires_at", None) or getattr(STATE, "expira_em", None)
    ativa = STATE.is_active() if hasattr(STATE, "is_active") else STATE.qr_ativo()
    qtd_presentes = len(getattr(STATE, "presentes", set()))

    return request.app.state.templates.TemplateResponse(
        "projecao.html",
        {
            "request": request,
            "disciplina": DISCIPLINA,
            "turma": TURMA,
            "ativa": ativa,
            "token": token,
            "expira_em": expira_em,
            "qtd_presentes": qtd_presentes,
        },
    )


@router.get("/qr.png")
def qr_png():
    token = getattr(STATE, "token", None)
    ativa = STATE.is_active() if hasattr(STATE, "is_active") else STATE.qr_ativo()

    if (not token) or (not ativa):
        return Response(content=b"", status_code=204)

    url = checkin_url(token)
    png = qr_service.png_for_url(url)

    resp = Response(content=png, media_type="image/png")
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return resp


@router.get("/status")
def status():
    token = getattr(STATE, "token", None)
    expira_em = getattr(STATE, "expires_at", None) or getattr(STATE, "expira_em", None)
    ativa = STATE.is_active() if hasattr(STATE, "is_active") else STATE.qr_ativo()
    qtd_presentes = len(getattr(STATE, "presentes", set()))

    expira_iso = expira_em.isoformat() if expira_em else None
    expira_epoch_ms = int(expira_em.timestamp() * 1000) if expira_em else None

    return {
        "token_ativo": bool(token),
        "ativa": ativa,
        "expira_em": expira_iso,
        "expira_epoch_ms": expira_epoch_ms,
        "qtd_presentes": qtd_presentes,
    }


# =========================
# CHECK-IN PÚBLICO (/checkin)
# =========================

@public_router.get("/checkin/{token}", response_class=HTMLResponse)
def checkin_form(request: Request, token: str):
    token_ativo = getattr(STATE, "token", None)
    ativa = STATE.is_active() if hasattr(STATE, "is_active") else STATE.qr_ativo()

    if (not ativa) or token != token_ativo:
        return HTMLResponse("<h3>QR inválido ou expirado.</h3>", status_code=401)

    # Aviso opcional (não essencial)
    aviso = ""
    host = (request.headers.get("host") or "").lower()
    if host.startswith("localhost") or host.startswith("127."):
        aviso = (
            "<p style='color:#b00'>"
            "<strong>Atenção:</strong> você abriu pelo <code>localhost</code>. "
            "Use a URL pública (Render) ou o IP do notebook na rede.</p>"
        )

    return request.app.state.templates.TemplateResponse(
        "checkin.html",
        {"request": request, "aviso": aviso},
    )


@public_router.post("/checkin/{token}", response_class=HTMLResponse)
def checkin_submit(request: Request, token: str, ra: str = Form(...), nome: str = Form(...)):
    token_ativo = getattr(STATE, "token", None)
    ativa = STATE.is_active() if hasattr(STATE, "is_active") else STATE.qr_ativo()

    if (not ativa) or token != token_ativo:
        return HTMLResponse("QR inválido ou expirado.", status_code=401)

    ra = ra.strip()
    nome = nome.strip()

    presentes = getattr(STATE, "presentes", set())
    if ra in presentes:
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

    presentes.add(ra)
    # se presentes for atributo, garante persistência
    if hasattr(STATE, "presentes"):
        STATE.presentes = presentes

    return HTMLResponse("<h3>Presença registrada com sucesso!</h3>")