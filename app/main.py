import json
import io
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional, Set

import qrcode
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, Response

import gspread
from oauth2client.service_account import ServiceAccountCredentials


# =========================
# CONFIGURAÇÕES
# =========================
DISCIPLINA = "Fundações (CV721A)"
TURMA = "Engenharia Civil – 2025"
TEMPO_QR_MIN = int(os.getenv("QR_TTL_MIN", "3"))

SHEET_NAME = os.getenv("SHEET_NAME", "Presenca_FEC_Fundacoes_CV721A_2025")
BASE_URL = os.getenv("BASE_URL", "").rstrip("/")


# =========================
# GOOGLE SHEETS
# =========================
def get_worksheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]

    # Preferência: credenciais via ENV (Render)
    creds_json = os.getenv("GOOGLE_CREDS_JSON_CONTENT", "").strip()

    if creds_json:
        creds = ServiceAccountCredentials.from_json_keyfile_dict(
            json.loads(creds_json), scope
        )
    else:
        # Fallback: arquivo local (dev)
        creds_path = os.getenv("GOOGLE_CREDS_JSON", "credenciais.json")
        creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)

    client = gspread.authorize(creds)

    spreadsheet_id = os.getenv("SPREADSHEET_ID", "").strip()
    if spreadsheet_id:
        return client.open_by_key(spreadsheet_id).sheet1

    return client.open(SHEET_NAME).sheet1



# =========================
# ESTADO DA AULA
# =========================
class AulaState:
    def __init__(self):
        self.token: Optional[str] = None
        self.expira_em: Optional[datetime] = None
        self.data_ref: Optional[str] = None
        self.presencas_hoje: Set[str] = set()
        self.header_ok: bool = False  # evita checar A1 a cada check-in

    def nova_aula(self):
        self.token = secrets.token_urlsafe(16)
        self.expira_em = datetime.now() + timedelta(minutes=TEMPO_QR_MIN)
        self.data_ref = datetime.now().strftime("%Y-%m-%d")
        self.presencas_hoje.clear()
        self.header_ok = False

    def valido(self, token: str) -> bool:
        return (
            self.token == token
            and self.expira_em is not None
            and datetime.now() <= self.expira_em
        )


STATE = AulaState()
app = FastAPI()


# =========================
# UTILIDADES
# =========================
def make_qr_png_bytes(url: str) -> bytes:
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def resolve_base_url(request: Request) -> str:
    """
    - Se BASE_URL estiver definido (Render/produção), usa ele.
    - Senão, monta pelo host da requisição (funciona local e com IP).
    """
    if BASE_URL:
        return BASE_URL

    scheme = request.headers.get("x-forwarded-proto", "http")
    host = request.headers.get("host") or "localhost"
    return f"{scheme}://{host}".rstrip("/")


def warn_if_localhost(request: Request) -> str:
    """
    Se abrir via localhost, o QR aponta para localhost e no celular não funciona.
    """
    host = (request.headers.get("host") or "").lower()
    if host.startswith("localhost") or host.startswith("127.0.0.1"):
        return (
            "<p style='color:#b00'>"
            "<strong>Atenção:</strong> você abriu pelo <code>localhost</code>. "
            "No celular isso não funciona. "
            "Abra este sistema usando o IP do notebook na rede (ex.: "
            "<code>http://192.168.x.y:8000</code>)."
            "</p>"
        )
    return ""


# =========================
# ROTAS
# =========================
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    aviso = warn_if_localhost(request)

    html = f"""
    <h1>Presença por QR – {DISCIPLINA}</h1>
    <p><strong>Turma:</strong> {TURMA}</p>
    {aviso}

    <ol>
      <li>Clique em <strong>Gerar QR</strong> no início da aula.</li>
      <li>Projete o QR por <strong>{TEMPO_QR_MIN} min</strong>.</li>
      <li>Alunos fazem check-in com RA e Nome.</li>
    </ol>

    <form action="/aula/nova" method="post">
        <button type="submit">Gerar QR (início da aula)</button>
    </form>
    """

    if STATE.token and STATE.expira_em:
        html += f"""
        <hr>
        <p><strong>QR válido até:</strong> {STATE.expira_em.strftime("%H:%M:%S")}</p>
        <img src="/qr.png" width="300">
        """

    return html


@app.post("/aula/nova", response_class=HTMLResponse)
def aula_nova():
    STATE.nova_aula()
    return HTMLResponse(f"""
        <h2>QR Code gerado com sucesso</h2>
        <p><strong>Válido por:</strong> {TEMPO_QR_MIN} min</p>
        <p><a href="/">Voltar</a></p>
        <img src="/qr.png" width="300">
    """)


@app.get("/qr.png")
def qr_png(request: Request):
    if not STATE.token:
        return Response(
            status_code=404,
            content="QR ainda não gerado.",
            media_type="text/plain; charset=utf-8",
        )

    base_url = resolve_base_url(request)
    checkin_url = f"{base_url}/checkin/{STATE.token}"

    png = make_qr_png_bytes(checkin_url)
    return Response(content=png, media_type="image/png")


@app.get("/checkin/{token}", response_class=HTMLResponse)
def checkin_form(token: str):
    if not STATE.valido(token):
        return HTMLResponse("<h3>QR inválido ou expirado.</h3>", status_code=401)

    return HTMLResponse("""
        <h2>Registro de Presença</h2>
        <form method="post">
            <input name="ra" placeholder="RA" required><br><br>
            <input name="nome" placeholder="Nome completo" required><br><br>
            <button type="submit">Confirmar presença</button>
        </form>
    """)


@app.post("/checkin/{token}", response_class=HTMLResponse)
def checkin_submit(token: str, ra: str = Form(...), nome: str = Form(...)):
    if not STATE.valido(token):
        return HTMLResponse("QR inválido ou expirado.", status_code=401)

    ra = ra.strip()
    nome = nome.strip()

    data = datetime.now().strftime("%Y-%m-%d")
    hora = datetime.now().strftime("%H:%M:%S")

    if ra in STATE.presencas_hoje:
        return HTMLResponse("Presença já registrada.")

    ws = get_worksheet()

    # Cabeçalho: evita chamada remota (acell) a cada check-in
    if not STATE.header_ok:
        if ws.acell("A1").value is None:
            ws.update(
                values=[["Data", "Disciplina", "Turma", "RA", "Nome", "Hora"]],
                range_name="A1:F1",
            )
        STATE.header_ok = True

    ws.append_row([data, DISCIPLINA, TURMA, ra, nome, hora])
    STATE.presencas_hoje.add(ra)

    return HTMLResponse("<h3>Presença registrada com sucesso!</h3>")


@app.get("/health")
def health():
    spreadsheet_id = os.getenv("SPREADSHEET_ID", "").strip()
    return {
        "ok": True,
        "token_ativo": bool(STATE.token),
        "expira_em": STATE.expira_em.isoformat() if STATE.expira_em else None,
        "ttl_min": TEMPO_QR_MIN,
        "spreadsheet_id_configurado": bool(spreadsheet_id),
    }
