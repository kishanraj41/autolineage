"""Generate AutoLineage brand assets (C1 mark, P2 palette) as SVG + PNG + ICO.

Text is converted to outlines with fontTools so the SVGs render identically
everywhere (GitHub, PyPI, slides) without needing the fonts installed.
IBM Plex Mono / Sans are SIL OFL; outlining them in a logo is permitted.
"""
import glob, io, os, sys
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
import cairosvg
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.environ.get("PLEX_FONTS", os.path.join(HERE, "..", "fonts"))
OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)

# P2 palette
AUB = "#2A1236"      # aubergine: ink on light, ground on dark
LIME = "#C8F03C"     # accent on dark
OLIVE = "#6E9A00"    # accent on light (lime is too faint on white)
LIGHT = "#F3EAF7"    # bars on dark
MUTED_L = "#7A6884"  # "auto" on light
MUTED_D = "#B9A9C2"  # "auto" on dark


def font(path_glob):
    return TTFont(glob.glob(os.path.join(FONTS, path_glob))[0])

MONO_R = font("fontsource-ibm-plex-mono-*/files/ibm-plex-mono-latin-400-normal.woff")
MONO_B = font("fontsource-ibm-plex-mono-*/files/ibm-plex-mono-latin-600-normal.woff")
SANS_R = font("fontsource-ibm-plex-sans-*/files/ibm-plex-sans-latin-400-normal.woff")


def text_path(f, text, size, x, baseline, fill):
    """Return (svg <path>, advance width) for text set in font f."""
    gs = f.getGlyphSet()
    cmap = f.getBestCmap()
    upm = f["head"].unitsPerEm
    s = size / upm
    pen = SVGPathPen(gs)
    cx = 0
    for ch in text:
        g = cmap[ord(ch)]
        tp = TransformPen(pen, (s, 0, 0, -s, x + cx * s, baseline))
        gs[g].draw(tp)
        cx += f["hmtx"][g][0]
    return f'<path fill="{fill}" d="{pen.getCommands()}"/>', cx * s


def mark(ink, accent, ghost_opacity=0.3):
    """C1 'Tree' mark, detailed, in a 100x100 box."""
    return (
        f'<path d="M14 20V74M14 20H24M14 38H24M14 56H24M14 74H24" stroke="{ink}" stroke-width="4.5" stroke-linecap="round" fill="none"/>'
        f'<rect x="24" y="14" width="62" height="12" rx="6" fill="{ink}"/>'
        f'<rect x="24" y="32" width="62" height="12" rx="6" fill="{ink}"/>'
        f'<path d="M51 56H84" fill="none" stroke="{ink}" stroke-opacity="{ghost_opacity + 0.15}" stroke-width="4" stroke-linecap="round" stroke-dasharray="0.01 5.5"/>'
        f'<rect x="24" y="50" width="20" height="12" rx="6" fill="{accent}"/>'
        f'<rect x="24" y="68" width="20" height="12" rx="6" fill="{ink}"/>'
    )


def mark_small(ink, accent):
    """Heavier, ghost-free variant for 16-48 px."""
    return (
        f'<path d="M10 22V78M10 22H22M10 50H22M10 78H22" stroke="{ink}" stroke-width="9" stroke-linecap="round" fill="none"/>'
        f'<rect x="22" y="12" width="70" height="20" rx="10" fill="{ink}"/>'
        f'<rect x="22" y="40" width="26" height="20" rx="10" fill="{accent}"/>'
        f'<rect x="22" y="68" width="26" height="20" rx="10" fill="{ink}"/>'
    )


def svg(w, h, body, title="AutoLineage"):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img">'
            f'<title>{title}</title>{body}</svg>\n')


def write(name, content):
    with open(os.path.join(OUT, name), "w") as fh:
        fh.write(content)


def png(svg_text, name, w, h):
    cairosvg.svg2png(bytestring=svg_text.encode(), write_to=os.path.join(OUT, name), output_width=w, output_height=h)


# 1. Bare marks (transparent background)
write("autolineage-mark.svg", svg(100, 100, mark(AUB, OLIVE)))
write("autolineage-mark-dark.svg", svg(100, 100, mark(LIGHT, LIME, 0.35)))

# 2. App icon: aubergine tile, light bars, lime accent. Primary avatar/favicon.
icon = svg(512, 512, f'<rect width="512" height="512" rx="112" fill="{AUB}"/>'
                     f'<g transform="translate(76 76) scale(3.6)">{mark(LIGHT, LIME, 0.35)}</g>')
icon_small = svg(100, 100, f'<rect width="100" height="100" rx="22" fill="{AUB}"/>'
                           f'<g transform="translate(8 8) scale(0.84)">{mark_small(LIGHT, LIME)}</g>')
write("autolineage-icon.svg", icon)
write("autolineage-icon-small.svg", icon_small)
for s in (512, 256, 128):
    png(icon, f"autolineage-icon-{s}.png", s, s)
for s in (64, 48, 32, 16):
    png(icon_small, f"autolineage-icon-{s}.png", s, s)
Image.open(os.path.join(OUT, "autolineage-icon-48.png")).save(
    os.path.join(OUT, "favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48)])

# 3. Lockups: mark + outlined "autolineage" wordmark
def lockup(ink, accent, muted, ghost):
    size, gap = 52, 22
    a, wa = text_path(MONO_R, "auto", size, 100 + gap, 68, muted)
    b, wb = text_path(MONO_B, "lineage", size, 100 + gap + wa, 68, ink)
    w = int(100 + gap + wa + wb + 6)
    return svg(w, 100, mark(ink, accent, ghost) + a + b), w

lk, lw = lockup(AUB, OLIVE, MUTED_L, 0.3)
lkd, _ = lockup(LIGHT, LIME, MUTED_D, 0.35)
write("autolineage-lockup.svg", lk)
write("autolineage-lockup-dark.svg", lkd)
png(lk, "autolineage-lockup.png", lw * 4, 400)

# 4. GitHub social preview, 1280x640
parts = [f'<rect width="1280" height="640" fill="{AUB}"/>',
         f'<g transform="translate(110 170) scale(3.0)">{mark(LIGHT, LIME, 0.35)}</g>']
x0 = 480
p, wa = text_path(MONO_R, "auto", 92, x0, 290, MUTED_D); parts.append(p)
p, _ = text_path(MONO_B, "lineage", 92, x0 + wa, 290, LIGHT); parts.append(p)
p, _ = text_path(SANS_R, "Find the pandas operation that", 36, x0, 372, "#D9CCE0"); parts.append(p)
p, _ = text_path(SANS_R, "silently broke your model.", 36, x0, 420, "#D9CCE0"); parts.append(p)
p, _ = text_path(MONO_R, "pip install autolineage", 28, x0, 500, LIME); parts.append(p)
social = svg(1280, 640, "".join(parts), "AutoLineage: find the pandas operation that silently broke your model")
write("autolineage-social-preview.svg", social)
png(social, "autolineage-social-preview.png", 1280, 640)

print("\n".join(sorted(os.listdir(OUT))))
