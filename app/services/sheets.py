# app/services/sheets.py
import os
import json
import re
from functools import lru_cache
from datetime import datetime, timezone

import gspread
from gspread.exceptions import WorksheetNotFound, APIError
from google.oauth2.service_account import Credentials

from typing import Tuple, List, Dict, Any


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

RA_RE = re.compile(r"^\d{6}$")

def _now_iso() -> str:
    # ISO simples em horário local do servidor; se quiser forçar -03:00, ajustamos depois
    return datetime.now().isoformat(timespec="seconds")

def normalize_ra(ra: str) -> str:
    ra = (ra or "").strip()
    return ra

def validate_ra(ra: str) -> bool:
    return bool(RA_RE.match(ra))

def _load_service_account_info() -> dict:
    raw = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if raw:
        return json.loads(raw)

    path = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
    if path:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    raise RuntimeError(
        "Credenciais do Google não encontradas. Defina GOOGLE_SERVICE_ACCOUNT_JSON ou GOOGLE_SERVICE_ACCOUNT_FILE."
    )

@lru_cache(maxsize=1)
def get_gspread_client():
    info = _load_service_account_info()
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds)

@lru_cache(maxsize=1)
def get_spreadsheet():
    sid = os.getenv("SHEETS_SPREADSHEET_ID")
    if not sid:
        raise RuntimeError("Env SHEETS_SPREADSHEET_ID não definida.")
    return get_gspread_client().open_by_key(sid)

def get_ws(title: str):
    return get_spreadsheet().worksheet(title)

def ensure_ws(title: str, headers: list[str]):
    sh = get_spreadsheet()
    try:
        ws = sh.worksheet(title)
    except WorksheetNotFound:
        ws = sh.add_worksheet(title=title, rows=1000, cols=max(10, len(headers)))
        ws.append_row(headers)
    return ws

def get_aluno_por_ra(ra: str) -> dict | None:
    """
    Procura o RA na aba 'Alunos'. Espera headers contendo 'ra' e 'nome' (mínimo).
    Retorna dict da linha encontrada ou None.
    """
    ws = get_ws("Alunos")
    rows = ws.get_all_records()
    if not rows:
        return None

    # header esperado: 'ra' (case-insensitive)
    for r in rows:
        r_ra = str(r.get("ra") or r.get("RA") or "").strip()
        if r_ra == ra:
            return r
    return None

def append_checkin(aula_id: str, ra: str, status: str):
    ws = ensure_ws("Checkins", ["timestamp", "aula_id", "ra", "status"])
    ws.append_row([_now_iso(), aula_id, ra, status])

def append_pendencia(aula_id: str, ra: str, motivo: str):
    ws = ensure_ws("Pendencias", ["timestamp", "aula_id", "ra_informado", "motivo"])
    ws.append_row([_now_iso(), aula_id, ra, motivo])



def ja_registrou_na_aula(aula_id: str, ra: str) -> bool:
    """
    Deduplicação simples: varre Checkins e checa (aula_id, ra) com status OK.
    Para 2k linhas isso é OK. Depois otimizamos com caching/índice.
    """
    try:
        ws = get_ws("Checkins")
    except WorksheetNotFound:
        return False

    rows = ws.get_all_records()
    for r in rows:
        if str(r.get("aula_id", "")).strip() == aula_id and str(r.get("ra", "")).strip() == ra:
            if str(r.get("status", "")).strip().upper() == "OK":
                return True
    return False


def calcular_frequencia() -> Tuple[int, List[Dict[str, Any]]]:
    """
    Calcula frequência a partir da aba 'Checkins'.

    Regras:
    - Conta apenas status == "OK"
    - Frequência = nº de aulas distintas (aula_id) por RA
    - Total de aulas = nº de aula_id distintos no log
    """
    ws = get_ws("Checkins")
    rows = ws.get_all_records()

    if not rows:
        return 0, []

    # --------
    # Detecta colunas (case-insensitive)
    # --------
    def pick_key(d: dict, candidates: list[str]) -> str | None:
        keys = {k.lower(): k for k in d.keys()}
        for c in candidates:
            if c.lower() in keys:
                return keys[c.lower()]
        return None

    sample = rows[0]

    k_aula = pick_key(sample, ["aula_id"])
    k_ra = pick_key(sample, ["ra"])
    k_status = pick_key(sample, ["status"])

    if not k_aula or not k_ra:
        raise RuntimeError(
            f"Aba 'Checkins' precisa conter colunas 'aula_id' e 'ra'. "
            f"Headers encontrados: {list(sample.keys())}"
        )

    # --------
    # Coleta aulas válidas
    # --------
    aulas_validas = set()
    presencas_por_ra: Dict[str, set] = {}

    for r in rows:
        aula_id = str(r.get(k_aula, "")).strip()
        ra = str(r.get(k_ra, "")).strip()
        status = str(r.get(k_status, "")).strip().upper() if k_status else "OK"

        if not aula_id or not ra:
            continue

        if status != "OK":
            continue

        aulas_validas.add(aula_id)

        if ra not in presencas_por_ra:
            presencas_por_ra[ra] = set()

        presencas_por_ra[ra].add(aula_id)

    total_aulas = len(aulas_validas)

    # --------
    # Monta retorno
    # --------
    alunos = []
    for ra, aulas in presencas_por_ra.items():
        pres = len(aulas)
        freq = (pres / total_aulas * 100.0) if total_aulas else 0.0

        alunos.append({
            "ra": ra,
            "presencas": pres,
            "frequencia": round(freq, 1),
        })

    # ordena por RA (estável)
    alunos.sort(key=lambda x: x["ra"])

    return total_aulas, alunos
