#!/usr/bin/env python3
"""Generate self-hosted profile stat cards (dark + light SVG) into assets/.

Uses only the gh CLI (GITHUB_TOKEN in Actions). Public data only.
"""

import json
import os
import subprocess
import sys
import time
from collections import Counter

OWNER = "thejaustin"
LANG_COLORS = {
    "Kotlin": "#A97BFF", "Java": "#B07219", "Dart": "#00B4AB", "Python": "#3572A5",
    "TypeScript": "#3178C6", "JavaScript": "#F1E05A", "C++": "#F34B7D", "C": "#555555",
    "Shell": "#89E051", "CMake": "#DA3434", "HTML": "#E34C26", "CSS": "#663399",
}
THEMES = {
    "dark": dict(bg="#1a1b27", border="#2f3146", title="#70a5fd", text="#c0caf5", muted="#7982a9", up="#3DDC84"),
    "light": dict(bg="#ffffff", border="#d0d7de", title="#0969da", text="#1f2328", muted="#656d76", up="#1a7f37"),
}


def gh(*args):
    r = subprocess.run(["gh"] + list(args), capture_output=True, text=True)
    if r.returncode != 0:
        print(f"gh error: {r.stderr.strip()}", file=sys.stderr)
        return None
    return r.stdout


def fmt(n):
    return f"{n / 1000:.1f}k".replace(".0k", "k") if n >= 1000 else str(n)


def load_drafts():
    try:
        return json.load(open(DRAFTS))
    except (OSError, ValueError):
        return {}


def repo_downloads(name, extra=None):
    """Release downloads for one repo, or None if the lookup failed.

    Counts published releases and pre-releases. Draft pre-releases are invisible to CI, so they come
    from data/draft-downloads.json (scripts/sync_drafts.py) unless their tag has since been published.
    """
    extra = load_drafts() if extra is None else extra
    o = None
    for _ in range(3):
        o = gh("api", "--paginate", f"repos/{OWNER}/{name}/releases",
               "--jq", '.[] | select((.draft | not) or .prerelease) | "\\(.tag_name)\\t\\([.assets[].download_count] | add // 0)"')
        if o is not None:
            break
        time.sleep(2)
    if o is None:
        return None
    seen, total = set(), 0
    for line in o.splitlines():
        tag, _, n = line.rpartition("\t")
        seen.add(tag)
        total += int(n) if n.isdigit() else 0
    return total + sum(n for t, n in extra.get(name, {}).items() if t not in seen)


def collect():
    out = gh("api", "--paginate", f"users/{OWNER}/repos?per_page=100&type=owner")
    if not out:
        sys.exit("could not list repos")
    # --paginate emits concatenated JSON arrays
    dec, repos, i = json.JSONDecoder(), [], 0
    out = out.strip()
    while i < len(out):
        arr, j = dec.raw_decode(out, i)
        repos += arr
        i = j
        while i < len(out) and out[i].isspace():
            i += 1
    user = json.loads(gh("api", f"users/{OWNER}") or "{}")
    mine = [r for r in repos if not r["fork"]]
    stars = sum(r["stargazers_count"] for r in repos)
    extra = load_drafts()
    dl = 0
    for r in repos:
        n = repo_downloads(r["name"], extra)
        if n is None:
            # Never store a partial total: it would show up as a fake dip and a fake gain later.
            sys.exit(f"could not read releases for {r['name']}; leaving stats unchanged")
        dl += n
    langs = Counter()
    for r in mine:
        o = gh("api", f"repos/{OWNER}/{r['name']}/languages")
        if o:
            langs.update(json.loads(o))
    return dict(stars=stars, dl=dl, repos=user.get("public_repos", len(repos)),
                followers=user.get("followers", 0), forks=sum(r["forks_count"] for r in mine),
                langs=langs)


HISTORY = "data/stats-history.json"
DRAFTS = "data/draft-downloads.json"
WINDOW_H = 24
KEYS = ("stars", "dl", "followers", "repos")


WINDOWS = [("1h", 1), ("3h", 3), ("6h", 6), ("12h", 12), ("24h", 24), ("7d", 168)]
SLACK = 900  # cron runs can start a few minutes late


def history_delta(d, per=None):
    """Append this run to the history file.

    `per` is {repo: {"stars": n, "dl": n}} for the tracked projects.
    Returns (24h changes, hours covered, {window: changes}, {window: {repo: changes}}).
    """
    try:
        with open(HISTORY) as f:
            hist = json.load(f)
    except (OSError, ValueError):
        hist = []
    now = int(time.time())

    def since(hours):
        base = None
        for e in hist:  # oldest first; keep the newest entry that is old enough
            if now - e["t"] >= hours * 3600 - SLACK:
                base = e
        return base

    def diff(base):
        return {k: d[k] - base[k] for k in KEYS if k in base}

    per = per or {}

    def pdiff(base):
        old = base.get("p") or {}
        return {r: {"stars": v["stars"] - old[r][0], "dl": v["dl"] - old[r][1]}
                for r, v in per.items() if r in old}

    wins, pwins = {}, {}
    for label, h in WINDOWS:
        base = since(h)
        wins[label] = diff(base) if base else None
        pwins[label] = pdiff(base) if base else None
    base = since(WINDOW_H)
    if base is None and hist:
        base = hist[0]  # not enough history yet: compare with the oldest entry
    delta, hours = {}, 0
    if base:
        hours = max(1, round((now - base["t"]) / 3600))
        delta = diff(base)
    hist.append({"t": now, **{k: d[k] for k in KEYS},
                 "p": {r: [v["stars"], v["dl"]] for r, v in per.items()}})
    hist = [e for e in hist if now - e["t"] <= 35 * 86400]
    os.makedirs("data", exist_ok=True)
    with open(HISTORY, "w") as f:
        json.dump(hist, f, separators=(",", ":"))
    base24 = base
    pdelta = pdiff(base24) if base24 else {}
    return delta, hours, wins, pwins, pdelta


PROJECT_WINDOWS = ["1h", "6h", "24h", "7d"]


def gains_table(wins, pwins=None, featured=()):
    """Markdown table of gains per window, for the tap-to-open section in README."""
    def cell(w, key):
        if w is None:
            return "–"
        return "+" + fmt(max(0, w.get(key, 0)))
    head = "| | " + " | ".join(l for l, _ in WINDOWS) + " |\n|---|" + "---|" * len(WINDOWS)
    rows = [("⭐ Stars", "stars"), ("⬇ Downloads", "dl"), ("👥 Followers", "followers")]
    body = "\n".join(
        f"| {name} | " + " | ".join(cell(wins[l], key) for l, _ in WINDOWS) + " |" for name, key in rows)
    out = head + "\n" + body
    if pwins and featured:
        def pcell(label, repo, has_dl):
            w = (pwins.get(label) or {}).get(repo)
            if w is None:
                return "–"
            s = f"+{fmt(max(0, w['stars']))} ⭐"
            return s + (f"<br>+{fmt(max(0, w['dl']))} ⬇" if has_dl else "")
        head = "| Project | " + " | ".join(PROJECT_WINDOWS) + " |\n|---|" + "---|" * len(PROJECT_WINDOWS)
        lines = [f"| [{r}](https://github.com/{OWNER}/{r}) | "
                 + " | ".join(pcell(l, r, dl) for l in PROJECT_WINDOWS) + " |" for r, dl in featured]
        out += "\n\n" + head + "\n" + "\n".join(lines)
    return out


CYCLE_WINDOWS = ["1h", "6h", "24h", "7d"]
CYCLE_STEP = 3  # seconds each window stays on screen


def card(d, t, delta=None, hours=0, wins=None):
    delta = delta or {}
    # windows to rotate through; falls back to the single oldest-entry comparison
    cyc = [(l, wins[l]) for l in CYCLE_WINDOWS if wins and wins.get(l)]
    if not cyc and delta:
        cyc = [(f"{hours}h", delta)]
    n = len(cyc) or 1
    pct = 100 / n
    total = sum(d["langs"].values()) or 1
    top = d["langs"].most_common(5)
    rows = [("Stars earned", fmt(d["stars"]), "stars"), ("Downloads", fmt(d["dl"]), "dl"),
            ("Public repos", str(d["repos"]), "repos"), ("Followers", str(d["followers"]), "followers")]
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 215" width="100%" role="img" '
         f'aria-label="GitHub stats for {OWNER}">',
         f'<rect x=".5" y=".5" width="479" height="214" rx="8" fill="{t["bg"]}" stroke="{t["border"]}"/>',
         f'<style>.g{{animation:cyc{n} {n * CYCLE_STEP}s infinite}}'
         f'@keyframes cyc{n}{{0%{{opacity:0}}2%,{pct - 2:.1f}%{{opacity:1}}{pct:.1f}%,100%{{opacity:0}}}}'
         f'@media (prefers-reduced-motion:reduce){{.g{{animation:none}}}}</style>',
         f'<g font-family="-apple-system,Segoe UI,Helvetica,Arial,sans-serif">',
         f'<text x="24" y="34" font-size="16" font-weight="600" fill="{t["title"]}">{OWNER} · live stats</text>']
    for i, (k, v, key) in enumerate(rows):
        y = 64 + i * 24
        s.append(f'<text x="24" y="{y}" font-size="13" fill="{t["muted"]}">{k}</text>')
        s.append(f'<text x="196" y="{y}" font-size="13" font-weight="600" fill="{t["text"]}" text-anchor="end">{v}</text>')
        for j, (_, w) in enumerate(cyc):
            if w.get(key, 0) > 0:
                s.append(f'<text class="g" x="202" y="{y}" font-size="11" font-weight="600" fill="{t["up"]}" '
                         f'style="animation-delay:{j * CYCLE_STEP}s;opacity:{1 if j == 0 else 0}">'
                         f'↑{fmt(w[key])}</text>')
    for j, (label, _) in enumerate(cyc):
        s.append(f'<text class="g" x="24" y="204" font-size="11" fill="{t["muted"]}" '
                 f'style="animation-delay:{j * CYCLE_STEP}s;opacity:{1 if j == 0 else 0}">'
                 f'↑ new in the last {label}</text>')
    # language bar + legend on the right
    x0, w = 262, 194
    s.append(f'<text x="{x0}" y="64" font-size="13" fill="{t["muted"]}">Top languages</text>')
    x = x0
    s.append(f'<clipPath id="c{t["bg"][1:]}"><rect x="{x0}" y="74" width="{w}" height="8" rx="4"/></clipPath>')
    s.append(f'<g clip-path="url(#c{t["bg"][1:]})">')
    for n, b in top:
        bw = w * b / sum(b for _, b in top)
        s.append(f'<rect x="{x:.1f}" y="74" width="{bw:.1f}" height="8" fill="{LANG_COLORS.get(n, "#8b949e")}"/>')
        x += bw
    s.append('</g>')
    for i, (n, b) in enumerate(top):
        y = 104 + i * 20
        s.append(f'<circle cx="{x0 + 5}" cy="{y - 4}" r="5" fill="{LANG_COLORS.get(n, "#8b949e")}"/>')
        s.append(f'<text x="{x0 + 18}" y="{y}" font-size="12" fill="{t["text"]}">{n}</text>')
        s.append(f'<text x="{x0 + w}" y="{y}" font-size="12" fill="{t["muted"]}" text-anchor="end">{100 * b / total:.1f}%</text>')
    s.append('</g></svg>')
    return "\n".join(s)


def write_cards(d, delta, hours, wins=None):
    os.makedirs("assets", exist_ok=True)
    for name, th in THEMES.items():
        with open(f"assets/stats-{name}.svg", "w") as f:
            f.write(card(d, th, delta, hours, wins) + "\n")
    print(f"cards written: {fmt(d['stars'])} stars, {fmt(d['dl'])} downloads, {len(d['langs'])} languages")


def main():
    d = collect()
    delta, hours, wins, *_ = history_delta(d)
    write_cards(d, delta, hours, wins)


if __name__ == "__main__":
    main()
