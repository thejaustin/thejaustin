#!/usr/bin/env python3
"""Generate self-hosted profile stat cards (dark + light SVG) into assets/.

Uses only the gh CLI (GITHUB_TOKEN in Actions). Public data only.
"""

import json
import os
import subprocess
import sys
from collections import Counter

OWNER = "thejaustin"
LANG_COLORS = {
    "Kotlin": "#A97BFF", "Java": "#B07219", "Dart": "#00B4AB", "Python": "#3572A5",
    "TypeScript": "#3178C6", "JavaScript": "#F1E05A", "C++": "#F34B7D", "C": "#555555",
    "Shell": "#89E051", "CMake": "#DA3434", "HTML": "#E34C26", "CSS": "#663399",
}
THEMES = {
    "dark": dict(bg="#1a1b27", border="#2f3146", title="#70a5fd", text="#c0caf5", muted="#7982a9"),
    "light": dict(bg="#ffffff", border="#d0d7de", title="#0969da", text="#1f2328", muted="#656d76"),
}


def gh(*args):
    r = subprocess.run(["gh"] + list(args), capture_output=True, text=True)
    if r.returncode != 0:
        print(f"gh error: {r.stderr.strip()}", file=sys.stderr)
        return None
    return r.stdout


def fmt(n):
    return f"{n / 1000:.1f}k".replace(".0k", "k") if n >= 1000 else str(n)


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
    dl = 0
    for r in repos:
        o = gh("api", "--paginate", f"repos/{OWNER}/{r['name']}/releases",
               "--jq", "[.[].assets[].download_count] | add // 0")
        if o:
            dl += sum(int(x) for x in o.split() if x.lstrip("-").isdigit())
    langs = Counter()
    for r in mine:
        o = gh("api", f"repos/{OWNER}/{r['name']}/languages")
        if o:
            langs.update(json.loads(o))
    return dict(stars=stars, dl=dl, repos=user.get("public_repos", len(repos)),
                followers=user.get("followers", 0), forks=sum(r["forks_count"] for r in mine),
                langs=langs)


def card(d, t):
    total = sum(d["langs"].values()) or 1
    top = d["langs"].most_common(5)
    rows = [("Stars earned", fmt(d["stars"])), ("Release downloads", fmt(d["dl"])),
            ("Public repos", str(d["repos"])), ("Followers", str(d["followers"]))]
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 215" width="100%" role="img" '
         f'aria-label="GitHub stats for {OWNER}">',
         f'<rect x=".5" y=".5" width="479" height="214" rx="8" fill="{t["bg"]}" stroke="{t["border"]}"/>',
         f'<g font-family="-apple-system,Segoe UI,Helvetica,Arial,sans-serif">',
         f'<text x="24" y="34" font-size="16" font-weight="600" fill="{t["title"]}">{OWNER} · live stats</text>']
    for i, (k, v) in enumerate(rows):
        y = 64 + i * 24
        s.append(f'<text x="24" y="{y}" font-size="13" fill="{t["muted"]}">{k}</text>')
        s.append(f'<text x="196" y="{y}" font-size="13" font-weight="600" fill="{t["text"]}" text-anchor="end">{v}</text>')
    # language bar + legend on the right
    x0, w = 236, 220
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


def main():
    d = collect()
    os.makedirs("assets", exist_ok=True)
    for name, t in THEMES.items():
        with open(f"assets/stats-{name}.svg", "w") as f:
            f.write(card(d, t) + "\n")
    print(f"cards written: {fmt(d['stars'])} stars, {fmt(d['dl'])} downloads, {len(d['langs'])} languages")


if __name__ == "__main__":
    main()
