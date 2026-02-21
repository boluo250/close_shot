from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageDraw, ImageFont, ImageOps


def add_text_watermark(image_bytes: bytes, watermark_text: str = "边拍") -> tuple[bytes, str]:
    with Image.open(BytesIO(image_bytes)) as im:
        orig_format = (im.format or "").upper()
        im = ImageOps.exif_transpose(im)
        if im.mode != "RGBA":
            im = im.convert("RGBA")
        width, height = im.size
        overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        try:
            font_size = max(16, int(min(width, height) * 0.035))
            font = ImageFont.truetype("DejaVuSans.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()

        text = watermark_text or "边拍"
        # Pillow 10+ 移除了 textsize，优先使用 textbbox，并保留向后兼容。
        try:
            left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
            text_width = right - left
            text_height = bottom - top
        except Exception:
            text_width, text_height = font.getsize(text)
        padding = max(10, int(text_height * 0.6))
        x = width - text_width - padding
        y = height - text_height - padding

        box = (x - padding, y - padding, x + text_width + padding, y + text_height + padding)
        draw.rectangle(box, fill=(0, 0, 0, 90))
        draw.text((x, y), text, font=font, fill=(255, 255, 255, 200))

        combined = Image.alpha_composite(im, overlay)
        output = BytesIO()
        content_type = "image/png"
        fmt = "PNG"
        if combined.mode != "RGBA":
            combined = combined.convert("RGBA")
        if orig_format in ("JPEG", "JPG"):
            fmt = "JPEG"
            content_type = "image/jpeg"
            combined = combined.convert("RGB")
        combined.save(output, format=fmt, quality=92)
        return output.getvalue(), content_type
