#!/usr/bin/env python3
"""Record download counts of draft pre-releases (invisible to CI) in data/draft-downloads.json.

Run locally with your own `gh` login; CI never needs a token that can see drafts.
Usage: python3 scripts/sync_drafts.py   (then commit data/draft-downloads.json)
"""
import json, subprocess, sys

OWNER = "thejaustin"
OUT = "data/draft-downloads.json"
JQ = '.[] | select(.draft and .prerelease) | "\\(.tag_name)\\t\\([.assets[].download_count] | add // 0)"'


def gh(*a):
    r = subprocess.run(["gh", *a], capture_output=True, text=True)
    if r.returncode:
        sys.exit(r.stderr.strip() or "gh failed")
    return r.stdout


repos = json.loads(gh("api", f"users/{OWNER}/repos?per_page=100&type=owner"))
out = {}
for r in repos:
    rows = gh("api", "--paginate", f"repos/{OWNER}/{r['name']}/releases", "--jq", JQ).splitlines()
    d = {t: int(n) for t, _, n in (x.partition("\t") for x in rows) if n.isdigit()}
    if d:
        out[r["name"]] = d
json.dump(out, open(OUT, "w"), indent=1, sort_keys=True)
print(out)
