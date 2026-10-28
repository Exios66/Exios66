#!/usr/bin/env python3
"""Build the README artwork: assets/header.svg and assets/cards/*.svg.

All text is converted to vector outlines, so the images look identical on every
device and need no font loading. Edit the PROJECTS list (or the header copy)
below, run the script, and commit the SVGs.

    pip install fonttools uharfbuzz
    python3 scripts/build_assets.py

Fonts (SIL OFL, in scripts/fonts/): Quicksand Medium/Bold, JetBrains Mono.
"""
import io
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "scripts" / "fonts"
ASSETS = ROOT / "assets"

# One flat palette, one accent. Matches the badges, header and snake.
ACCENT, BG, EDGE = "#29A9F0", "#0D1117", "#30363D"
TITLE, BODY, MUTED = "#E6EDF3", "#A9B4C2", "#8B98A8"

# ----------------------------------------------------------------- typography
_cache = {}


class Face:
    def __init__(self, name):
        f = TTFont(FONTS / name)
        f.flavor = None
        buf = io.BytesIO()
        f.save(buf)
        raw = buf.getvalue()
        self.font = TTFont(io.BytesIO(raw))
        self.upm = self.font["head"].unitsPerEm
        self.hb = hb.Font(hb.Face(raw))
        self.glyphs = self.font.getGlyphSet()
        self.order = self.font.getGlyphOrder()


def face(name):
    if name not in _cache:
        _cache[name] = Face(name)
    return _cache[name]


QS_B, QS_M, JB = "Quicksand-Bold.woff", "Quicksand-Medium.woff", "JetBrainsMono-Regular.woff"


def shape(name, text, size, tracking=0.0, outline=True):
    """Return (svg path d, cumulative x after each character, total width)."""
    fc = face(name)
    s = size / fc.upm
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(fc.hb, buf, {"liga": False, "calt": False, "clig": False})
    d, x, ends = [], 0.0, {}
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
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
    return "".join(d), xs, x


def width(name, text, size, tracking=0.0):
    return shape(name, text, size, tracking, outline=False)[2]


def wrap(name, text, size, max_w):
    n = len(_wrap(name, text, size, max_w))
    lo, hi = max_w * 0.5, max_w
    for _ in range(14):  # narrowest width that still fits in n lines -> no orphan last line
        mid = (lo + hi) / 2
        if len(_wrap(name, text, size, mid)) <= n:
            hi = mid
        else:
            lo = mid
    return _wrap(name, text, size, hi + 1)


def _wrap(name, text, size, max_w):
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if cur and width(name, trial, size) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def text_path(name, text, size, x, y, fill, tracking=0.0, extra=""):
    d, _, _ = shape(name, text, size, tracking)
    return f'<path transform="translate({x:.2f} {y:.2f})" fill="{fill}" {extra}d="{d}"/>'


def frame(w, h):
    return f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="12" fill="{BG}" stroke="{EDGE}"/>'


def chips(items, x, y, accent_first=False, max_x=None):
    """Outlined tag pills; wraps to new rows past max_x. Returns (svg, bottom edge)."""
    out, cx, cy = [], x, y
    for i, t in enumerate(items):
        cw = width(JB, t, 11) + 20
        if max_x is not None and cx > x and cx + cw > max_x:
            cx, cy = x, cy + 30
        stroke = ACCENT if (accent_first and i == 0) else EDGE
        out.append(f'<rect x="{cx:.1f}" y="{cy}" width="{cw:.1f}" height="22" rx="11" fill="none" stroke="{stroke}"/>')
        out.append(text_path(JB, t, 11, cx + 10, cy + 15, BODY))
        cx += cw + 8
    return "\n".join(out), cy + 22


# --------------------------------------------------------------------- header
def build_header():
    H, PAD, LOOP = 160, 52, 12.0
    NAME, SUBT = "Jack J. Burleson", "It’s a pleasure to meet you here..."
    d1, x1, w1 = shape(QS_B, NAME, 50)
    d2, x2, w2 = shape(JB, SUBT, 18)
    Y1, Y2 = 76, 120
    W = round(2 * PAD + max(w1, w2))

    def pct(t):
        return f"{t / LOOP * 100:.3f}%"

    ev = []

    def typed(line, n, t0, t1):
        for i in range(1, n + 1):
            ev.append((t0 + (t1 - t0) * (i - 1) / (n - 1), line, i))

    def erased(line, n, t0, t1):
        for i in range(1, n + 1):
            ev.append((t0 + (t1 - t0) * (i - 1) / (n - 1), line, n - i))

    n1, n2 = len(NAME), len(SUBT)
    typed(1, n1, 0.7, 2.3)
    typed(2, n2, 2.8, 5.2)
    erased(2, n2, 9.0, 10.1)
    erased(1, n1, 10.25, 10.95)
    xs = {1: x1, 2: x2}
    Y = {1: Y1, 2: Y2}
    state = {1: 0, 2: 0}
    frames = [(0.0, dict(state), 1)]
    for t, line, n in ev:
        state[line] = n
        frames.append((t, dict(state), line))
    frames.append((LOOP, {1: 0, 2: 0}, 1))

    def kf(name, fn):
        out = [f"    @keyframes {name} {{"]
        for t, st, ln in frames:
            out.append(f"      {pct(t)} {{ {fn(st, ln)} animation-timing-function: steps(1, end); }}")
        out.append("    }")
        return "\n".join(out)

    def clip(line):
        return lambda st, ln: f"transform: scaleX({xs[line][st[line]]:.2f});"

    CUR = {1: (38, 43, 3), 2: (16, 22, 2.5)}

    def cur(st, ln):
        top, h, w = CUR[ln]
        x = PAD + xs[ln][st[ln]] + (4 if ln == 1 else 2)
        return f"transform: translate({x:.2f}px, {Y[ln] - top:.2f}px) scale({w}, {h});"

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="t d">
  <title id="t">Jack J. Burleson</title>
  <desc id="d">It’s a pleasure to meet you here...</desc>
  <defs>
    <clipPath id="c1"><rect class="r1" x="{PAD}" y="{Y1 - 56}" width="1" height="72"/></clipPath>
    <clipPath id="c2"><rect class="r2" x="{PAD}" y="{Y2 - 24}" width="1" height="38"/></clipPath>
  </defs>
  <style>
    .r1, .r2 {{ transform-box: view-box; transform-origin: {PAD}px 0; }}
    .r1 {{ animation: r1 {LOOP}s infinite; }}
    .r2 {{ animation: r2 {LOOP}s infinite; }}
    .cur {{ animation: cur {LOOP}s infinite; }}
    .bar {{ animation: blink 1s steps(1, end) infinite; }}
{kf("r1", clip(1))}
{kf("r2", clip(2))}
{kf("cur", cur)}
    @keyframes blink {{ 0%, 55% {{ opacity: 1; }} 56%, 100% {{ opacity: 0; }} }}
    @media (prefers-reduced-motion: reduce) {{
      .r1, .r2, .cur, .bar {{ animation: none; }}
      .r1 {{ transform: scaleX({x1[-1]:.2f}); }} .r2 {{ transform: scaleX({x2[-1]:.2f}); }}
      .cur {{ display: none; }}
    }}
  </style>

  {frame(W, H)}

  <g clip-path="url(#c1)"><path transform="translate({PAD} {Y1})" fill="{ACCENT}" d="{d1}"/></g>
  <g clip-path="url(#c2)"><path transform="translate({PAD} {Y2})" fill="{BODY}" d="{d2}"/></g>

  <g class="cur"><rect class="bar" x="0" y="0" width="1" height="1" fill="{ACCENT}"/></g>
</svg>
'''


# ---------------------------------------------------------------------- cards
# Copy below is drawn from each repository's own README.
FEATURED = dict(
    file="digital-mailroom.svg",
    compact="digital-mailroom-compact.svg",  # swapped in on phones
    label="FEATURED PROJECT",
    title="The Digital Mailroom",
    desc=("A multi-agent pipeline for legal documents. Every file is sorted, extracted, "
          "second-opinioned by a judge, and archived with a hash-chained receipt."),
    tags=["13-node LangGraph pipeline", "5 document classes", "3,302-row dataset"],
    alt=("The Digital Mailroom: a multi-agent legal-document pipeline with intake, classify, "
         "extract, judge, compile and archive stages."),
    stages=["INTAKE", "CLASSIFY", "EXTRACT", "JUDGE", "COMPILE", "ARCHIVE"],
)

PROJECTS = [
    dict(file="agent-mailroom.svg", label="AGENT SYSTEMS", title="Agent Mailroom",
         desc=("The document pipeline on a walking pixel-art office floor. Agents sort, "
               "extract and judge while you watch."),
         tags=["Python", "OpenRouter", "SQLite"],
         alt="Agent Mailroom: the document pipeline on a walking pixel-art office floor."),
    dict(file="rvl-cdip-classifier.svg", label="DOCUMENT AI", title="RVL-CDIP Classifier",
         desc=("Vision-model classification across 16 document classes, with versioned "
               "prompts, Braintrust evals and per-model cost projections."),
         tags=["Python", "OpenRouter", "Tesseract"],
         alt="RVL-CDIP Classifier: vision-model document classification with evals and cost projections."),
    dict(file="psych-755.svg", label="RESEARCH", title="PSYCH 755",
         desc=("Can an LLM predict communication apprehension from a persona, and does it "
               "stereotype when it misses? Tested against seven ML baselines."),
         tags=["Python", "SHAP", "Quarto"],
         alt="PSYCH 755: LLM persona prediction of communication apprehension versus ML baselines."),
    dict(file="mandalay-bay.svg", label="INTERACTIVE", title="The Mandalay Bay",
         desc=("A satirical resort simulator on one chip economy: Python CLI, browser "
               "terminal and a Phaser pixel RPG. 200+ tests."),
         tags=["Python", "JavaScript", "Phaser"],
         alt="The Mandalay Bay: a satirical resort simulator as a CLI, browser terminal and pixel RPG."),
]


M = 4  # transparent margin around cards, so inline cards sit 8px apart


def wrap_svg(w, h, alt, title, style, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w + 2 * M}" height="{h + 2 * M}" '
            f'viewBox="0 0 {w + 2 * M} {h + 2 * M}" role="img" aria-label="{alt}">\n<title>{title}</title>\n'
            f'{style}<g transform="translate({M} {M})">\n{frame(w, h)}\n{body}\n</g>\n</svg>\n')


def build_featured(c, compact=False):
    W, PAD = (392, 24) if compact else (792, 36)
    st = c["stages"]
    fs = 9 if compact else 10
    trk = 0.5 if compact else 0.8
    tws = [width(JB, t, fs, trk) for t in st]
    x0, x1 = PAD + tws[0] / 2, W - PAD - tws[-1] / 2   # first/last labels sit flush with the card margins
    n = len(st)
    step = (x1 - x0) / (n - 1)
    out = [text_path(JB, c["label"], 11, PAD, 36 if compact else 38, ACCENT, tracking=1.6)]
    out.append(text_path(JB, "\u2197", 14, W - PAD - 10, 36 if compact else 38, MUTED))
    ts, ds, dl = (28, 14.5, 21) if compact else (36, 16, 24)
    ty = 72 if compact else 82
    out.append(text_path(QS_B, c["title"], ts, PAD, ty, TITLE))
    lines = wrap(QS_M, c["desc"], ds, W - 2 * PAD - (0 if compact else 40))
    dy = ty + (28 if compact else 30)
    for i, ln in enumerate(lines):
        out.append(text_path(QS_M, ln, ds, PAD, dy + i * dl, BODY))
    chip_y = dy + len(lines) * dl - 6
    svg_chips, bottom = chips(c["tags"], PAD, chip_y, accent_first=True, max_x=W - PAD)
    out.append(svg_chips)
    # conveyor: six stage nodes on a line, an envelope rides along it
    ly = bottom + 40
    out.append(f'<line x1="{x0:.1f}" y1="{ly}" x2="{x1:.1f}" y2="{ly}" stroke="{EDGE}" stroke-width="2" stroke-linecap="round"/>')
    for i, name in enumerate(st):
        cx = x0 + i * step
        out.append(f'<circle cx="{cx:.1f}" cy="{ly}" r="5" fill="{BG}" stroke="{MUTED}" stroke-width="1.5"/>')
        out.append(text_path(JB, name, fs, cx - tws[i] / 2, ly + 24, MUTED, tracking=trk))
    out.append(f'<g class="env"><g transform="translate({x0 - 7:.1f} {ly - 22})">'
               f'<rect width="14" height="10" rx="1.5" fill="{ACCENT}"/>'
               f'<path d="M1.2 1.6 L7 6 L12.8 1.6" fill="none" stroke="{BG}" stroke-width="1.2" stroke-linejoin="round"/>'
               f'</g></g>')
    H = ly + 24 + 22
    dist = x1 - x0
    style = ("<style>\n  .env { animation: ride 9s linear infinite; }\n"
             f"  @keyframes ride {{ 0% {{ transform: translateX(0); }} 88% {{ transform: translateX({dist:.1f}px); }} "
             f"100% {{ transform: translateX({dist:.1f}px); }} }}\n"
             f"  @media (prefers-reduced-motion: reduce) {{ .env {{ animation: none; transform: translateX({dist / 2:.1f}px); }} }}\n"
             "</style>\n")
    return wrap_svg(W, H, c["alt"], c["title"], style, "\n".join(out))


def build_card(c):
    W, H, PAD = 392, 206, 24
    out = [text_path(JB, c["label"], 11, PAD, 36, ACCENT, tracking=1.6),
           text_path(JB, "\u2197", 14, W - PAD - 10, 36, MUTED),
           text_path(QS_B, c["title"], 24, PAD, 70, TITLE)]
    lines = wrap(QS_M, c["desc"], 14.5, W - 2 * PAD)
    assert len(lines) <= 3, f'{c["title"]}: description wraps to {len(lines)} lines'
    for i, ln in enumerate(lines):
        out.append(text_path(QS_M, ln, 14.5, PAD, 98 + i * 21, BODY))
    svg_chips, _ = chips(c["tags"], PAD, H - 44, max_x=W - PAD)
    assert svg_chips.count("<rect") == len(c["tags"]) and 'y="%d"' % (H - 44) in svg_chips, f'{c["title"]}: tags wrapped'
    out.append(svg_chips)
    return wrap_svg(W, H, c["alt"], c["title"], "", "\n".join(out))


def main():
    ASSETS.mkdir(exist_ok=True)
    (ASSETS / "cards").mkdir(exist_ok=True)
    (ASSETS / "header.svg").write_text(build_header())
    (ASSETS / "cards" / FEATURED["file"]).write_text(build_featured(FEATURED))
    (ASSETS / "cards" / FEATURED["compact"]).write_text(build_featured(FEATURED, compact=True))
    for p in PROJECTS:
        (ASSETS / "cards" / p["file"]).write_text(build_card(p))
    print("wrote assets/header.svg and", 2 + len(PROJECTS), "cards")


if __name__ == "__main__":
    main()
