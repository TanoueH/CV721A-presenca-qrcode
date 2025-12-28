from datetime import datetime, timedelta
import secrets

class AulaState:
    def __init__(self, ttl_minutes: int):
        self.ttl = timedelta(minutes=ttl_minutes)
        self.token = None
        self.expires_at = None

    def start(self):
        self.token = secrets.token_urlsafe(16)
        self.expires_at = datetime.utcnow() + self.ttl
        return self.token

    def is_active(self) -> bool:
        return self.token is not None and datetime.utcnow() < self.expires_at

    def is_valid_token(self, token: str) -> bool:
        return self.is_active() and token == self.token

    def remaining_seconds(self) -> int:
        if not self.is_active():
            return 0
        return int((self.expires_at - datetime.utcnow()).total_seconds())