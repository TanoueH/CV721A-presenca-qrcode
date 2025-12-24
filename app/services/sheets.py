import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

DISCIPLINA = "Fundações (CV721A)"
TURMA = "Engenharia Civil – 2025"

def get_worksheet():
    creds_path = os.getenv("GOOGLE_CREDS_JSON", "credenciais.json")
    spreadsheet_id = os.getenv("SPREADSHEET_ID")

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]

    creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
    client = gspread.authorize(creds)

    return client.open_by_key(spreadsheet_id).worksheet("Checkins")

def registrar_presenca(ra: str, nome: str):
    ws = get_worksheet()
   

    if ws.acell("A1").value is None:
        ws.update(
            "A1:F1",
            [["Data", "Disciplina", "Turma", "RA", "Nome", "Hora"]],
        )

    ws.append_row([
        datetime.now().strftime("%Y-%m-%d"),
        DISCIPLINA,
        TURMA,
        ra,
        nome,
        datetime.now().strftime("%H:%M:%S"),
    ])

def calcular_frequencia():
    ws = get_worksheet()
    registros = ws.get_all_records()

    total_aulas = len(set(r["Data"] for r in registros))

    alunos = {}
    for r in registros:
        ra = r["RA"]
        nome = r["Nome"]

        if ra not in alunos:
            alunos[ra] = {
                "ra": ra,
                "nome": nome,
                "presencas": 0,
            }

        alunos[ra]["presencas"] += 1

    return total_aulas, list(alunos.values())

