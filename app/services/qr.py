import io
import os
import qrcode
from qrcode.constants import ERROR_CORRECT_M

def build_checkin_url(token: str) -> str:
    base = (os.getenv("BASE_URL") or "").rstrip("/")
    if not base:
        raise RuntimeError("BASE_URL não definido")
    return f"{base}/checkin/{token}"

def gerar_qr_png(url: str) -> bytes:
    qr = qrcode.QRCode(
        version=None,                 # deixa o lib escolher
        error_correction=ERROR_CORRECT_M,  # melhor tolerância para projeção
        box_size=12,                  # AUMENTA o QR (8 -> 12 costuma ajudar muito)
        border=4,                     # margem branca maior (2 -> 4)
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()