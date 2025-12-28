import io
import qrcode

class QRCodeService:
    def __init__(self, box_size: int = 8, border: int = 2):
        self.box_size = box_size
        self.border = border

    def png_for_url(self, url: str) -> bytes:
        qr = qrcode.QRCode(
            box_size=self.box_size,
            border=self.border,
        )
        qr.add_data(url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()