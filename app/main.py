"""
Sistema de Presença por QR Code Dinâmico
Projeto-piloto FEC/UNICAMP – Disciplina: Fundações (CV721A)

Coordenação técnica:
Heloi Moacyr Tanoue
"""

import io
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional, Set, Tuple

import qrcode
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, Response

import gspread
from oauth2client.service_account import ServiceAccountCredentials


# =========================
# CONFIGURAÇÕES DO PILOTO
# =========================
DISCIPLINA = "Fundações (CV721A)"
TURMA = "Engenharia Civil – 2025"
TEMPO_QR_MIN = int(os.getenv("QR_TTL_MIN", "3"))

# Nome exato da sua planilha no Google Drive
SHEET_NAME = os.getenv("SHEET_NAME", "Presenca_FEC_Fundacoes_CV721A_2025")

# URL pública do serviço (Render): ex. https://cv721a-presenca-qrcode.onrender.com
BASE_URL = os.getenv("BASE_URL", "").rstrip("/")


# =========================
# GOOGLE SHEETS
# =========================
def get_worksheet():
    """
    Carrega credenciais a partir de:
    - caminho do arquivo (recomendado em dev): GOOGLE_CREDS_JSON=credenciais.json
    - ou Secret File no Render apontando para /etc/secrets/credenciais.json
    """
    creds_path = os.getenv("GOOGLE_CREDS_JSON", "credenciais.json")
    if not os.path.exists(creds_path):
        raise RuntimeError(
            f"Arquivo de credenciais não encontrado: {creds_path}. "
            "Defina GOOGLE_CREDS_JSON para o caminho correto (Render Secret File)."
        )

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
    client = gspread.authorize(creds)
    ws = client.open(SHEET_NAME).sheet1
    return ws


# =========================
# ESTADO EM MEMÓRIA
# =========================
class AulaState:
    def __init__(self):
        self.token: Optional[str] = None
        self.expira_em: Optional[datetime] = None
        self.data_ref: Optional[str] = None  # YYYY-MM-DD
        self.presencas_hoje: Set[str] = set()  # RAs já confirmados hoje

    def nova_aula(self):
        self.token = secrets.token_urlsafe(16)
        self.expira_em = datetime.now() + timedelta(minutes=TEMPO_QR_MIN)
        self.data_ref = datetime.now().strftime("%Y-%m-%d")
        # Mantém cache do dia; se mudou o dia, limpa
        # (em geral não precisa, mas é seguro)
        # Se preferir “por aula”, limpe sempre:
        # self.presencas_hoje = set()

    def valido(self, token: str) -> bool:
        return (
            self.token is not None
            and self.expira_em is not None
            and token == self.token
            and datetime.now() <= self.expira_em
        )

STATE = AulaState()
app = FastAPI()


# =========================
# UTILIDADES
# =========================
def make_qr_png_bytes(url: str) -> bytes:
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def require_base_url():
    if not BASE_URL:
        raise RuntimeError(
            "BASE_URL não configurada. Defina BASE_URL com a URL pública do Render, "
            "ex.: https://cv721a-presenca-qrcode.onrender.com"
        )


# =========================
# ROTAS
# =========================
@app.get("/", response_class=HTMLResponse)
def home():
    """
    Página do professor:
    - Mostra QR atual
    - Botão para gerar QR novo (início da aula)
    """
    html = f"""
    <h1>Presença por QR – {DISCIPLINA}</h1>
    <p><strong>Turma:</strong> {TURMA}</p>
    <p>1) Clique em <strong>Gerar QR</strong> no início da aula.<br>
       2) Projete o QR por {TEMPO_QR_MIN} min.<br>
       3) Alunos fazem check-in com RA e Nome.</p>
    <form action="/aula/nova" method="post">
        <button type="submit">Gerar QR (início da aula)</button>
    </form>
    """
    if STATE.token and STATE.expira_em:
        html += f"""
        <hr>
        <p><strong>QR vigente</strong> – válido até: {STATE.expira_em.strftime("%H:%M:%S")}</p>
        <img src="/qr.png" width="320" />
        """
    return html


@app.post("/aula/nova", response_class=HTMLResponse)
def aula_nova():
    """
    Gera um novo token/QR explicitamente (recomendado),
    evitando trocar o QR “sem querer” ao atualizar a página.
    """
    require_base_url()
    STATE.nova_aula()
    return HTMLResponse(f"""
        <h2>QR gerado com sucesso</h2>
        <p><strong>Válido até:</strong> {STATE.expira_em.strftime("%H:%M:%S")}</p>
        <p><a href="/">Voltar</a></p>
        <img src="/qr.png" width="320" />
    """)


@app.get("/qr.png")
def qr_png():
    require_base_url()
    if not STATE.token:
        return Response(status_code=404, content=b"QR ainda não gerado.")
    checkin_url = f"{BASE_URL}/checkin/{STATE.token}"
    png = make_qr_png_bytes(checkin_url)
    return Response(content=png, media_type="image/png")


@app.get("/checkin/{token}", response_class=HTMLResponse)
def checkin_form(token: str):
    if not STATE.valido(token):
        return HTMLResponse("<h3>QR inválido ou expirado.</h3>", status_code=401)

    aviso = (
        "Os dados coletados destinam-se exclusivamente ao controle acadêmico de presença (LGPD)."
    )
    return HTMLResponse(f"""
        <h2>Registro de Presença – FEC/UNICAMP</h2>
        <p>{aviso}</p>
        <form method="post">
            <input name="ra" placeholder="RA" required><br><br>
            <input name="nome" placeholder="Nome completo" required><br><br>
            <button type="submit">Confirmar presença</button>
        </form>
    """)


@app.post("/checkin/{token}", response_class=HTMLResponse)
def checkin_submit(
    request: Request,
    token: str,
    ra: str = Form(...),
    nome: str = Form(...),
):
    if not STATE.valido(token):
        return HTMLResponse("QR inválido ou expirado.", status_code=401)

    ra = ra.strip()
    nome = nome.strip()

    data = datetime.now().strftime("%Y-%m-%d")
    hora = datetime.now().strftime("%H:%M:%S")

    # Anti-duplicidade rápida (cache em memória)
    if data == STATE.data_ref and ra in STATE.presencas_hoje:
        return HTMLResponse("Você já registrou presença hoje.")

    # Registro no Sheets
    ws = get_worksheet()

    # Header opcional: se planilha vazia, cria cabeçalho
    if ws.row_count >= 1 and (ws.acell("A1").value or "").strip() == "":
        ws.update("A1:F1", [["Data", "Disciplina", "Turma", "RA", "Nome", "Hora"]])

    # Fallback anti-duplicidade (planilha) – busca simples por RA+Data
    # (evita leitura total; ainda assim é leve o suficiente para o piloto)
    values = ws.get_all_values()
    for row in values[1:]:
        # Esperado: [Data, Disciplina, Turma, RA, Nome, Hora]
        if len(row) >= 4 and row[0] == data and row[3] == ra:
            STATE.presencas_hoje.add(ra)
            return HTMLResponse("Você já registrou presença hoje.")

    ws.append_row([data, DISCIPLINA, TURMA, ra, nome, hora])

    # Atualiza cache do dia
    if data == STATE.data_ref:
        STATE.presencas_hoje.add(ra)

    return HTMLResponse("<h3>✅ Presença registrada com sucesso!</h3>")

