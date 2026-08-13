"""Generate QR code images for certificate verification links."""

from __future__ import annotations

from io import BytesIO
from typing import Optional


def generate_qr_png_bytes(
    url: str,
    *,
    box_size: int = 6,
    border: int = 1,
    center_logo_bytes: Optional[bytes] = None,
    logo_scale: float = 0.22,
) -> bytes:
    try:
        import qrcode
        from PIL import Image
    except ImportError as exc:
        raise ImportError(
            "qrcode and Pillow are required for certificate verification QR codes. "
            "Install with: pip install 'qrcode>=7.4.2' Pillow"
        ) from exc

    use_logo = bool(center_logo_bytes)
    qr = qrcode.QRCode(
        version=None,
        error_correction=(
            qrcode.constants.ERROR_CORRECT_H
            if use_logo
            else qrcode.constants.ERROR_CORRECT_M
        ),
        box_size=box_size,
        border=border,
    )
    qr.add_data(url)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white").convert("RGBA")

    if use_logo and center_logo_bytes:
        image = _embed_center_logo(image, center_logo_bytes, logo_scale=logo_scale)

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _embed_center_logo(image, logo_bytes: bytes, *, logo_scale: float) -> "Image.Image":
    from PIL import Image

    qr_w, qr_h = image.size
    logo_max = max(16, int(min(qr_w, qr_h) * logo_scale))

    with Image.open(BytesIO(logo_bytes)) as raw_logo:
        logo = raw_logo.convert("RGBA")
        logo.thumbnail((logo_max, logo_max), Image.Resampling.LANCZOS)

        pad = max(3, logo_max // 10)
        badge = Image.new("RGBA", (logo.size[0] + 2 * pad, logo.size[1] + 2 * pad), (255, 255, 255, 255))
        badge.paste(logo, (pad, pad), logo)

    position = ((qr_w - badge.size[0]) // 2, (qr_h - badge.size[1]) // 2)
    image.paste(badge, position, badge)
    return image
