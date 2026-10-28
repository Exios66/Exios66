#!/usr/bin/env python3
"""Build the README artwork: assets/header.svg and assets/cards/*.svg.

Type: Roboto Serif for display, Roboto for text, Roboto Mono for the greeting,
labels and tags, with one teal accent on deep blue-grey surfaces. All text is
converted to vector outlines, so the images look identical on every device and
need no font loading. Edit the copy below, run the script, commit the SVGs.

    pip install fonttools uharfbuzz brotli
    python3 scripts/build_assets.py

University logo: put the official full-colour file at assets/logo/uw-madison.svg (or
.png) and re-run; the UW\u2013Madison badge then uses it. Without it a plain mortarboard
icon is drawn.

Fonts (in scripts/fonts/, licences alongside): Roboto, Roboto Serif, Roboto Mono.
"""
import io
import sys
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "scripts" / "fonts"
ASSETS = ROOT / "assets"

# Dark surfaces and teal accent borrowed from the portfolio site's dark mode.
BG, EDGE = "#131C20", "#25333A"            # --paper, --rule
ACCENT, ACCENT_SOFT = "#4FC1CD", "#16303A"  # --accent, --accent-soft
INK, MUTED = "#E6EDEF", "#93A3A9"           # --ink, --muted

# ----------------------------------------------------------------- typography
_cache = {}


class Face:
    def __init__(self, file):
        f = TTFont(FONTS / file)
        f.flavor = None
        buf = io.BytesIO()
        f.save(buf)
        raw = buf.getvalue()
        self.font = TTFont(io.BytesIO(raw))
        self.upm = self.font["head"].unitsPerEm
        self.hb = hb.Font(hb.Face(raw))
        self.glyphs = self.font.getGlyphSet()
        self.order = self.font.getGlyphOrder()


def face(file):
    if file not in _cache:
        _cache[file] = Face(file)
    return _cache[file]


def roboto(weight=400):
    return face(f"roboto-latin-{weight}-normal.woff2")


def roboto_serif(weight=600):
    return face(f"roboto-serif-latin-{weight}-normal.woff2")


def mono():
    return face("roboto-mono-latin-400-normal.woff2")


def shape(fc, text, size, tracking=0.0, outline=True):
    """Return (svg path d, cumulative x after each character, total width)."""
    s = size / fc.upm
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(fc.hb, buf, {"liga": False, "calt": False, "clig": False})
    d, x, ends = [], 0.0, {}
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        if info.codepoint == 0:
            raise ValueError(f"font has no glyph for a character in {text!r}")
        if outline:
            pen = SVGPathPen(fc.glyphs, ntos=lambda v: f"{v:.1f}".rstrip("0").rstrip(".") or "0")
            tp = TransformPen(pen, (s, 0, 0, -s, x + pos.x_offset * s, -pos.y_offset * s))
            fc.glyphs[fc.order[info.codepoint]].draw(tp)
            d.append(pen.getCommands())
        x += pos.x_advance * s + tracking
        ends[info.cluster] = x
    xs, last = [0.0], 0.0
    for i in range(len(text)):
        last = ends.get(i, last)
        xs.append(last)
    return "".join(d), xs, x - tracking


def width(fc, text, size, tracking=0.0):
    return shape(fc, text, size, tracking, outline=False)[2]


def _wrap(fc, text, size, max_w):
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if cur and width(fc, trial, size) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def wrap(fc, text, size, max_w):
    """Greedy wrap, then rebalance to the narrowest width with the same line count."""
    n = len(_wrap(fc, text, size, max_w))
    lo, hi = max_w * 0.5, max_w
    for _ in range(14):
        mid = (lo + hi) / 2
        if len(_wrap(fc, text, size, mid)) <= n:
            hi = mid
        else:
            lo = mid
    return _wrap(fc, text, size, hi + 1)


def text_path(fc, text, size, x, y, fill, tracking=0.0):
    d, _, _ = shape(fc, text, size, tracking)
    return f'<path transform="translate({x:.1f} {y:.1f})" fill="{fill}" d="{d}"/>'


def frame(w, h, x=0, y=0):
    return (f'<rect x="{x + 0.5}" y="{y + 0.5}" width="{w - 1}" height="{h - 1}" rx="12" '
            f'fill="{BG}" stroke="{EDGE}"/>')


def arrow(x, y, color=MUTED):
    """Small up-right arrow (external link), drawn as a stroke."""
    return (f'<path transform="translate({x:.1f} {y:.1f})" d="M0 10 L10 0 M3 0 H10 V7" fill="none" '
            f'stroke="{color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>')


def kicker(text, x, y, size=11, color=ACCENT):
    return text_path(mono(), text.upper(), size, x, y, color, tracking=size * 0.1)


def pills(items, x, y, max_x=None):
    """Filled accent-soft tag pills (the portfolio's .tag). Wraps past max_x. Returns (svg, bottom)."""
    out, cx, cy = [], x, y
    for t in items:
        cw = width(mono(), t, 11) + 22
        if max_x is not None and cx > x and cx + cw > max_x:
            cx, cy = x, cy + 32
        out.append(f'<rect x="{cx:.1f}" y="{cy}" width="{cw:.1f}" height="24" rx="12" fill="{ACCENT_SOFT}"/>')
        out.append(text_path(mono(), t, 11, cx + 11, cy + 16, ACCENT))
        cx += cw + 8
    return "\n".join(out), cy + 24


# --------------------------------------------------------------------- header
M = 4  # transparent margin around every image, so neighbours sit 8px apart


def build_header():
    W, H, LOOP = 792, 184, 12.0
    NAME = "JACK J. BURLESON"
    ROLE = "MACHINE LEARNING • DATA SCIENCE • AI ENGINEERING & SAFETY"
    GREET = "It’s a pleasure to meet you here..."
    f_name, f_role, f_greet = roboto_serif(600), mono(), mono()
    d1, xs1, w1 = shape(f_name, NAME, 40, tracking=40 * 0.06)
    d_role, _, wr = shape(f_role, ROLE, 11.5, tracking=11.5 * 0.14)
    d2, xs2, w2 = shape(f_greet, GREET, 17)
    Y1, YR, Y2 = 76 + M, 106 + M, 150 + M
    X1, XR, X2 = M + (W - w1) / 2, M + (W - wr) / 2, M + (W - w2) / 2

    ev = []

    def typed(line, n, t0, t1):
        for i in range(1, n + 1):
            ev.append((t0 + (t1 - t0) * (i - 1) / (n - 1), line, i))

    def erased(line, n, t0, t1):
        for i in range(1, n + 1):
            ev.append((t0 + (t1 - t0) * (i - 1) / (n - 1), line, n - i))

    n1, n2 = len(NAME), len(GREET)
    typed(1, n1, 0.7, 2.3)
    typed(2, n2, 2.8, 5.2)
    erased(2, n2, 9.0, 10.1)
    erased(1, n1, 10.25, 10.95)
    xs = {1: xs1, 2: xs2}
    X = {1: X1, 2: X2}
    Y = {1: Y1, 2: Y2}
    state = {1: 0, 2: 0}
    frames = [(0.0, dict(state), 1)]
    for t, line, n in ev:
        state[line] = n
        frames.append((t, dict(state), line))
    frames.append((LOOP, {1: 0, 2: 0}, 1))

    def pct(t):
        return f"{t / LOOP * 100:.3f}%"

    def kf(name, fn):
        out = [f"    @keyframes {name} {{"]
        for t, st, ln in frames:
            out.append(f"      {pct(t)} {{ {fn(st, ln)} animation-timing-function: steps(1, end); }}")
        out.append("    }")
        return "\n".join(out)

    def clip(line):
        return lambda st, ln: f"transform: scaleX({xs[line][st[line]]:.2f});"

    CUR = {1: (31, 36, 2.5), 2: (15, 21, 2)}   # (top above baseline, height, width)

    def cur(st, ln):
        top, h, w = CUR[ln]
        x = X[ln] + xs[ln][st[ln]] + 3
        return f"transform: translate({x:.2f}px, {Y[ln] - top:.2f}px) scale({w}, {h});"

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W + 2 * M}" height="{H + 2 * M}" viewBox="0 0 {W + 2 * M} {H + 2 * M}" role="img" aria-labelledby="t d">
  <title id="t">Jack J. Burleson</title>
  <desc id="d">Machine Learning, Data Science, AI Engineering &amp; Safety. It’s a pleasure to meet you here...</desc>
  <defs>
    <clipPath id="card"><rect x="{M + 0.5}" y="{M + 0.5}" width="{W - 1}" height="{H - 1}" rx="12"/></clipPath>
    <clipPath id="c1"><rect class="r1" x="{X1:.2f}" y="{Y1 - 48}" width="1" height="64"/></clipPath>
    <clipPath id="c2"><rect class="r2" x="{X2:.2f}" y="{Y2 - 26}" width="1" height="40"/></clipPath>
  </defs>
  <style>
    .r1, .r2 {{ transform-box: view-box; }}
    .r1 {{ transform-origin: {X1:.2f}px 0; animation: r1 {LOOP}s infinite; }}
    .r2 {{ transform-origin: {X2:.2f}px 0; animation: r2 {LOOP}s infinite; }}
    .cur {{ animation: cur {LOOP}s infinite; }}
    .bar {{ animation: blink 1s steps(1, end) infinite; }}
{kf("r1", clip(1))}
{kf("r2", clip(2))}
{kf("cur", cur)}
    @keyframes blink {{ 0%, 55% {{ opacity: 1; }} 56%, 100% {{ opacity: 0; }} }}
    @media (prefers-reduced-motion: reduce) {{
      .r1, .r2, .cur, .bar {{ animation: none; }}
      .r1 {{ transform: scaleX({xs1[-1]:.2f}); }} .r2 {{ transform: scaleX({xs2[-1]:.2f}); }}
      .cur {{ display: none; }}
    }}
  </style>

  {frame(W, H, M, M)}
  <rect x="{M}" y="{M}" width="{W}" height="4" fill="{ACCENT}" clip-path="url(#card)"/>

  <g clip-path="url(#c1)"><path transform="translate({X1:.2f} {Y1})" fill="{INK}" d="{d1}"/></g>
  <path transform="translate({XR:.2f} {YR})" fill="{ACCENT}" d="{d_role}"/>
  <g clip-path="url(#c2)"><path transform="translate({X2:.2f} {Y2})" fill="{MUTED}" d="{d2}"/></g>

  <g class="cur"><rect class="bar" x="0" y="0" width="1" height="1" fill="{ACCENT}"/></g>
</svg>
'''


# ---------------------------------------------------------------------- cards
# Copy is taken from the portfolio's project pages and each repository's README.
FEATURED = dict(
    file="digital-mailroom.svg",
    compact="digital-mailroom-compact.svg",  # swapped in on phones
    kicker="Capstone · American Family Insurance",
    title="Digital-Mailroom",
    desc=("Five Python packages and one LangGraph pipeline that joins legal-document routing, "
          "prompt experiments, deterministic scoring, and deployment, in a reproducible Docker environment."),
    tags=["13-node LangGraph pipeline", "5 document classes", "3,302-document dataset"],
    alt=("Digital-Mailroom, a capstone with American Family Insurance: five Python packages and one "
         "LangGraph pipeline for legal-document routing, scoring and deployment."),
    stages=["INTAKE", "CLASSIFY", "EXTRACT", "JUDGE", "COMPILE", "ARCHIVE"],
)

PROJECTS = [
    dict(file="mailroom-ml.svg", kicker="Training & calibration", title="Mailroom-ML",
         desc=("A ModernBERT classifier that handles the easy documents fast and knows, "
               "from calibrated confidence, when to pass one to an LLM."),
         tags=["PyTorch", "Calibration", "ONNX"],
         alt="Mailroom-ML: a calibrated ModernBERT document classifier. PyTorch, Calibration, ONNX."),
    dict(file="rvl-cdip-classifier.svg", kicker="Vision LLMs & prompts", title="RVL-CDIP-Classifier",
         desc=("Zero-shot document classification with vision LLMs: 29 tracked prompt versions, "
               "checked on larger slices, with the cost of every page measured."),
         tags=["OpenRouter", "Evaluation", "Error analysis"],
         alt="RVL-CDIP-Classifier: zero-shot document classification with vision LLMs. OpenRouter, Evaluation, Error analysis."),
    dict(file="psychometric-digital-twin.svg", kicker="Behavioral ML research", title="Psychometric Digital Twin",
         desc=("Can an LLM persona predict communication apprehension? Tested against seven "
               "classical models, the personas did not beat simple baselines."),
         tags=["scikit-learn", "XGBoost", "SHAP"],
         alt="Psychometric Digital Twin: LLM personas versus seven classical models on behavioral prediction. scikit-learn, XGBoost, SHAP."),
    dict(file="wave-laboratory.svg", kicker="Simulation & graphics", title="Wave Laboratory",
         desc=("A real-time 3D ocean to experiment with: spectral wave models, rogue waves, "
               "and ships that move in six directions, rendered with WebGL 2."),
         tags=["TypeScript", "Three.js", "Physics"],
         alt="Wave Laboratory: a real-time 3D ocean simulation in the browser. TypeScript, Three.js, Physics."),
]


def wrap_svg(w, h, alt, title, style, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w + 2 * M}" height="{h + 2 * M}" '
            f'viewBox="0 0 {w + 2 * M} {h + 2 * M}" role="img" aria-label="{alt}">\n<title>{title}</title>\n'
            f'{style}<g transform="translate({M} {M})">\n{frame(w, h)}\n{body}\n</g>\n</svg>\n')


def build_featured(c, compact=False):
    W, PAD = (392, 24) if compact else (792, 36)
    st = c["stages"]
    fs, trk = (8.5, 0.9) if compact else (10, 1.4)
    f_lab = mono()
    tws = [width(f_lab, t, fs, trk) for t in st]
    x0, x1 = PAD + tws[0] / 2, W - PAD - tws[-1] / 2   # first/last labels sit flush with the card margins
    step = (x1 - x0) / (len(st) - 1)
    ts, ds, dl = (28, 14, 21) if compact else (36, 16, 25)
    out = [kicker(c["kicker"], PAD, 38 if compact else 40), arrow(W - PAD - 10, 28 if compact else 30)]
    ty = 78 if compact else 86
    out.append(text_path(roboto_serif(600), c["title"], ts, PAD, ty, INK))
    lines = wrap(roboto(400), c["desc"], ds, W - 2 * PAD - (0 if compact else 60))
    dy = ty + (30 if compact else 34)
    for i, ln in enumerate(lines):
        out.append(text_path(roboto(400), ln, ds, PAD, dy + i * dl, MUTED))
    chips_svg, bottom = pills(c["tags"], PAD, dy + len(lines) * dl - 8, max_x=W - PAD)
    out.append(chips_svg)
    # conveyor: six stage nodes on a line, an envelope rides along it
    ly = bottom + 42
    out.append(f'<line x1="{x0:.1f}" y1="{ly}" x2="{x1:.1f}" y2="{ly}" stroke="{EDGE}" stroke-width="2" stroke-linecap="round"/>')
    for i, name in enumerate(st):
        cx = x0 + i * step
        out.append(f'<circle cx="{cx:.1f}" cy="{ly}" r="5" fill="{BG}" stroke="{MUTED}" stroke-width="1.5"/>')
        out.append(text_path(f_lab, name, fs, cx - tws[i] / 2, ly + 25, MUTED, tracking=trk))
    out.append(f'<g class="env"><g transform="translate({x0 - 7:.1f} {ly - 23})">'
               f'<rect width="14" height="10" rx="1.5" fill="{ACCENT}"/>'
               f'<path d="M1.2 1.6 L7 6 L12.8 1.6" fill="none" stroke="{BG}" stroke-width="1.2" stroke-linejoin="round"/>'
               f'</g></g>')
    H = ly + 25 + 24
    dist = x1 - x0
    style = ("<style>\n  .env { animation: ride 9s linear infinite; }\n"
             f"  @keyframes ride {{ 0% {{ transform: translateX(0); }} 88% {{ transform: translateX({dist:.1f}px); }} "
             f"100% {{ transform: translateX({dist:.1f}px); }} }}\n"
             f"  @media (prefers-reduced-motion: reduce) {{ .env {{ animation: none; transform: translateX({dist / 2:.1f}px); }} }}\n"
             "</style>\n")
    return wrap_svg(W, H, c["alt"], c["title"], style, "\n".join(out))


def build_card(c):
    W, H, PAD = 392, 206, 24
    out = [kicker(c["kicker"], PAD, 38), arrow(W - PAD - 10, 28),
           text_path(roboto(700), c["title"], 19, PAD, 72, INK)]
    lines = wrap(roboto(400), c["desc"], 14, W - 2 * PAD)
    assert len(lines) <= 3, f'{c["title"]}: description wraps to {len(lines)} lines'
    for i, ln in enumerate(lines):
        out.append(text_path(roboto(400), ln, 14, PAD, 100 + i * 21, MUTED))
    chips_svg, bottom = pills(c["tags"], PAD, H - 46, max_x=W - PAD)
    assert bottom == H - 46 + 24, f'{c["title"]}: tags wrapped'
    out.append(chips_svg)
    return wrap_svg(W, H, c["alt"], c["title"], "", "\n".join(out))


# --------------------------------------------------------------------- badges
# Typographic badges only: no institutional crests or product logos are reproduced.
UW_RED, WHITE = "#C5050C", "#FFFFFF"   # cardinal red used for the UW–Madison badge


def _logo_data(path):
    """Return (data URI, aspect ratio w/h) for an SVG or PNG logo file."""
    import base64
    import re
    raw = Path(path).read_bytes()
    if Path(path).suffix.lower() == ".svg":
        head = raw[:4000].decode("utf-8", "ignore")
        vb = re.search(r'viewBox="[-\d.]+[ ,]+[-\d.]+[ ,]+([\d.]+)[ ,]+([\d.]+)"', head)
        if vb:
            aspect = float(vb.group(1)) / float(vb.group(2))
        else:
            wh = [re.search(rf'\b{k}="([\d.]+)', head) for k in ("width", "height")]
            aspect = float(wh[0].group(1)) / float(wh[1].group(1)) if all(wh) else 1.0
        mime = "image/svg+xml"
    else:
        from PIL import Image
        with Image.open(path) as im:
            aspect = im.width / im.height
        mime = "image/png"
    return f"data:{mime};base64,{base64.b64encode(raw).decode()}", aspect


def build_uw_badge(logo=None):
    """University badge. With an official logo file it sits on a white cap; without one,
    a plain mortarboard icon on cardinal red is drawn instead."""
    H = 68
    title = "UNIVERSITY OF WISCONSIN\u2013MADISON"
    sub = "M.S. DATA SCIENCE IN HUMAN BEHAVIOR \u00b7 MADISON, WI"
    cap_w, art = 68, ""
    if logo:
        uri, aspect = _logo_data(logo)
        lh = 52 if aspect < 1 else 44            # tall crests get more height
        lw = min(lh * aspect, 120)
        lh = lw / aspect
        cap_w = max(68, round(lw + 28))
        art = (f'<rect x="0" y="0" width="{cap_w}" height="{H}" fill="{WHITE}" clip-path="url(#plate)"/>'
               f'<image x="{(cap_w - lw) / 2:.1f}" y="{(H - lh) / 2:.1f}" width="{lw:.1f}" height="{lh:.1f}" '
               f'preserveAspectRatio="xMidYMid meet" href="{uri}"/>')
    else:
        art = (f'<rect x="0" y="0" width="{cap_w}" height="{H}" fill="{UW_RED}" clip-path="url(#plate)"/>'
               f'<g fill="{WHITE}" stroke="{WHITE}" stroke-linejoin="round">'
               f'<path d="M34 19 L54 28 L34 37 L14 28 Z" stroke-width="1"/>'
               f'<path d="M24 33.5 V40 Q34 46 44 40 V33.5 L34 38.5 Z" stroke-width="1" opacity=".92"/>'
               f'<path d="M54 28 V40" fill="none" stroke-width="1.6" stroke-linecap="round"/>'
               f'<circle cx="54" cy="42" r="2" stroke="none"/></g>')
    tx = cap_w + 20
    t_w = width(roboto_serif(600), title, 15.5, 15.5 * 0.06)
    s_w = width(mono(), sub, 10.5, 10.5 * 0.08)
    W = round(max(520, tx + max(t_w, s_w) + 28))
    out = [f'<clipPath id="plate"><rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="14"/></clipPath>',
           frame(W, H).replace('rx="12"', 'rx="14"'), art,
           text_path(roboto_serif(600), title, 15.5, tx, 32, INK, tracking=15.5 * 0.06),
           text_path(mono(), sub, 10.5, tx, 51, MUTED, tracking=10.5 * 0.08)]
    alt = "University of Wisconsin\u2013Madison. M.S. Data Science in Human Behavior. Madison, WI."
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W + 2 * M}" height="{H + 2 * M}" '
            f'viewBox="0 0 {W + 2 * M} {H + 2 * M}" role="img" aria-label="{alt}">\n<title>{alt}</title>\n'
            f'<g transform="translate({M} {M})">\n' + "\n".join(out) + '\n</g>\n</svg>\n'), W + 2 * M


# (category, tool, brand colour): the category is the small label on the left of each badge.
# Colours are each project's well-known brand colour; no logos are reproduced.
TOOL_BADGES = [
    ("LANGUAGE", "Python", "#3776AB"), ("LANGUAGE", "R", "#276DC3"),
    ("DEEP LEARNING", "PyTorch", "#EE4C2C"), ("CLASSICAL ML", "scikit-learn", "#F7931E"),
    ("AGENTS", "LangGraph", "#2D9C84"), ("MODELS", "Hugging Face", "#FFD21E"),
    ("SERVING", "vLLM", "#30A2FF"), ("CONTAINERS", "Docker", "#2496ED"),
]


def slug(text):
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in text).strip("-")


def _lum(hex_color):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def _on(bg):
    """Dark or white text, whichever contrasts more with the brand colour."""
    dark, light = "#0D1117", "#FFFFFF"
    c = lambda a, b: (max(_lum(a), _lum(b)) + 0.05) / (min(_lum(a), _lum(b)) + 0.05)
    return dark if c(bg, dark) >= c(bg, light) else light


def build_tool_badge(category, tool, brand):
    H, PAD = 32, 12
    cat_w = width(mono(), category, 9, 9 * 0.12) + 2 * PAD
    val_w = width(roboto(500), tool, 13) + 2 * PAD
    W = cat_w + val_w
    alt = f"{tool} ({category.lower()})"
    out = [f'<clipPath id="pill"><rect x="0.5" y="0.5" width="{W - 1:.1f}" height="{H - 1}" rx="16"/></clipPath>',
           f'<rect x="0.5" y="0.5" width="{W - 1:.1f}" height="{H - 1}" rx="16" fill="{BG}"/>',
           f'<rect x="0" y="0" width="{cat_w:.1f}" height="{H}" fill="{brand}" clip-path="url(#pill)"/>',
           f'<rect x="0.5" y="0.5" width="{W - 1:.1f}" height="{H - 1}" rx="16" fill="none" stroke="{brand}" stroke-opacity=".7"/>',
           text_path(mono(), category, 9, PAD, 19.5, _on(brand), tracking=9 * 0.12),
           text_path(roboto(500), tool, 13, cat_w + PAD, 20.5, INK)]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W + 2 * M:.0f}" height="{H + 2 * M}" '
            f'viewBox="0 0 {W + 2 * M:.1f} {H + 2 * M}" role="img" aria-label="{alt}">\n<title>{alt}</title>\n'
            f'<g transform="translate({M} {M})">\n' + "\n".join(out) + '\n</g>\n</svg>\n')


def main():
    ASSETS.mkdir(exist_ok=True)
    (ASSETS / "cards").mkdir(exist_ok=True)
    (ASSETS / "header.svg").write_text(build_header())
    (ASSETS / "cards" / FEATURED["file"]).write_text(build_featured(FEATURED))
    (ASSETS / "cards" / FEATURED["compact"]).write_text(build_featured(FEATURED, compact=True))
    for p in PROJECTS:
        (ASSETS / "cards" / p["file"]).write_text(build_card(p))
    (ASSETS / "badges").mkdir(exist_ok=True)
    logo = next((q for q in (ASSETS / "logo" / "uw-madison.svg", ASSETS / "logo" / "uw-madison.png") if q.exists()), None)
    if len(sys.argv) > 1:   # optional: python3 scripts/build_assets.py path/to/logo.svg|png
        logo = sys.argv[1]
    svg, badge_w = build_uw_badge(logo)
    (ASSETS / "badges" / "uw-madison.svg").write_text(svg)
    print("UW badge:", "official logo" if logo else "mortarboard placeholder", f"(width {badge_w})")
    for cat, tool, brand in TOOL_BADGES:
        (ASSETS / "badges" / f"{slug(tool)}.svg").write_text(build_tool_badge(cat, tool, brand))
    print("wrote header, ", 2 + len(PROJECTS), "cards and", 1 + len(TOOL_BADGES), "badges")


if __name__ == "__main__":
    main()
