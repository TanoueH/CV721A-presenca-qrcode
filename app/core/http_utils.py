from fastapi import Request
import os

BASE_URL = os.getenv("BASE_URL", "").rstrip("/")

def resolve_base_url(request: Request) -> str:
    if BASE_URL:
        return BASE_URL
    scheme = request.headers.get("x-forwarded-proto", "https")
     
def warn_if_localhost(request: Request) -> str:
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
