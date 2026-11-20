"""Image download / inspection / conversion for email-safe assets."""
import hashlib
import io
import os
import shutil
import subprocess
import tempfile
from collections import Counter

from PIL import Image

from . import colors

EMAIL_SAFE = {"JPEG", "PNG", "GIF"}


def _svg_to_png(data, width=600):
    """Convert SVG bytes to PNG bytes using cairosvg or rsvg-convert."""
    try:
        import cairosvg  # type: ignore
        return cairosvg.svg2png(bytestring=data, output_width=width)
    except Exception:
        pass
    exe = shutil.which("rsvg-convert")
    if exe:
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            f.write(data)
            path = f.name
        try:
            out = subprocess.run([exe, "-w", str(width), "--keep-aspect-ratio", path],
                                 capture_output=True, timeout=30)
            if out.returncode == 0 and out.stdout:
                return out.stdout
        finally:
            os.unlink(path)
    return None


def load(data, ctype=""):
    """Return a PIL image (or None) from raw bytes; handles SVG."""
    if not data:
        return None, None
    head = data[:600].lstrip().lower()
    is_svg = "svg" in (ctype or "") or head.startswith(b"<svg") or (head.startswith(b"<?xml") and b"<svg" in data[:2000].lower())
    if is_svg:
        png = _svg_to_png(data)
        if not png:
            return None, "SVG"
        data = png
        fmt = "SVG"
    else:
        fmt = None
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
        return im, fmt or im.format
    except Exception:
        return None, None


def dominant_colors(im, n=6):
    """Most common non-white/non-transparent colors of an image."""
    im = im.convert("RGBA")
    im.thumbnail((120, 120))
    counter = Counter()
    for r, g, b, a in im.getdata():
        if a < 200:
            continue
        # bucket colors to merge anti-aliasing noise
        counter[(r // 12 * 12, g // 12 * 12, b // 12 * 12)] += 1
    out = []
    for rgb, cnt in counter.most_common(40):
        h = colors.to_hex(rgb)
        if colors.luminance(h) > 0.85:  # near white
            continue
        if any(colors.similar(h, o, 40) for o, _ in out):
            continue
        out.append((h, cnt))
        if len(out) >= n:
            break
    return out


class AssetStore:
    """Writes converted images to <out>/assets and returns public URLs."""

    def __init__(self, out_dir, public_base):
        self.dir = os.path.join(out_dir, "assets")
        self.public_base = public_base.rstrip("/") if public_base else ""
        os.makedirs(self.dir, exist_ok=True)

    def save(self, im, name, fmt="PNG"):
        buf = io.BytesIO()
        if fmt == "JPEG":
            if im.mode in ("RGBA", "LA", "P"):
                bg = Image.new("RGB", im.size, "white")
                rgba = im.convert("RGBA")
                bg.paste(rgba, mask=rgba.split()[-1])
                im = bg
            im.convert("RGB").save(buf, "JPEG", quality=86, optimize=True, progressive=True)
            ext = "jpg"
        else:
            im.save(buf, "PNG", optimize=True)
            ext = "png"
        data = buf.getvalue()
        digest = hashlib.sha1(data).hexdigest()[:8]
        fname = f"{name}-{digest}.{ext}"
        with open(os.path.join(self.dir, fname), "wb") as f:
            f.write(data)
        return f"{self.public_base}/assets/{fname}" if self.public_base else f"assets/{fname}"


def square(im, size=600, bg="white"):
    """Fit image inside a square canvas (so product cards line up)."""
    im = im.convert("RGBA")
    im.thumbnail((size, size), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), bg)
    canvas.paste(im, ((size - im.width) // 2, (size - im.height) // 2), im)
    return canvas.convert("RGB")


def trim_transparent(im):
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        rgba = im.convert("RGBA")
        bbox = rgba.split()[-1].getbbox()
        if bbox:
            return rgba.crop(bbox)
    return im
