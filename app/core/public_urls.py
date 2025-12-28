from app.core.public_base import get_public_base_url

CHECKIN_PATH = "/checkin/{token}"
QR_PNG_PATH = "/prof/qr.png"

def checkin_url(token: str) -> str:
    return get_public_base_url() + CHECKIN_PATH.format(token=token)

def qr_png_url() -> str:
    return get_public_base_url() + QR_PNG_PATH