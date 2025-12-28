import os
from datetime import datetime
from typing import Optional, Set

from app.domain.aula_state import AulaState as _AulaState
import app.core.app_state as app_state


DISCIPLINA = getattr(app_state, "DISCIPLINA", "Fundações (CV721A)")
TURMA = getattr(app_state, "TURMA", "Engenharia Civil FEC – 2026")
TEMPO_QR_MIN = getattr(app_state, "TEMPO_QR_MIN", 15)

STATE = getattr(app_state, "STATE", None)
if STATE is None:
    # fallback mínimo (não derruba o deploy)
    import secrets
    from datetime import datetime, timedelta
    from typing import Optional, Set

    class _FallbackState:
        def __init__(self):
            self.token: Optional[str] = None
            self.expira_em: Optional[datetime] = None
            self.presentes: Set[str] = set()

        def nova_aula(self):
            self.token = secrets.token_urlsafe(16)
            self.expira_em = datetime.now() + timedelta(minutes=TEMPO_QR_MIN)
            self.presentes.clear()

    STATE = _FallbackState()