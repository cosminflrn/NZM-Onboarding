"""Color helpers: parsing, scoring and deriving an email palette."""
import colorsys
import re

HEX_RE = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
RGB_RE = re.compile(r"rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})(?:\s*,\s*([\d.]+))?\s*\)")


def norm_hex(value):
    """Return '#rrggbb' (lowercase) or None."""
    if not value:
        return None
    value = value.strip()
    m = HEX_RE.fullmatch(value) if value.startswith("#") else None
    if m:
        h = m.group(1)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return "#" + h.lower()
    m = RGB_RE.fullmatch(value)
    if m:
        if m.group(4) is not None and float(m.group(4)) < 0.5:
            return None
        r, g, b = (min(255, int(m.group(i))) for i in (1, 2, 3))
        return "#%02x%02x%02x" % (r, g, b)
    return None


def find_colors(text):
    """All colors (normalized hex) appearing in a CSS/HTML string."""
    out = []
    for m in HEX_RE.finditer(text):
        # skip things like url(#id) or html entities (&#123;)
        start = m.start()
        if start > 0 and text[start - 1] in "&":
            continue
        out.append(norm_hex(m.group(0)))
    for m in RGB_RE.finditer(text):
        c = norm_hex(m.group(0))
        if c:
            out.append(c)
    return [c for c in out if c]


def to_rgb(h):
    h = norm_hex(h)
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def to_hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(v)))) for v in rgb)


def hls(h):
    r, g, b = (v / 255 for v in to_rgb(h))
    return colorsys.rgb_to_hls(r, g, b)  # hue, lightness, saturation


def luminance(h):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = to_rgb(h)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def mix(a, b, t):
    """Mix color a with b; t=0 -> a, t=1 -> b."""
    ra, rb = to_rgb(a), to_rgb(b)
    return to_hex([ra[i] + (rb[i] - ra[i]) * t for i in range(3)])


def is_brandish(h):
    """A saturated, mid-lightness color that could be a brand/accent color."""
    _, l, s = hls(h)
    return s >= 0.28 and 0.18 <= l <= 0.78


def is_dark(h):
    return luminance(h) < 0.045


def darken_until_contrast(h, against="#ffffff", target=3.0):
    c = h
    for _ in range(30):
        if contrast(c, against) >= target:
            return c
        c = mix(c, "#000000", 0.08)
    return c


def similar(a, b, tol=28):
    ra, rb = to_rgb(a), to_rgb(b)
    return sum(abs(ra[i] - rb[i]) for i in range(3)) <= tol


def palette(accent, dark=None):
    """Derive every color role used by the templates from 1-2 brand colors."""
    accent = norm_hex(accent) or "#e63946"
    # buttons use white text: keep the accent readable
    accent_btn = darken_until_contrast(accent, "#ffffff", 3.0)
    dark = norm_hex(dark) if dark else None
    if not dark or not is_dark(dark):
        h, _, s = hls(accent)
        r, g, b = colorsys.hls_to_rgb(h, 0.10, min(s, 0.35))
        dark = to_hex((r * 255, g * 255, b * 255))
    return {
        "accent": accent_btn,           # buttons, highlights, top bars
        "accent_original": accent,
        "accent_text": "#ffffff",
        "dark": dark,                   # header/footer bars, strong text
        "light": mix(accent, "#ffffff", 0.90),   # soft section backgrounds
        "muted": mix(dark, "#ffffff", 0.40),     # small footer text
    }
