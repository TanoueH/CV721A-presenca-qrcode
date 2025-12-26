import json
import logging
import os
from datetime import datetime
from functools import lru_cache
from typing import Tuple, List, Dict, Any, Optional

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from gspread.exceptions import WorksheetNotFound, APIError

DISCIPLINA = "Fundações (CV721A)"
TURMA = "Engenharia Civil (FEC) – 2026"

CHECKINS_TAB = os.getenv("CHECKINS_TAB", "Checkins")
AULAS_TAB = os.getenv("AULAS_TAB", "Aulas")

# -------------------------
# LOGGING
# -------------------------
logger = logging.getLogger("cv721a.sheets")
if not logger.handlers:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))


# -------------------------
# ERROS EXPLÍCITOS
# -------------------------
class SheetsConfigError(RuntimeError):
    """Erro de configuração (env/credenciais/planilha)."""


class SheetsRuntimeError(RuntimeError):
    """Erro em runtime (API/aba/atualização)."""


def _get_env_required(name: str) -> str:
    val = (os.getenv(name) or "").strip()
    if not val:
        raise SheetsConfigError(f"Variável de ambiente {name} não definida.")
    return val


def _load_creds_path() -> str:
    # Prioridade: caminho de arquivo no container/WSL
    path = (os.getenv("GOOGLE_CREDS_JSON") or "credenciais.json").strip()
    if os.path.exists(path):
        return path

    # Alternativa comum no Render: credenciais em JSON string
    # (se você quiser usar, defina GOOGLE_CREDS_JSON_TEXT no Render)
    text = (os.getenv("GOOGLE_CREDS_JSON_TEXT") or "").strip()
    if text:
        # salva em /tmp para uso pelo oauth2client
        tmp_path = "/tmp/google_creds.json"
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(text)
        return tmp_path

    raise SheetsConfigError(
        "Credenciais não encontradas. Defina GOOGLE_CREDS_JSON (caminho do arquivo) "
        "ou GOOGLE_CREDS_JSON_TEXT (conteúdo JSON como texto)."
    )


@lru_cache(maxsize=1)
def get_client() -> gspread.Client:
    """
    Cria client uma única vez (cache).
    Em produção evita autorizar a cada request.
    """
    creds_path = _load_creds_path()

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]

    logger.info("Autorizando Google Sheets client...")
    creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
    return gspread.authorize(creds)


def get_spreadsheet() -> gspread.Spreadsheet:
    spreadsheet_id = _get_env_required("SPREADSHEET_ID")
    client = get_client()
    try:
        return client.open_by_key(spreadsheet_id)
    except Exception as e:
        logger.exception("Falha ao abrir planilha por SPREADSHEET_ID.")
        raise SheetsRuntimeError(f"Não foi possível abrir a planilha (ID={spreadsheet_id}).") from e


def get_worksheet(tab_name: str) -> gspread.Worksheet:
    ss = get_spreadsheet()
    try:
        return ss.worksheet(tab_name)
    except WorksheetNotFound as e:
        logger.error("Aba '%s' não encontrada na planilha.", tab_name)
        raise SheetsConfigError(
            f"Aba '{tab_name}' não existe. Crie a aba com esse nome no Google Sheets."
        ) from e
    except APIError as e:
        logger.exception("APIError ao abrir aba '%s'.", tab_name)
        raise SheetsRuntimeError(f"Erro de API ao acessar a aba '{tab_name}'.") from e


# -------------------------
# AULAS (Assunto + Material)
# -------------------------
def ensure_aulas_header(ws: gspread.Worksheet) -> None:
    """Garante cabeçalho padrão na aba Aulas."""
    try:
        colA = ws.col_values(1)
        if not colA or (colA and colA[0] != "Data"):
            ws.update("A1:F1", [["Data", "Turma", "Disciplina", "Assunto", "MaterialURL", "UpdatedAt"]])
    except Exception as e:
        logger.exception("Falha ao garantir cabeçalho da aba Aulas.")
        raise SheetsRuntimeError("Não foi possível preparar cabeçalho da aba Aulas.") from e

def upsert_aula_hoje(
    data: str,
    disciplina: str,
    turma: str,
    assunto: str,
    material_url: str,
    tab_name: str = AULAS_TAB,
) -> None:
    ws = get_worksheet(tab_name)
    ensure_aulas_header(ws)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        colA = ws.col_values(1)  # inclui header em colA[0]
        try:
            idx = colA.index(data)
            row = idx + 1
            ws.update(f"B{row}:F{row}", [[turma, disciplina, assunto, material_url, now]])
            logger.info("Aula do dia atualizada (data=%s).", data)
        except ValueError:
            ws.append_row([data, turma, disciplina, assunto, material_url, now])
            logger.info("Aula do dia inserida (data=%s).", data)
    except APIError as e:
        logger.exception("APIError ao inserir/atualizar aula.")
        raise SheetsRuntimeError("Erro de API ao salvar dados da aula.") from e
    except Exception as e:
        logger.exception("Erro inesperado ao inserir/atualizar aula.")
        raise SheetsRuntimeError("Erro inesperado ao salvar dados da aula.") from e


def load_aula_hoje(data: str, tab_name: str = AULAS_TAB) -> Dict[str, str]:
    """Busca (assunto, material_url) pela Data."""
    ws = get_worksheet(tab_name)
    try:
        rows = ws.get_all_records()
        for r in rows:
            if r.get("Data") == data:
                return {
                    "assunto": (r.get("Assunto") or "").strip(),
                    "material_url": (r.get("MaterialURL") or "").strip(),
                }
        return {"assunto": "", "material_url": ""}
    except Exception as e:
        logger.exception("Falha ao ler aula do dia.")
        raise SheetsRuntimeError("Não foi possível ler a aula do dia na aba Aulas.") from e


# -------------------------
# CHECKINS (Presença)
# -------------------------
def ensure_checkins_header(ws: gspread.Worksheet) -> None:
    try:
        first_row = ws.row_values(1)
        if not first_row or first_row[0] != "Data":
            ws.update("A1:F1", [["Data", "Disciplina", "Turma", "RA", "Nome", "Hora"]])
    except Exception as e:
        logger.exception("Falha ao garantir cabeçalho da aba Checkins.")
        raise SheetsRuntimeError("Não foi possível preparar cabeçalho da aba Checkins.") from e


def registrar_presenca(ra: str, nome: str, tab_name: str = CHECKINS_TAB) -> None:
    ra = (ra or "").strip()
    nome = (nome or "").strip()
    if not ra or not nome:
        raise ValueError("RA/Nome vazios")
    _append_presenca_row(ra, nome, tab_name=tab_name)

def _append_presenca_row(ra: str, nome: str, tab_name: str = CHECKINS_TAB) -> None:
    ws = get_worksheet(tab_name)
    ensure_checkins_header(ws)

    hoje = datetime.now().strftime("%Y-%m-%d")
    hora = datetime.now().strftime("%H:%M:%S")

    try:
        ws.append_row([hoje, DISCIPLINA, TURMA, ra, nome, hora], value_input_option="USER_ENTERED")
        logger.info("Check-in registrado (RA=%s).", ra)
    except APIError as e:
        logger.exception("APIError ao registrar check-in.")
        raise SheetsRuntimeError("Erro de API ao registrar check-in.") from e
    except Exception as e:
        logger.exception("Erro inesperado ao registrar check-in.")
        raise SheetsRuntimeError("Erro inesperado ao registrar check-in.") from e


def calcular_frequencia(tab_name: str = CHECKINS_TAB) -> Tuple[int, List[Dict[str, Any]]]:
    ws = get_worksheet(tab_name)
    try:
        registros = ws.get_all_records()
        total_aulas = len(set(r["Data"] for r in registros if r.get("Data")))

        alunos: Dict[str, Dict[str, Any]] = {}
        for r in registros:
            ra = (r.get("RA") or "").strip()
            nome = (r.get("Nome") or "").strip()
            if not ra:
                continue

            if ra not in alunos:
                alunos[ra] = {"ra": ra, "nome": nome, "presencas": 0}

            alunos[ra]["presencas"] += 1

        return total_aulas, list(alunos.values())
    except Exception as e:
        logger.exception("Falha ao calcular frequência.")
        raise SheetsRuntimeError("Não foi possível calcular frequência a partir da aba Checkins.") from e
