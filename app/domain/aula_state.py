from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Set
import secrets


@dataclass
class AulaState:
    """
    Modelo simples:
      - aula ativa/inativa
      - QR publicado sob demanda (token + expires_at) ou não publicado (None)
      - validação de QR checa: aula ativa + token igual + TTL
    """

    ttl_minutes: int = 15

    # Aula
    active: bool = False

    # QR publicado
    token: Optional[str] = None
    expires_at: Optional[datetime] = None

    # Presenças (limpa ao iniciar aula)
    presentes: Set[str] = field(default_factory=set)

    # --------- Aula ---------
    def iniciar_aula(self) -> None:
        """Ativa a aula. Não publica QR automaticamente."""
        self.active = True
        self.presentes.clear()
        self.revogar_qr()

    def encerrar_aula(self) -> None:
        """Encerra a aula e remove QR."""
        self.active = False
        self.revogar_qr()
        self.presentes.clear()

    # --------- QR sob demanda ---------
    def gerar_qr(self) -> str:
        """Publica QR (token + TTL). Requer aula ativa."""
        if not self.active:
            raise RuntimeError("Não é possível gerar QR: aula inativa.")
        self.token = secrets.token_urlsafe(16)
        self.expires_at = datetime.now() + timedelta(minutes=self.ttl_minutes)
        return self.token

    def renovar_qr(self) -> str:
        """Gera novo token e reinicia TTL."""
        return self.gerar_qr()

    def revogar_qr(self) -> None:
        """Oculta QR sem encerrar aula."""
        self.token = None
        self.expires_at = None

    # --------- Compatibilidade (para remover hasattr no router) ---------
    def start(self) -> None:
        """Compat: iniciar aula (sem gerar QR automaticamente)."""
        self.iniciar_aula()

    def end(self) -> None:
        """Compat: encerrar aula."""
        self.encerrar_aula()

    def renew(self) -> None:
        """Compat: renovar QR."""
        self.renovar_qr()

    def is_active(self) -> bool:
        return self.active

    def qr_ativo(self) -> bool:
        """Mantém seu uso legado: 'QR publicado e não expirado' (não significa aula ativa)."""
        return self.token is not None and self.expires_at is not None and datetime.now() <= self.expires_at

    # --------- Validação ---------
    def qr_valido(self, token: str) -> bool:
        """Modelo correto: aula ativa + token atual + TTL."""
        if not self.active:
            return False
        if not self.token or not self.expires_at:
            return False
        if token != self.token:
            return False
        return datetime.now() <= self.expires_at

    def remaining_seconds(self) -> Optional[int]:
        if not self.expires_at:
            return None
        delta = (self.expires_at - datetime.now()).total_seconds()
        return max(0, int(delta))
