from datetime import datetime, timedelta
import secrets
from typing import Optional, Set


class AulaState:
    """
    Estado em memória da aula corrente.
    Controla token, validade e presenças.
    """

    def __init__(self, ttl_minutes: int):
        self.ttl = timedelta(minutes=ttl_minutes)
        self.token: Optional[str] = None
        self.expires_at: Optional[datetime] = None
        self.presentes: Set[str] = set()

    # -------------------------
    # Ciclo de vida da aula
    # -------------------------
    def start(self) -> str:
        """
        Inicia (ou reinicia) a aula e gera um novo token.
        """
        self.token = secrets.token_urlsafe(16)
        self.expires_at = datetime.utcnow() + self.ttl
        self.presentes.clear()
        return self.token

    def renew(self) -> str:
        """
        Renova o token mantendo a aula ativa.
        """
        return self.start()

    def end(self) -> None:
        """
        Encerra a aula e limpa o estado.
        """
        self.token = None
        self.expires_at = None
        self.presentes.clear()

    # -------------------------
    # Validação
    # -------------------------
    def is_active(self) -> bool:
        return (
            self.token is not None
            and self.expires_at is not None
            and datetime.utcnow() <= self.expires_at
        )

    def is_valid_token(self, token: str) -> bool:
        return self.is_active() and token == self.token

    # -------------------------
    # Utilidades
    # -------------------------
    def remaining_seconds(self) -> int:
        if not self.is_active():
            return 0
        return int((self.expires_at - datetime.utcnow()).total_seconds())