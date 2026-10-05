#!/usr/bin/env python3
"""Update star and download counts in README.md from GitHub API."""

import json
import re
import subprocess
import sys

OWNER = "thejaustin"

FEATURED_REPOS = [
    ("ShizukuPlus", True),
    ("hexodus", True),
    ("ObtainiumPlus", True),
    ("ShizukuPlus-API", False),
    ("termux-ai-app", True),
    ("sharemove", True),
]

MORE_REPOS = [
    ("SuperShade", True),
    ("pearity", True),
    ("ContactsPlus", True),
    ("smartlauncher-morphe-patches", True),
    ("AutoCat", True),
    ("afdroid", False),
    ("maps-timeline-viewer", False),
]


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
    out = gh(
        "api", "--paginate",
        f"repos/{OWNER}/{repo}/releases",
        "--jq", "[.[].assets[].download_count] | add // 0",
    )
    if not out:
        return 0
    total = sum(int(line) for line in out.splitlines() if line.strip().lstrip("-").isdigit())
    return max(0, total)


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


def update_readme(stars: dict, downloads: dict) -> bool:
    with open("README.md", "r") as f:
        content = f.read()

    original = content

    total_stars = sum(stars.values())
    total_dl = sum(downloads.values())

    # --- Top summary badges ---
    content = re.sub(
        r"(shields\.io/badge/Stars-)([^?&\s]+)(%3F|\?)",
        lambda m: f"{m.group(1)}{fmt_badge_stars(total_stars)}{m.group(3)}",
        content,
    )
    content = re.sub(
        r"(shields\.io/badge/Downloads-)([^?&\s]+)(%3F|\?)",
        lambda m: f"{m.group(1)}{fmt_badge_dl(total_dl)}{m.group(3)}",
        content,
    )

    # --- Featured project stats lines ---
    # Pattern: <!-- STATS:RepoName -->**N ★ · Mk ⬇**<!-- /STATS --> · Lang
    # or:      <!-- STATS:RepoName -->**N ★**<!-- /STATS --> · Lang
    def replace_stats_marker(m):
        repo = m.group(1)
        s = stars.get(repo, 0)
        d = downloads.get(repo, 0)
        if d:
            return f"<!-- STATS:{repo} -->**{s} ★ · {fmt_k(d)} ⬇**<!-- /STATS -->"
        return f"<!-- STATS:{repo} -->**{s} ★**<!-- /STATS -->"

    content = re.sub(
        r"<!-- STATS:(\w[\w-]*) -->.*?<!-- /STATS -->",
        replace_stats_marker,
        content,
    )

    # --- More projects table rows ---
    # Pattern: <!-- STARS:RepoName -->⭐ N<!-- /STARS --> and <!-- DL:RepoName -->⬇ Mk<!-- /DL -->
    def replace_stars_cell(m):
        repo = m.group(1)
        s = stars.get(repo, 0)
        return f"<!-- STARS:{repo} -->⭐ {s}<!-- /STARS -->"

    def replace_dl_cell(m):
        repo = m.group(1)
        d = downloads.get(repo, 0)
        if d:
            return f"<!-- DL:{repo} -->⬇ {fmt_k(d)}<!-- /DL -->"
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


def main():
    all_repos = FEATURED_REPOS + MORE_REPOS
    stars = {}
    downloads = {}

    for repo, has_dl in all_repos:
        print(f"Fetching {repo}...")
        stars[repo] = get_stars(repo)
        downloads[repo] = get_downloads(repo) if has_dl else 0
        print(f"  {repo}: {stars[repo]} ★, {downloads[repo]} ⬇")

    changed = update_readme(stars, downloads)
    if changed:
        print("README.md updated with fresh stats.")
    else:
        print("README.md already up to date.")


if __name__ == "__main__":
    main()
