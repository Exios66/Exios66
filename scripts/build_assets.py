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

Photo carousel: put photos in assets/photos/ (optionally described by photos.json) and
re-run; needs Pillow (pip install pillow). Without photos the gallery is skipped.

Fonts (in scripts/fonts/, licences alongside): Roboto, Roboto Serif, Roboto Mono.
"""
import base64
import io
import json
import sys
from datetime import date, timedelta
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
PINK = "#FE01B1"                            # second accent, used sparingly: cursor, arrows, highlights
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


def ink_bounds(fc, text, size):
    """Return (xmin, ymin, xmax, ymax) of the glyph outlines, y pointing down from the baseline."""
    from fontTools.pens.boundsPen import BoundsPen
    s = size / fc.upm
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(fc.hb, buf, {"liga": False, "calt": False, "clig": False})
    bp, x = BoundsPen(fc.glyphs), 0.0
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        tp = TransformPen(bp, (s, 0, 0, -s, x + pos.x_offset * s, -pos.y_offset * s))
        fc.glyphs[fc.order[info.codepoint]].draw(tp)
        x += pos.x_advance * s
    return bp.bounds


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


def pills(items, x, y, max_x=None, size=11, h=24, pad=11):
    """Filled accent-soft tag pills (the portfolio's .tag). Wraps past max_x. Returns (svg, bottom)."""
    out, cx, cy = [], x, y
    for t in items:
        cw = width(mono(), t, size) + 2 * pad
        if max_x is not None and cx > x and cx + cw > max_x:
            cx, cy = x, cy + h + 8
        out.append(f'<rect x="{cx:.1f}" y="{cy}" width="{cw:.1f}" height="{h}" rx="{h / 2}" fill="{ACCENT_SOFT}"/>')
        out.append(text_path(mono(), t, size, cx + pad, cy + h / 2 + size * 0.36, ACCENT))
        cx += cw + 8
    return "\n".join(out), cy + h


# --------------------------------------------------------------------- header
M = 4  # transparent margin around every image, so neighbours sit 8px apart


def build_header(compact=False):
    """Typing header. compact=True is the phone variant: smaller type, role line on two lines."""
    LOOP = 12.0
    NAME = "JACK J. BURLESON"
    GREET = "It’s a pleasure to meet you here..."
    if compact:
        W, H = 336, 164
        name_sz, role_sz, greet_sz = 24, 9.5, 13.5
        roles = ["MACHINE LEARNING • DATA SCIENCE", "AI ENGINEERING & SAFETY"]
        y1, yroles, y2 = 56, (80, 95), 134
        cur_cfg = {1: (19, 24, 2), 2: (11, 15, 1.6)}      # cursor: (top above baseline, height, width)
        clip1, clip2 = (36, 46), (20, 28)                  # clip: (top above baseline, height)
        tab = 40
    else:
        W, H = 792, 184
        name_sz, role_sz, greet_sz = 40, 11.5, 17
        roles = ["MACHINE LEARNING • DATA SCIENCE • AI ENGINEERING & SAFETY"]
        y1, yroles, y2 = 76, (106,), 150
        cur_cfg = {1: (31, 36, 2.5), 2: (15, 21, 2)}
        clip1, clip2 = (48, 64), (26, 40)
        tab = 56
    d1, xs1, w1 = shape(roboto_serif(600), NAME, name_sz, tracking=name_sz * 0.06)
    d2, xs2, w2 = shape(mono(), GREET, greet_sz)
    role_paths = []
    for line, yr in zip(roles, yroles):
        dr, _, wr = shape(mono(), line, role_sz, tracking=role_sz * 0.14)
        role_paths.append(f'<path transform="translate({M + (W - wr) / 2:.2f} {yr + M})" fill="{ACCENT}" d="{dr}"/>')
    Y1, Y2 = y1 + M, y2 + M
    X1, X2 = M + (W - w1) / 2, M + (W - w2) / 2

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

    def cur(st, ln):
        top, h, w = cur_cfg[ln]
        x = X[ln] + xs[ln][st[ln]] + 3
        return f"transform: translate({x:.2f}px, {Y[ln] - top:.2f}px) scale({w}, {h});"

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W + 2 * M}" height="{H + 2 * M}" viewBox="0 0 {W + 2 * M} {H + 2 * M}" role="img" aria-labelledby="t d">
  <title id="t">Jack J. Burleson</title>
  <desc id="d">Machine Learning, Data Science, AI Engineering &amp; Safety. It’s a pleasure to meet you here...</desc>
  <defs>
    <clipPath id="card"><rect x="{M + 0.5}" y="{M + 0.5}" width="{W - 1}" height="{H - 1}" rx="12"/></clipPath>
    <clipPath id="c1"><rect class="r1" x="{X1:.2f}" y="{Y1 - clip1[0]}" width="1" height="{clip1[1]}"/></clipPath>
    <clipPath id="c2"><rect class="r2" x="{X2:.2f}" y="{Y2 - clip2[0]}" width="1" height="{clip2[1]}"/></clipPath>
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
  <rect x="{M}" y="{M}" width="{tab}" height="4" fill="{PINK}" clip-path="url(#card)"/>

  <g clip-path="url(#c1)"><path transform="translate({X1:.2f} {Y1})" fill="{INK}" d="{d1}"/></g>
  {chr(10).join("  " + r for r in role_paths).strip()}
  <g clip-path="url(#c2)"><path transform="translate({X2:.2f} {Y2})" fill="{MUTED}" d="{d2}"/></g>

  <g class="cur"><rect class="bar" x="0" y="0" width="1" height="1" fill="{PINK}"/></g>
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
    dict(file="mapreduce-reloaded.svg", kicker="Distributed systems", title="MapReduce-Reloaded",
         desc=("From-scratch MapReduce in Go: all 23 features of Google\u2019s paper, surviving worker "
               "crashes and coordinator restarts, with benchmarks."),
         tags=["Go", "Python", "gRPC"],
         alt="MapReduce-Reloaded: a from-scratch rebuild of Google's MapReduce in Go with all 23 paper features, crash recovery and benchmarks. Go, Python, gRPC."),
    dict(file="psychometric-digital-twin.svg", kicker="Behavioral ML research", title="Psychometric Digital Twin",
         desc=("LLM personas vs seven cross-validated classical ML models, from Ridge to XGBoost, "
               "on 241 respondents. The personas did not beat the simple models."),
         tags=["scikit-learn", "XGBoost", "SHAP"],
         alt="Psychometric Digital Twin: LLM personas compared with seven cross-validated classical ML models, from Ridge to XGBoost, on 241 respondents. The personas did not beat the simple models. scikit-learn, XGBoost, SHAP."),
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
    out = [kicker(c["kicker"], PAD, 38 if compact else 40), arrow(W - PAD - 10, 28 if compact else 30, PINK)]
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
               f'<rect width="14" height="10" rx="1.5" fill="{PINK}"/>'
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
    out = [kicker(c["kicker"], PAD, 38), arrow(W - PAD - 10, 28, PINK),
           text_path(roboto(700), c["title"], 19, PAD, 72, INK)]
    lines = wrap(roboto(400), c["desc"], 14, W - 2 * PAD)
    assert len(lines) <= 3, f'{c["title"]}: description wraps to {len(lines)} lines'
    for i, ln in enumerate(lines):
        out.append(text_path(roboto(400), ln, 14, PAD, 100 + i * 21, MUTED))
    chips_svg, bottom = pills(c["tags"], PAD, H - 46, max_x=W - PAD)
    assert bottom == H - 46 + 24, f'{c["title"]}: tags wrapped'
    out.append(chips_svg)
    return wrap_svg(W, H, c["alt"], c["title"], "", "\n".join(out))


def build_card_compact(c):
    """Phone variant of a project card: kicker, title and two tags (no description)."""
    W, H, PAD = 176, 122, 14
    out = [kicker(c["kicker"], PAD, 26, size=8.5), arrow(W - PAD - 8, 17, PINK)]
    lines = wrap(roboto(700), c["title"], 14, W - 2 * PAD)
    for i, ln in enumerate(lines):
        out.append(text_path(roboto(700), ln, 14, PAD, 52 + i * 18, INK))
    chips_svg, bottom = pills(c["tags"][:2], PAD, H - 36, max_x=W - PAD, size=9, h=20, pad=8)
    assert bottom == H - 36 + 20, f'{c["title"]}: compact tags wrapped'
    out.append(chips_svg)
    return wrap_svg(W, H, c["alt"], c["title"], "", "\n".join(out))


# --------------------------------------------------------------------- badges
# The university badge uses the official crest from assets/logo/ (supplied by the author) when that
# file exists, and a plain mortarboard icon otherwise. Tool badges use brand colours only, no logos.
UW_RED, WHITE = "#C5050C", "#FFFFFF"   # cardinal red used for the UW–Madison badge


def _logo_data(path):
    """Return a logo's base64 data URI and width/height aspect ratio.

    A .svg suffix selects SVG; all other suffixes require a PNG signature.
    SVG dimensions come from viewBox, then width/height, within the first
    4,000 bytes; missing dimensions default to a square.

    File errors propagate. Invalid PNG signatures or SVG numbers raise
    ValueError, truncated PNG dimensions raise struct.error, and a zero
    height raises ZeroDivisionError.
    """
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
        import struct
        if raw[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError(f"{path}: logo must be an SVG or a PNG file")
        w, h = struct.unpack(">II", raw[16:24])   # IHDR width and height
        aspect = w / h
        mime = "image/png"
    return f"data:{mime};base64,{base64.b64encode(raw).decode()}", aspect


def build_uw_badge(logo=None, compact=False):
    """Return (university badge SVG, total width in pixels), including margins.

    A truthy logo path embeds an SVG or PNG on a white cap; a falsy value
    draws a plain mortarboard on cardinal red. Errors from _logo_data
    propagate rather than selecting the placeholder. Font loading errors
    and ValueError for missing text glyphs also propagate.
    """
    if compact:
        return _build_uw_badge_compact(logo)
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


def _build_uw_badge_compact(logo):
    """Phone variant: narrower, university name on two lines, shorter subtitle."""
    W, H, cap_w = 336, 72, 56
    if logo:
        uri, aspect = _logo_data(logo)
        lh = 46 if aspect < 1 else 36
        lw = min(lh * aspect, 44)
        lh = lw / aspect
        art = (f'<rect x="0" y="0" width="{cap_w}" height="{H}" fill="{WHITE}" clip-path="url(#plate)"/>'
               f'<image x="{(cap_w - lw) / 2:.1f}" y="{(H - lh) / 2:.1f}" width="{lw:.1f}" height="{lh:.1f}" '
               f'preserveAspectRatio="xMidYMid meet" href="{uri}"/>')
    else:
        art = (f'<rect x="0" y="0" width="{cap_w}" height="{H}" fill="{UW_RED}" clip-path="url(#plate)"/>'
               f'<g transform="translate(-1 9) scale(.82)" fill="{WHITE}" stroke="{WHITE}" stroke-linejoin="round">'
               f'<path d="M34 19 L54 28 L34 37 L14 28 Z" stroke-width="1"/>'
               f'<path d="M24 33.5 V40 Q34 46 44 40 V33.5 L34 38.5 Z" stroke-width="1" opacity=".92"/>'
               f'<path d="M54 28 V40" fill="none" stroke-width="1.6" stroke-linecap="round"/>'
               f'<circle cx="54" cy="42" r="2" stroke="none"/></g>')
    tx = cap_w + 16
    out = [f'<clipPath id="plate"><rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="14"/></clipPath>',
           frame(W, H).replace('rx="12"', 'rx="14"'), art,
           text_path(roboto_serif(600), "UNIVERSITY OF", 10.5, tx, 24, MUTED, tracking=10.5 * 0.1),
           text_path(roboto_serif(600), "WISCONSIN\u2013MADISON", 15, tx, 43, INK, tracking=15 * 0.05),
           text_path(mono(), "M.S. DATA SCIENCE \u00b7 MADISON, WI", 9.5, tx, 59, MUTED, tracking=9.5 * 0.06)]
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
    """Lowercase alphanumeric characters, replace each other character with
    a hyphen, and strip leading and trailing hyphens.
    """
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in text).strip("-")


def _lum(hex_color):
    """Return relative luminance for a #RRGGBB color on a scale from 0 to 1.

    Invalid hexadecimal channel slices raise ValueError.
    """
    def ch(v):
        """Convert an 8-bit sRGB channel to its linear-light value."""
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
    """Return a tool badge SVG with a category label and tool name.

    brand is a #RRGGBB color for the category background and badge border;
    category text uses whichever of dark or white has greater contrast.
    Invalid hexadecimal channels raise ValueError. Font loading errors
    and ValueError for missing text glyphs propagate.
    """
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


# ------------------------------------------------------------------ activity stats
def load_activity():
    f = ASSETS / "data" / "activity.json"
    return json.loads(f.read_text()) if f.exists() else None


def activity_stats(data):
    """Numbers shown on the stats card, from assets/data/activity.json (written by make_snake.py)."""
    days = data["days"]
    levels = [d["l"] for d in days]
    counts = [d.get("c") for d in days]
    has_counts = all(c is not None for c in counts)
    longest = run = 0
    for lv in levels:
        run = run + 1 if lv > 0 else 0
        longest = max(longest, run)
    i = len(levels) - 1
    if levels[i] == 0:      # today may still be empty; the streak then runs up to yesterday
        i -= 1
    current = 0
    while i >= 0 and levels[i] > 0:
        current += 1
        i -= 1
    first = date.fromisoformat(days[0]["d"])
    sunday = first - timedelta(days=(first.weekday() + 1) % 7)
    weeks = {}
    for d, lv, c in zip(days, levels, counts):
        w = (date.fromisoformat(d["d"]) - sunday).days // 7
        weeks[w] = weeks.get(w, 0) + (c if has_counts else lv)
    series = [weeks.get(w, 0) for w in range(max(weeks) + 1)]
    return dict(active=sum(1 for lv in levels if lv), total=sum(counts) if has_counts else None,
                current=current, longest=longest, series=series,
                active_weeks=sum(1 for v in series if v), n_days=len(days), updated=data["generated"])


def _bars(series, x0, baseline, total_w, max_h, gap):
    peak = max(series) or 1
    pitch = total_w / len(series)
    out = []
    for k, v in enumerate(series):
        h = 3 if v == 0 else 4 + (max_h - 4) * v / peak
        colour = PINK if k == len(series) - 1 else (EDGE if v == 0 else ACCENT)
        out.append(f'<rect x="{x0 + k * pitch:.1f}" y="{baseline - h:.1f}" width="{pitch - gap:.1f}" height="{h:.1f}" rx="1.5" fill="{colour}"/>')
    return out


def _stat_tiles(st):
    first = (("CONTRIBUTIONS", f"{st['total']:,}", "") if st["total"] is not None
             else ("ACTIVE DAYS", str(st["active"]), f"of {st['n_days']}"))
    return [first,
            ("CURRENT STREAK", str(st["current"]), "days"),
            ("LONGEST STREAK", str(st["longest"]), "days"),
            ("ACTIVE WEEKS", str(st["active_weeks"]), f"of {len(st['series'])}")]


def build_stats(st, compact=False):
    """Activity card. compact=True is the phone variant (2x2 tiles)."""
    tiles = _stat_tiles(st)
    series = st["series"]
    alt = (f"Activity over the last 12 months: {tiles[0][1]} {tiles[0][0].lower()}, current streak {st['current']} days, "
           f"longest streak {st['longest']} days, active in {st['active_weeks']} of {len(series)} weeks. Updated {st['updated']}.")
    upd = f"UPDATED {st['updated']}"
    out = []
    if compact:
        W, H, PAD = 336, 252, 16
        out.append(kicker("Activity \u00b7 12 months", PAD, 28, size=9))
        uw = width(mono(), upd, 9, 0.9)
        out.append(text_path(mono(), upd, 9, W - PAD - uw, 28, MUTED, tracking=0.9))
        tw = (W - 2 * PAD) / 2
        for i, (label, value, unit) in enumerate(tiles):
            col, row = i % 2, i // 2
            x = PAD + col * tw + (14 if col else 0)
            y = 82 + row * 66
            out.append(text_path(roboto_serif(600), value, 32, x, y, PINK if i == 1 else ACCENT))
            vw = width(roboto_serif(600), value, 32)
            if unit:
                out.append(text_path(roboto(400), unit, 12, x + vw + 6, y, MUTED))
            out.append(text_path(mono(), label, 9, x, y + 18, MUTED, tracking=1.0))
        out.append(f'<line x1="{PAD + tw:.1f}" y1="52" x2="{PAD + tw:.1f}" y2="170" stroke="{EDGE}"/>')
        out.append(f'<line x1="{PAD}" y1="108" x2="{W - PAD}" y2="108" stroke="{EDGE}"/>')
        out += _bars(series, PAD, 226, W - 2 * PAD, 34, 1.6)
    else:
        W, H, PAD = 792, 204, 36
        TILE = (W - 2 * PAD) / 4
        out.append(kicker("Activity \u00b7 last 12 months", PAD, 38))
        uw = width(mono(), upd, 10, 1.0)
        out.append(text_path(mono(), upd, 10, W - PAD - uw, 38, MUTED, tracking=1.0))
        for i, (label, value, unit) in enumerate(tiles):
            x = PAD + i * TILE + (0 if i == 0 else 20)
            out.append(text_path(roboto_serif(600), value, 40, x, 104, PINK if i == 1 else ACCENT))
            vw = width(roboto_serif(600), value, 40)
            if unit:
                out.append(text_path(roboto(400), unit, 14, x + vw + 8, 104, MUTED))
            out.append(text_path(mono(), label, 10, x, 126, MUTED, tracking=1.2))
            if i:
                out.append(f'<line x1="{PAD + i * TILE:.1f}" y1="64" x2="{PAD + i * TILE:.1f}" y2="130" stroke="{EDGE}"/>')
        out += _bars(series, PAD, 176, W - 2 * PAD, 34, 4)
    return wrap_svg(W, H, alt, "Activity stats", "", "\n".join(out))


# ------------------------------------------------------------------ photo carousel
# GitHub strips scripts, so the carousel is a CSS-animated SVG: the photos are embedded as
# JPEGs, cross-fade one after another, and the thumbnail strip highlights the current one.
PHOTOS = ASSETS / "photos"
HOLD, FADE = 4.5, 0.7   # seconds each photo is shown, and the cross-fade into the next
MAX_PHOTOS = 6
PHOTO_EXT = {".jpg", ".jpeg", ".png", ".webp"}


QUALITY = 95      # JPEG quality of the embedded photos
MAX_SCALE = 3     # embed at most this many pixels per displayed pixel; smaller sources are never upscaled


def load_photos():
    """Photos in assets/photos, sorted by file name, as [(path, caption, focus, fit)].

    assets/photos/photos.json may map a file name to {"caption": "...", "focus": [x, y], "fit": "..."}.
    fit "cover" (default) fills the stage and crops; focus is the point of the photo (0..1) that
    stays in frame, default (0.5, 0.35) to keep heads in frame on portraits. fit "contain" shows the
    whole photo, uncropped, on a soft blurred backdrop of itself, which suits portrait photos.
    """
    if not PHOTOS.is_dir():
        return []
    meta_file = PHOTOS / "photos.json"
    meta = json.loads(meta_file.read_text()) if meta_file.exists() else {}
    files = sorted(q for q in PHOTOS.iterdir() if q.suffix.lower() in PHOTO_EXT)
    assert len(files) <= MAX_PHOTOS, f"at most {MAX_PHOTOS} photos fit the thumbnail strip, found {len(files)}"
    out = []
    for q in files:
        m = meta.get(q.name, {})
        fit = m.get("fit", "cover")
        assert fit in ("cover", "contain"), f"{q.name}: fit must be cover or contain, not {fit!r}"
        out.append((q, m.get("caption", ""), tuple(m.get("focus", (0.5, 0.35))), fit))
    return out


def _jpeg_b64(im):
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=QUALITY, optimize=True, progressive=True, subsampling=0)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def _photo_group(path, sw, sh, focus, fit):
    """SVG for one photo in a stage of sw x sh. Re-encoding drops EXIF, GPS included.

    The source is resampled only to shrink it to MAX_SCALE times the displayed size, never enlarged.
    """
    from PIL import Image, ImageCms, ImageOps
    im = Image.open(path)
    icc = im.info.get("icc_profile")
    im = ImageOps.exif_transpose(im).convert("RGB")
    if icc:   # phones shoot in Display P3; without this conversion the colours look flat in sRGB browsers
        im = ImageCms.profileToProfile(im, ImageCms.ImageCmsProfile(io.BytesIO(icc)), ImageCms.createProfile("sRGB"),
                                       outputMode="RGB")

    def shrink(img, w):
        return img if img.width <= w else img.resize((w, round(img.height * w / img.width)), Image.LANCZOS)

    def cover(img, ratio):
        """Crop img to the aspect ratio around focus, no resampling."""
        w, h = (img.width, round(img.width / ratio)) if img.width / img.height < ratio else (round(img.height * ratio), img.height)
        left, top = round((img.width - w) * focus[0]), round((img.height - h) * focus[1])
        return img.crop((left, top, left + w, top + h))

    if fit == "cover":
        photo = shrink(cover(im, sw / sh), sw * MAX_SCALE)
        return f'<image width="{sw}" height="{sh}" preserveAspectRatio="none" href="{_jpeg_b64(photo)}"/>'
    k = min(sw / im.width, sh / im.height)
    dw, dh = im.width * k, im.height * k
    photo = shrink(im, round(dw * MAX_SCALE))
    backdrop = cover(im, sw / sh).resize((64, round(64 * sh / sw)), Image.LANCZOS)  # scaled up smoothly = blur
    return (f'<image width="{sw}" height="{sh}" preserveAspectRatio="none" href="{_jpeg_b64(backdrop)}"/>'
            f'<rect width="{sw}" height="{sh}" fill="{BG}" opacity=".45"/>'
            f'<image x="{(sw - dw) / 2:.2f}" y="{(sh - dh) / 2:.2f}" width="{dw:.2f}" height="{dh:.2f}" href="{_jpeg_b64(photo)}"/>')


def build_gallery(photos, compact=False):
    """Carousel card: stage on top, caption and counter below, thumbnail strip underneath."""
    n = len(photos)
    if compact:
        W, PAD, SH, TG, cap_size, cap_y, thumb_y = 392, 16, 270, 6, 14, 26, 44
    else:
        W, PAD, SH, TG, cap_size, cap_y, thumb_y = 792, 16, 475, 10, 16, 30, 50
    SW = W - 2 * PAD
    tw = (SW - (n - 1) * TG) / n
    k = tw / SW
    th = SH * k
    H = round(PAD + SH + thumb_y + th + PAD)
    T = n * HOLD

    defs = [f'<clipPath id="stage"><rect x="{PAD}" y="{PAD}" width="{SW}" height="{SH}" rx="8"/></clipPath>']
    for i, (path, _, focus, fit) in enumerate(photos):
        defs.append(f'<g id="p{i}">{_photo_group(path, SW, SH, focus, fit)}</g>')
        defs.append(f'<clipPath id="t{i}"><rect x="{PAD + i * (tw + TG):.2f}" y="{PAD + SH + thumb_y}" '
                    f'width="{tw:.2f}" height="{th:.2f}" rx="5"/></clipPath>')

    body, thumbs = [], []
    for i, (path, caption, _, _) in enumerate(photos):
        count_n, count_all = f"{i + 1:02d}", f" / {n:02d}"
        cw = width(mono(), count_n + count_all, 11, 1.1)
        slide = [f'<g clip-path="url(#stage)"><use href="#p{i}" x="{PAD}" y="{PAD}"/></g>']
        if caption:
            assert width(roboto(400), caption, cap_size) < SW - cw - 24, f"caption too long: {caption}"
            slide.append(text_path(roboto(400), caption, cap_size, PAD + 2, PAD + SH + cap_y, INK))
        nw = width(mono(), count_n, 11, 1.1)
        slide.append(text_path(mono(), count_n, 11, W - PAD - cw, PAD + SH + cap_y, PINK, tracking=1.1))
        slide.append(text_path(mono(), count_all, 11, W - PAD - cw + nw, PAD + SH + cap_y, MUTED, tracking=1.1))
        body.append(f'<g class="s s{i}">{"".join(slide)}</g>')
        tx, ty = PAD + i * (tw + TG), PAD + SH + thumb_y
        thumbs.append(f'<g clip-path="url(#t{i})"><use href="#p{i}" transform="translate({tx:.2f} {ty}) scale({k:.5f})"/>'
                      f'<rect class="d d{i}" x="{tx:.2f}" y="{ty}" width="{tw:.2f}" height="{th:.2f}" fill="{BG}"/></g>'
                      f'<rect class="b b{i}" x="{tx + 1:.2f}" y="{ty + 1}" width="{tw - 2:.2f}" height="{th - 2:.2f}" '
                      f'rx="4" fill="none" stroke="{PINK}" stroke-width="2"/>')

    # Photo i is fully shown from i*HOLD and starts fading in FADE earlier, so it overlaps its
    # predecessor's fade-out. Photo 0 starts mid-cycle, so the first frame is already its own.
    pct = lambda t: f"{t / T * 100:.3f}%"
    delays = "".join(f".s{i},.d{i},.b{i}{{animation-delay:{i * HOLD - FADE:.2f}s}}" for i in range(n))
    style = (f"<style>.s{{opacity:0}}.s0,.b0{{opacity:1}}.b{{opacity:0}}.d{{opacity:.55}}.d0{{opacity:0}}"
             + (f"@media (prefers-reduced-motion:no-preference){{.s,.b{{animation:show {T:g}s linear infinite}}"
                f".d{{animation:dim {T:g}s linear infinite}}{delays}}}"
                f"@keyframes show{{0%{{opacity:0}}{pct(FADE)}{{opacity:1}}{pct(HOLD)}{{opacity:1}}"
                f"{pct(HOLD + FADE)}{{opacity:0}}100%{{opacity:0}}}}"
                f"@keyframes dim{{0%{{opacity:.55}}{pct(FADE)}{{opacity:0}}{pct(HOLD)}{{opacity:0}}"
                f"{pct(HOLD + FADE)}{{opacity:.55}}100%{{opacity:.55}}}}" if n > 1 else "")
             + "</style>\n")
    stage_edge = f'<rect x="{PAD - 0.5}" y="{PAD - 0.5}" width="{SW + 1}" height="{SH + 1}" rx="8.5" fill="none" stroke="{EDGE}"/>'
    names = "; ".join(c for _, c, _, _ in photos if c)
    alt = f"Photo carousel of Jack J. Burleson, {n} photos" + (f": {names}." if names else ".")
    return wrap_svg(W, H, alt, "Photos", f"<defs>{''.join(defs)}</defs>\n{style}",
                    "\n".join([stage_edge] + body + thumbs))


# ------------------------------------------------------------------ link buttons
# (label, kind, file): "link" ends in a pink arrow, "demo" starts with a pink play triangle.
BUTTONS = [
    ("Portfolio", "link", "portfolio"), ("R\u00e9sum\u00e9 (PDF)", "link", "resume"),
    ("LinkedIn", "link", "linkedin"), ("Email", "link", "email"),
    ("Hugging Face", "link", "hugging-face"), ("Instagram", "link", "instagram"),
    ("Wave Laboratory", "demo", "demo-wave-laboratory"), ("Langton\u2019s Ant", "demo", "demo-langtons-ant"),
    ("The Mandalay Bay", "demo", "demo-mandalay-bay"),
    ("Mandalay Pixel RPG", "demo", "demo-mandalay-rpg"),
]


def build_button(label, kind):
    H, PAD = 38, 18
    tw = width(roboto(500), label, 14)
    lead = 20 if kind == "demo" else 0
    trail = 20 if kind == "link" else 0
    W = PAD + lead + tw + trail + PAD
    out = [f'<rect x="0.5" y="0.5" width="{W - 1:.1f}" height="{H - 1}" rx="{H / 2}" fill="{BG}" stroke="{ACCENT}" stroke-opacity=".6"/>']
    if kind == "demo":
        out.append(f'<path d="M{PAD} {H / 2 - 5} L{PAD + 9} {H / 2} L{PAD} {H / 2 + 5} Z" fill="{PINK}"/>')
    out.append(text_path(roboto(500), label, 14, PAD + lead, H / 2 + 5, INK))
    if kind == "link":
        out.append(arrow(PAD + lead + tw + 9, H / 2 - 5, PINK))
    alt = label + (" (live demo)" if kind == "demo" else "")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W + 2 * M:.0f}" height="{H + 2 * M}" '
            f'viewBox="0 0 {W + 2 * M:.1f} {H + 2 * M}" role="img" aria-label="{alt}">\n<title>{alt}</title>\n'
            f'<g transform="translate({M} {M})">\n' + "\n".join(out) + '\n</g>\n</svg>\n')


# ------------------------------------------------------------------ signature
def build_signature(dark):
    """Hand-signed look: script outlines, a slight slant, a tapered pink flourish, written once on load.

    The canvas is sized from the measured outline of the ink (after the tilt), so no stroke can be clipped.
    """
    import math
    ink = INK if dark else "#1B2428"
    fc = face("mr-de-haviland-latin-400-normal.woff2")
    text, size, tilt, pad = "Jack J. Burleson", 84, -3.5, 18
    d, _, _ = shape(fc, text, size)
    x0, y0, x1, y1 = ink_bounds(fc, text, size)         # name drawn with its origin at (0, 0)
    iw = x1 - x0
    sw = iw * 0.66                                      # flourish length
    fx, fy = x0 + iw * 0.24, y1 * 0.0 + 30              # flourish start, below the baseline
    flourish = (f"M{fx:.1f} {fy + 6:.1f} C{fx + sw * .26:.1f} {fy - 8:.1f} {fx + sw * .65:.1f} {fy - 16:.1f} {fx + sw:.1f} {fy - 6:.1f} "
                f"C{fx + sw * .65:.1f} {fy - 10:.1f} {fx + sw * .3:.1f} {fy - 2:.1f} {fx:.1f} {fy + 6:.1f} Z")
    # bounds of everything after the tilt (rotation about the middle of the name, on the baseline)
    cx, a = (x0 + x1) / 2, math.radians(tilt)
    pts = [(x0, y0), (x1, y0), (x0, y1), (x1, y1), (fx, fy - 16), (fx, fy + 8), (fx + sw, fy - 16), (fx + sw, fy + 8)]
    rot = [(cx + (px - cx) * math.cos(a) - py * math.sin(a), (px - cx) * math.sin(a) + py * math.cos(a)) for px, py in pts]
    minx, maxx = min(r[0] for r in rot) - pad, max(r[0] for r in rot) + pad
    miny, maxy = min(r[1] for r in rot) - pad, max(r[1] for r in rot) + pad
    W, H = math.ceil(maxx - minx), math.ceil(maxy - miny)
    place = f"translate({-minx:.1f} {-miny:.1f}) rotate({tilt} {cx:.1f} 0)"
    alt = "Signature of Jack J. Burleson"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{alt}">
<title>{alt}</title>
<defs>
  <clipPath id="name"><rect class="w1" x="0" y="0" width="{W}" height="{H}"/></clipPath>
  <clipPath id="swash"><rect class="w2" x="0" y="0" width="{W}" height="{H}"/></clipPath>
</defs>
<style>
  .w1, .w2 {{ transform-box: view-box; transform-origin: 0 0; }}
  .w1 {{ animation: write 2.6s cubic-bezier(.55,.05,.3,1) .4s both; }}
  .w2 {{ animation: write 1.1s cubic-bezier(.4,0,.2,1) 2.7s both; }}
  @keyframes write {{ from {{ transform: scaleX(0); }} to {{ transform: scaleX(1); }} }}
  @media (prefers-reduced-motion: reduce) {{ .w1, .w2 {{ animation: none; }} }}
</style>
<g clip-path="url(#name)"><g transform="{place}"><path fill="{ink}" stroke="{ink}" stroke-width=".6" stroke-linejoin="round" d="{d}"/></g></g>
<g clip-path="url(#swash)"><g transform="{place}"><path fill="{PINK}" d="{flourish}"/></g></g>
</svg>
'''


def main():
    """Write the header, cards, and badges under assets, overwriting matches.

    Use the first command-line argument as the university logo path when
    supplied; otherwise prefer assets/logo/uw-madison.svg, then .png, and
    use a mortarboard if neither exists. Print a generation summary.

    File, logo, and font errors propagate, as do card layout assertion
    failures; files already written are not rolled back.
    """
    ASSETS.mkdir(exist_ok=True)
    for sub in ("cards", "badges", "buttons"):
        (ASSETS / sub).mkdir(exist_ok=True)
    (ASSETS / "header.svg").write_text(build_header())
    (ASSETS / "header-compact.svg").write_text(build_header(compact=True))
    (ASSETS / "cards" / FEATURED["file"]).write_text(build_featured(FEATURED))
    (ASSETS / "cards" / FEATURED["compact"]).write_text(build_featured(FEATURED, compact=True))
    for p in PROJECTS:
        (ASSETS / "cards" / p["file"]).write_text(build_card(p))
        (ASSETS / "cards" / p["file"].replace(".svg", "-compact.svg")).write_text(build_card_compact(p))
    logo = next((q for q in (ASSETS / "logo" / "uw-madison.svg", ASSETS / "logo" / "uw-madison.png") if q.exists()), None)
    if len(sys.argv) > 1:   # optional: python3 scripts/build_assets.py path/to/logo.svg|png
        logo = sys.argv[1]
    svg, badge_w = build_uw_badge(logo)
    (ASSETS / "badges" / "uw-madison.svg").write_text(svg)
    (ASSETS / "badges" / "uw-madison-compact.svg").write_text(build_uw_badge(logo, compact=True)[0])
    print("UW badge:", "official logo" if logo else "mortarboard placeholder", f"(width {badge_w})")
    for cat, tool, brand in TOOL_BADGES:
        (ASSETS / "badges" / f"{slug(tool)}.svg").write_text(build_tool_badge(cat, tool, brand))
    for label, kind, file in BUTTONS:
        (ASSETS / "buttons" / f"{file}.svg").write_text(build_button(label, kind))
    (ASSETS / "signature-dark.svg").write_text(build_signature(dark=True))
    (ASSETS / "signature-light.svg").write_text(build_signature(dark=False))
    activity = load_activity()
    if activity:
        stats = activity_stats(activity)
        (ASSETS / "stats.svg").write_text(build_stats(stats))
        (ASSETS / "stats-compact.svg").write_text(build_stats(stats, compact=True))
    photos = load_photos()
    if photos:
        (ASSETS / "gallery.svg").write_text(build_gallery(photos))
        (ASSETS / "gallery-compact.svg").write_text(build_gallery(photos, compact=True))
        print(f"photo carousel: {len(photos)} photos")
    else:
        print("no photos in assets/photos, carousel skipped")
    print("wrote the header, cards, badges, buttons, signature and stats")


if __name__ == "__main__":
    main()
