import os
import json
from functools import lru_cache
from datetime import datetime

import gspread
from gspread.exceptions import WorksheetNotFound
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")

def _load_service_account_info() -> dict:
    raw = os.getenv("GOOGLE_CREDS_JSON_TEXT")
    if raw:
        return json.loads(raw)

    raise RuntimeError(
        "Credenciais do Google não encontradas. Defina GOOGLE_CREDS_JSON_TEXT."
    )

@lru_cache(maxsize=1)
def get_gspread_client():
    info = _load_service_account_info()
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds)

@lru_cache(maxsize=1)
def get_spreadsheet():
    sid = os.getenv("SPREADSHEET_ID")
    if not sid:
        raise RuntimeError("Env SPREADSHEET_ID não definida.")
    return get_gspread_client().open_by_key(sid)

def ensure_ws(title: str, headers: list[str]):
    sh = get_spreadsheet()
    try:
        ws = sh.worksheet(title)
    except WorksheetNotFound:
        ws = sh.add_worksheet(title=title, rows=1000, cols=max(10, len(headers)))
        ws.append_row(headers)
    return ws

def registrar_presenca(ra: str, nome: str):
    tab = os.getenv("CHECKINS_TAB", "Checkins")
    ws = ensure_ws(tab, ["Data/Hora", "Nome", "RA", "Status"])
    ws.append_row([_now_iso(), nome.strip(), ra.strip(), "OK"])