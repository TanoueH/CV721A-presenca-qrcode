import os

def get_public_base_url() -> str:
    base = os.getenv("BASE_URL", "").strip()
    if not base:
        raise RuntimeError(
            "BASE_URL não definido. "
            "Defina a URL pública do sistema (ex.: https://cv721a-presenca-qrcode.onrender.com)"
        )
    return base.rstrip("/")