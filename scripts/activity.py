#!/usr/bin/env python3
"""Rewrite the Recent Activity list in README.md from the public events feed, as plain text."""
import json, re, subprocess, sys

OWNER = "thejaustin"
MAX = 8
START, END = "<!--START_SECTION:activity-->", "<!--END_SECTION:activity-->"


def link(repo, path, text):
    return f"[{text}](https://github.com/{repo}/{path})"


def describe(e):
    repo, p, t = e["repo"]["name"], e["payload"], e["type"]
    name = repo.split("/", 1)[1]
    if t == "PullRequestEvent" and p.get("action") == "closed" and p["pull_request"].get("merged"):
        n = p["pull_request"]["number"]
        return f"Merged {link(repo, f'pull/{n}', f'#{n}')} in {link(repo, '', name)}"
    if t == "ReleaseEvent" and p.get("action") == "published":
        r = p["release"]
        kind = "Pre-released" if r.get("prerelease") else "Released"
        return f"{kind} {link(repo, f'releases/tag/{r['tag_name']}', r['tag_name'])} of {link(repo, '', name)}"
    if t == "IssuesEvent" and p.get("action") in ("opened", "closed"):
        n = p["issue"]["number"]
        return f"{p['action'].capitalize()} issue {link(repo, f'issues/{n}', f'#{n}')} in {link(repo, '', name)}"
    if t == "CreateEvent" and p.get("ref_type") == "repository":
        return f"Created {link(repo, '', name)}"
    return None


raw = subprocess.run(["gh", "api", f"users/{OWNER}/events/public?per_page=100"],
                     capture_output=True, text=True)
if raw.returncode:
    sys.exit(raw.stderr.strip() or "could not read events")
lines, seen = [], set()
for e in json.loads(raw.stdout):
    d = describe(e)
    if d and d not in seen:
        seen.add(d)
        lines.append(d)
if not lines:
    sys.exit("no recent events; leaving README unchanged")
body = "\n".join(f"- {x}" for x in lines[:MAX])
s = open("README.md").read()
new = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda m: f"{START}\n{body}\n{END}", s, flags=re.S)
if new != s:
    open("README.md", "w").write(new)
