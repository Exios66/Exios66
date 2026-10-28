#!/usr/bin/env python3
"""Generate the contribution-snake SVGs without GitHub Actions.

Reads your public contribution calendar (no token needed) and writes
assets/snake.svg (light) and assets/snake-dark.svg (dark). Standard library only.

    python3 scripts/make_snake.py                 # fetch from github.com
    python3 scripts/make_snake.py --html page.html  # use a saved copy of
                                                    # https://github.com/users/<user>/contributions
    python3 scripts/make_snake.py --empty         # blank grid (placeholder)

Then commit the two SVGs. Run it whenever you like (or from cron/launchd).
"""
import argparse, datetime as dt, html, re, sys, urllib.request
from pathlib import Path

ACCENT = "#4FC1CD"
PALETTES = {
    "light": ["#EBEDF0", "#9BE9A8", "#40C463", "#30A14E", "#216E39"],
    "dark": ["#161B22", "#0E4429", "#006D32", "#26A641", "#39D353"],
}
CELL, GAP, PAD = 11, 3, 14
PITCH = CELL + GAP
BODY = 5          # snake length in cells
SEC_PER_CELL = 0.07
DWELL = 12        # off-grid cells of pause at the end of each loop


def fetch(user):
    req = urllib.request.Request(
        f"https://github.com/users/{user}/contributions",
        headers={"User-Agent": "Mozilla/5.0 (snake generator)"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def parse(page):
    days = {}
    for tag in re.findall(r"<(?:td|rect)\b[^>]*>", page):
        d = re.search(r'data-date="(\d{4}-\d{2}-\d{2})"', tag)
        l = re.search(r'data-level="(\d)"', tag)
        if d and l:
            days[dt.date.fromisoformat(d.group(1))] = int(l.group(1))
    if not days:
        sys.exit("No contribution cells found (is the username right / page format changed?).")
    return days


def empty_days():
    end = dt.date.today()
    return {end - dt.timedelta(days=i): 0 for i in range(52 * 7 + (end.weekday() + 1) % 7)}


def grid(days):
    first = min(days)
    start = first - dt.timedelta(days=(first.weekday() + 1) % 7)  # back to Sunday
    cells = {}
    for d, lvl in days.items():
        cells[((d - start).days // 7, (d.weekday() + 1) % 7)] = lvl
    return max(c for c, _ in cells) + 1, cells


def build(cols, cells, theme):
    pal = PALETTES[theme]
    def ctr(c, r): return PAD + c * PITCH + CELL / 2, PAD + r * PITCH + CELL / 2
    # Boustrophedon route over every cell: down col 0, up col 1, ...
    # Distances are in cell units; the snake enters BODY cells left of the grid.
    pts = [(-BODY, 0)]
    for c in range(cols):
        a, b = (0, 6) if c % 2 == 0 else (6, 0)
        pts += [(c, a), (c, b)]
    last_row = 6 if (cols - 1) % 2 == 0 else 0
    pts.append((cols + BODY + DWELL, last_row))
    path = "M" + " L".join(f"{ctr(c, r)[0]:.1f},{ctr(c, r)[1]:.1f}" for c, r in pts)
    total = BODY + cols * 7 - 1 + BODY + DWELL + 1
    T = total * SEC_PER_CELL

    def dist(c, r): return BODY + c * 7 + (r if c % 2 == 0 else 6 - r)

    out = []
    for (c, r), lvl in sorted(cells.items()):
        x, y = PAD + c * PITCH, PAD + r * PITCH
        base = pal[lvl]
        if lvl:
            p = dist(c, r) / total
            out.append(
                f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" fill="{base}">'
                f'<animate attributeName="fill" dur="{T:.2f}s" repeatCount="indefinite" calcMode="discrete" '
                f'keyTimes="0;{p:.4f};1" values="{base};{pal[0]};{pal[0]}"/></rect>')
        else:
            out.append(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" fill="{base}"/>')
    snake = []
    for k in reversed(range(BODY)):   # draw tail first so the head sits on top
        lag = (T - k * SEC_PER_CELL) % T
        op = 1 if k == 0 else max(0.35, 1 - k * 0.15)
        snake.append(
            f'<rect x="{-CELL / 2}" y="{-CELL / 2}" width="{CELL}" height="{CELL}" rx="3" fill="{ACCENT}" opacity="{op:.2f}">'
            f'<animateMotion dur="{T:.2f}s" repeatCount="indefinite" begin="-{lag:.2f}s" path="{path}"/></rect>')
    w = PAD * 2 + cols * PITCH - GAP
    h = PAD * 2 + 7 * PITCH - GAP
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img" aria-label="Contribution graph with a snake eating the commits">\n'
            f'<title>Contribution snake</title>\n' + "\n".join(out + snake) + "\n</svg>\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--user", default="Exios66")
    ap.add_argument("--html", help="read a saved contributions page instead of fetching")
    ap.add_argument("--empty", action="store_true", help="blank grid (no data)")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "assets"))
    a = ap.parse_args()
    days = empty_days() if a.empty else parse(Path(a.html).read_text() if a.html else fetch(a.user))
    cols, cells = grid(days)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    (out / "snake.svg").write_text(build(cols, cells, "light"))
    (out / "snake-dark.svg").write_text(build(cols, cells, "dark"))
    print(f"wrote {out}/snake.svg and snake-dark.svg ({cols} weeks, "
          f"{sum(1 for v in cells.values() if v)} active days)")


if __name__ == "__main__":
    main()
