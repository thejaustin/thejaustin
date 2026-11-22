#!/usr/bin/env python3
"""Update star and download counts in README.md from GitHub API.

Also writes the stat cards and the tap-to-open gains table.

Repos are discovered from the markers already in README.md, so adding a
<!-- STARS:Name --> or <!-- STATS:Name --> marker is all it takes to track one.
The top Downloads badge uses the same all-repos total as the stat cards.
"""

import json
import re
import subprocess
import sys

from gen_cards import repo_downloads, collect, gains_table, history_delta, write_cards

OWNER = "thejaustin"

def gh(*args):
    result = subprocess.run(["gh"] + list(args), capture_output=True, text=True)
    if result.returncode != 0:
        print(f"gh error: {result.stderr.strip()}", file=sys.stderr)
        return None
    return result.stdout.strip()


def get_stars(repo):
    out = gh("api", f"repos/{OWNER}/{repo}", "--jq", ".stargazers_count")
    return int(out) if out and out.isdigit() else 0


def get_downloads(repo):
    return repo_downloads(repo) or 0


def fmt_k(n):
    """Format a number: 1234 -> '1.2k', 45600 -> '45.6k', 999 -> '999'"""
    if n >= 1000:
        k = n / 1000
        s = f"{k:.1f}k"
        s = s.rstrip("0").rstrip(".")
        if not s.endswith("k"):
            s += "k"
        return s
    return str(n)


def fmt_badge_stars(n):
    """Format for shields.io badge URL: 1700 -> '1.7k%2B'"""
    s = fmt_k(n)
    return f"{s}%2B"


def fmt_badge_dl(n):
    """Format for shields.io badge URL: 156000 -> '156k%2B'"""
    s = fmt_k(n)
    return f"{s}%2B"


def update_readme(stars: dict, downloads: dict, total: int, gains: str, pdelta: dict) -> bool:
    with open("README.md", "r") as f:
        content = f.read()

    original = content

    total_dl = total

    # --- Top summary badges ---
    content = re.sub(
        r"(shields\.io/badge/Downloads-)[^-?&\s]+(-[0-9A-Fa-f]{6})(\?)",
        lambda m: f"{m.group(1)}{fmt_badge_dl(total_dl)}{m.group(2)}{m.group(3)}",
        content,
    )

    content = re.sub(
        r"(<!-- GAINS -->\n).*?(\n<!-- /GAINS -->)",
        lambda m: m.group(1) + gains + m.group(2),
        content,
        flags=re.S,
    )

    # --- Featured project stats lines ---
    # Pattern: <!-- STATS:RepoName -->N stars · Mk downloads<!-- /STATS --> · Lang
    # or:      <!-- STATS:RepoName -->N stars<!-- /STATS --> · Lang
    def replace_stats_marker(m):
        repo = m.group(1)
        s = stars.get(repo, 0)
        d = downloads.get(repo, 0)
        up = pdelta.get(repo, {})
        us = f" (+{fmt_k(up['stars'])})" if up.get("stars", 0) > 0 else ""
        ud = f" (+{fmt_k(up['dl'])})" if up.get("dl", 0) > 0 else ""
        if d:
            return f"<!-- STATS:{repo} -->{s} stars{us} · {fmt_k(d)} downloads{ud}<!-- /STATS -->"
        return f"<!-- STATS:{repo} -->{s} stars{us}<!-- /STATS -->"

    content = re.sub(
        r"<!-- STATS:(\w[\w-]*) -->.*?<!-- /STATS -->",
        replace_stats_marker,
        content,
    )

    # --- More projects table rows ---
    # Pattern: <!-- STARS:RepoName -->N<!-- /STARS --> and <!-- DL:RepoName -->Mk<!-- /DL -->
    def replace_stars_cell(m):
        repo = m.group(1)
        s = stars.get(repo, 0)
        return f"<!-- STARS:{repo} -->{s}<!-- /STARS -->"

    def replace_dl_cell(m):
        repo = m.group(1)
        d = downloads.get(repo, 0)
        if d:
            return f"<!-- DL:{repo} -->{fmt_k(d)}<!-- /DL -->"
        return f"<!-- DL:{repo} -->—<!-- /DL -->"

    content = re.sub(
        r"<!-- STARS:(\w[\w-]*) -->.*?<!-- /STARS -->",
        replace_stars_cell,
        content,
    )
    content = re.sub(
        r"<!-- DL:(\w[\w-]*) -->.*?<!-- /DL -->",
        replace_dl_cell,
        content,
    )

    if content == original:
        return False

    with open("README.md", "w") as f:
        f.write(content)
    return True


def tracked_repos():
    """Repo names from the markers in README.md, plus whether each shows downloads."""
    with open("README.md") as f:
        content = f.read()
    repos = {}
    for kind, repo in re.findall(r"<!-- (STATS|STARS|DL):(\w[\w-]*) -->", content):
        repos.setdefault(repo, False)
        if kind in ("DL", "STATS"):
            repos[repo] = True
    return repos


def featured_repos(downloads):
    """(repo, shows downloads) for the projects in the Featured section, in README order."""
    with open("README.md") as f:
        names = re.findall(r"<!-- STATS:(\w[\w-]*) -->", f.read())
    return [(r, r in downloads and downloads[r] > 0) for r in names]


def main():
    stars = {}
    downloads = {}

    for repo, has_dl in tracked_repos().items():
        print(f"Fetching {repo}...")
        stars[repo] = get_stars(repo)
        downloads[repo] = get_downloads(repo) if has_dl else 0
        print(f"  {repo}: {stars[repo]} stars, {downloads[repo]} downloads")

    per = {r: {"stars": stars[r], "dl": downloads[r]} for r in stars}
    d = collect()
    delta, hours, wins, pwins, pdelta = history_delta(d, per)
    write_cards(d, delta, hours, wins)
    gains = gains_table(wins, pwins, featured_repos(downloads))
    changed = update_readme(stars, downloads, d["dl"], gains, pdelta)
    if changed:
        print("README.md updated with fresh stats.")
    else:
        print("README.md already up to date.")


if __name__ == "__main__":
    main()
