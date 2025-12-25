import os
import secrets
from datetime import datetime, timedelta
from typing import Optional, Set

DISCIPLINA = "Fundações (CV721A)"
TURMA = "Engenharia Civil – 2025"
TEMPO_QR_MIN = int(os.getenv("QR_TTL_MIN", "3"))

BASE_URL = os.getenv("BASE_URL", "").rstrip("/")

class AulaState:
    def __init__(self):
        self.token: Optional[str] = None
        self.expira_em: Optional[datetime] = None
        self.data_ref: Optional[str] = None
        self.presencas_hoje: Set[str] = set()
        self.header_ok: bool = False

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
