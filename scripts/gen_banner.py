#!/usr/bin/env python3
"""Write assets/banner-{dark,light}.svg: self-hosted profile banner.

Run by hand when the wording changes. Lines rotate with CSS only (works in
<img>); with reduced motion, or no CSS animation, the first line stays put.
"""

LINES = [
    "Extending what Android can do",
    "Shizuku · One UI · Kotlin",
    "Built on my phone, with AI help",
    "Small tools, big punch",
]
STEP = 3  # seconds per line

THEMES = {
    "dark": dict(bg="#1a1b27", border="#2f3146", title="#c0caf5", accent="#36BCF7", sub="#9aa5ce"),
    "light": dict(bg="#f6f8fa", border="#d0d7de", title="#1f2328", accent="#0b7bb5", sub="#4b535c"),
}


def svg(c):
    total = STEP * len(LINES)
    texts = []
    for i, line in enumerate(LINES):
        texts.append(
            f'<text class="l" x="400" y="118" text-anchor="middle" '
            f'style="animation-delay:{i * STEP}s;opacity:{1 if i == 0 else 0}">{line}</text>'
        )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 160" width="100%" role="img" aria-label="Hi, I'm Austin. Extending what Android can do.">
<style>
.l{{font:500 22px -apple-system,Segoe UI,Helvetica,Arial,sans-serif;fill:{c['accent']};animation:s {total}s infinite}}
@keyframes s{{0%{{opacity:0}}3%,22%{{opacity:1}}25%,100%{{opacity:0}}}}
@media (prefers-reduced-motion:reduce){{.l{{animation:none}}}}
</style>
<rect x=".5" y=".5" width="799" height="159" rx="12" fill="{c['bg']}" stroke="{c['border']}"/>
<text x="400" y="72" text-anchor="middle" font-family="-apple-system,Segoe UI,Helvetica,Arial,sans-serif" font-size="40" font-weight="700" fill="{c['title']}">Hi, I'm Austin</text>
{chr(10).join(texts)}
</svg>
"""


for name, c in THEMES.items():
    with open(f"assets/banner-{name}.svg", "w") as f:
        f.write(svg(c))
print("banners written")
