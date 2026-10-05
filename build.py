#!/usr/bin/env python3
"""Rebuild docs/index.html from live GitHub data.

Needs the gh CLI, logged in. Run: python3 build.py
Data source: GitHub search for merged PRs authored by OWNER.
Excluded: repos OWNER owns, private repos, and self-listing PRs
(adding OWNER's own products to awesome lists, registries and package indexes).
"""
import datetime as dt
import html
import json
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

OWNER = "theluckystrike"
EMAIL = "lipmichal@gmail.com"
OUT = Path(__file__).resolve().parent / "docs" / "index.html"

# ======================================================================
# PAYMENT LINKS: the owner pastes Stripe payment link URLs here.
# Each value is "" until filled. While a value is "", no Pay now button is
# shown for it. Paste the full https://buy.stripe.com/... URL, then run:
#   python3 build.py && git add docs && git commit -m "Add payment links" && git push
#   audit  = $400 one-time i18n audit and fix
#   pilot  = $400 one-time pilot month
#   upkeep = $750 a month locale upkeep (Stripe subscription link)
# ======================================================================
PAYMENT_LINKS = {"audit": "https://buy.stripe.com/eVq14o7Iu0tigstaYZ43S0D", "pilot": "https://buy.stripe.com/7sY28sd2Ogsggstd7743S0E", "upkeep": "https://buy.stripe.com/7sYdRa8My8ZO2BD3wx43S0F"}

REPO_URL = "https://github.com/theluckystrike/oss-maintenance"
FORMS = {
    "audit": REPO_URL + "/issues/new?template=i18n-audit.yml",
    "pilot": REPO_URL + "/issues/new?template=pilot-or-upkeep.yml",
}
PAY_LABELS = {"audit": "Pay now, audit $400", "pilot": "Pay now, pilot $400",
              "upkeep": "Pay now, upkeep $750 a month"}

START_CSS = """
.btns { display: flex; flex-wrap: wrap; gap: 10px; margin: 4px 0 14px; }
.btn { display: inline-block; padding: 11px 16px; border-radius: 8px; font-weight: 600;
  text-decoration: none; border: 1px solid var(--accent); line-height: 1.3; }
.btn.go { background: var(--accent); color: var(--bg); }
.btn.pay, .btn.alt { background: var(--card); color: var(--accent); }
.btn:hover { text-decoration: underline; }
.start ol { padding-left: 22px; margin: 0 0 12px; }
.start ol li { margin-bottom: 6px; }
.start .row { margin: 0 0 6px; font-weight: 600; }
"""


def start_block(first, mail_href, h=2):
    """The Start now block. first = "audit" or "pilot", whichever leads on this page.
    A Pay now button appears only for PAYMENT_LINKS values that are filled in."""
    def esc(x):
        return html.escape(str(x), quote=True)
    offers = {
        "audit": ("i18n audit and fix, $400 fixed", "Start now: i18n audit", ["audit"]),
        "pilot": ("Pilot month $400, or locale upkeep $750 a month", "Start now: pilot or upkeep",
                  ["pilot", "upkeep"]),
    }
    order = [first] + [k for k in offers if k != first]
    rows = []
    for k in order:
        label, go, pays = offers[k]
        btns = [f'<a class="btn go" href="{esc(FORMS[k])}">{esc(go)}</a>']
        btns += [f'<a class="btn pay" href="{esc(PAYMENT_LINKS[p])}">{esc(PAY_LABELS[p])}</a>'
                 for p in pays if PAYMENT_LINKS.get(p, "").startswith("https://")]
        rows.append(f'<p class="row">{esc(label)}</p><div class="btns">{"".join(btns)}</div>')
    return f"""<h{h} id="start">Start now</h{h}>
<div class="start">
{"".join(rows)}
<p>Or email <a href="{esc(mail_href)}">{esc(EMAIL)}</a>. Use email for a private repo or anything you'd rather not post in public, since the form opens a public GitHub issue.</p>
<p class="row">What happens next</p>
<ol>
<li>I reply in writing within 24 hours with the scope and a payment link.</li>
<li>Work starts when the payment arrives.</li>
<li>You get the written report and the first PR within 3 business days.</li>
</ol>
<p class="muted">No calls. Every step happens in writing, in the issue or by email.</p>
</div>"""

# Orgs checked by hand on 2026-10-03: GitHub org profile links to the website
# named here, and that website is a company or foundation with its own product.
# An org only gets the label if it also shows up in the live data below.
BACKED = {
    "medusajs": ("Medusa", "company", "https://medusajs.com"),
    "PrefectHQ": ("Prefect", "company", "https://prefect.io"),
    "microlinkhq": ("Microlink", "company", "https://microlink.io"),
    "toss": ("Toss", "company", "https://toss.im"),
    "unidoc": ("UniDoc", "company", "https://unidoc.io"),
    "dailydotdev": ("daily.dev", "company", "https://daily.dev"),
    "HeyPuter": ("Puter", "company", "https://puter.com"),
    "pixiebrix": ("PixieBrix", "company", "https://www.pixiebrix.com"),
    "raindropio": ("Raindrop.io", "company", "https://raindrop.io"),
    "GoogleChrome": ("Google Chrome", "company", "https://developer.chrome.com"),
    "ChromeDevTools": ("Chrome DevTools", "company", "https://devtools.chrome.com"),
    "mozilla": ("Mozilla", "company", "https://www.mozilla.org"),
    "tilfinltd": ("Tilfin Ltd.", "company", "http://www.tilfin.com"),
    "IndustriAgents": ("IndustriAgents", "company", "https://www.industriagents.com"),
    "autonomys": ("Autonomys", "company", "https://autonomys.xyz"),
    "stellar": ("Stellar", "foundation", "https://www.stellar.org"),
}
# Order used for the names in the opening paragraph (most recognisable first).
LEAD_NAMES = ["medusajs", "PrefectHQ", "stellar", "microlinkhq", "toss", "dailydotdev"]

LIST_REPO = re.compile(r"awesome|tiny-helpers|PackageList|^nix-community/NUR$|opam-repository|mcp-servers$|mcp-list", re.I)
OWN_PRODUCT = re.compile(r"zovo|belikenative|theluckystrike|epochpilot|gen8x|kappakit|lochbot|heytensor|readability|priceping|holdfolio|office[- ]suite", re.I)
I18N = re.compile(r"translat|locale|i18n|l10n|german|hebrew|hungarian|catalog", re.I)
DOCS = re.compile(r"^docs|\bdocs?\b|readme|mdn|chrome web store|documentation|\blinks?\b|^content|guide|javadoc|\badr\b", re.I)


def gh(*args):
    r = subprocess.run(["gh", *args], capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def is_self_listing(repo, title):
    if repo == "ocaml/opam-repository":
        return True
    if LIST_REPO.search(repo) and re.match(r"(add|\[new release\])", title, re.I):
        return True
    return bool(OWN_PRODUCT.search(title))


def category(title, repo=""):
    if I18N.search(title):
        return "i18n"
    if DOCS.search(title) or re.search(r"[-_/]docs?$", repo, re.I):
        return "docs"
    return "code"


def collect():
    prs = gh("search", "prs", "--author", OWNER, "--merged", "--limit", "1000",
             "--json", "url,repository,title,closedAt")
    meta, kept, dropped = {}, [], Counter()
    for p in prs:
        repo = p["repository"]["nameWithOwner"]
        org = repo.split("/")[0]
        if org.lower() == OWNER:
            dropped["own"] += 1
            continue
        if repo not in meta:
            meta[repo] = gh("api", f"repos/{repo}", "--jq",
                            "{private, stars: .stargazers_count, owner_type: .owner.type}")
        if meta[repo]["private"]:
            dropped["private"] += 1
            continue
        if is_self_listing(repo, p["title"]):
            dropped["listing"] += 1
            continue
        kept.append({"repo": repo, "org": org, "title": p["title"], "url": p["url"],
                     "date": p["closedAt"][:10], "cat": category(p["title"], repo),
                     "stars": meta[repo]["stars"]})
    kept.sort(key=lambda x: (x["date"], x["url"]), reverse=True)
    return prs, kept, dropped


def e(s):
    return html.escape(str(s), quote=True)


def fmt_date(d):
    return dt.date.fromisoformat(d).strftime("%-d %b %Y")


def render(prs, kept, dropped):
    now = dt.datetime.now(dt.timezone.utc)
    today = now.date()
    repos = {k["repo"] for k in kept}
    by_org = defaultdict(list)
    for k in kept:
        by_org[k["org"]].append(k)
    backed = [o for o in by_org if o in BACKED]
    backed_prs = sum(len(by_org[o]) for o in backed)
    cats = Counter(k["cat"] for k in kept)
    last90 = sum(1 for k in kept if (today - dt.date.fromisoformat(k["date"])).days <= 90)
    first = min(k["date"] for k in kept)
    lead = [BACKED[o][0] for o in LEAD_NAMES if o in by_org][:4]
    lead_txt = ", ".join(lead[:-1]) + " and " + lead[-1] if len(lead) > 1 else "".join(lead)

    stats = [
        (len(kept), "merged PRs in other people's repos"),
        (len(repos), "repos"),
        (len(by_org), "owners (orgs and people)"),
        (len(backed), "owners backed by a company or foundation"),
        (last90, "merged in the last 90 days"),
    ]
    stat_html = "".join(f'<div class="stat"><b>{n}</b><span>{e(l)}</span></div>' for n, l in stats)

    cat_desc = {
        "code": "Bug fixes, TypeScript types, dependency and security bumps, build tooling and packaging.",
        "i18n": "Missing locale keys filled, catalogs fixed, new languages added.",
        "docs": "Docs that had drifted from the code, dead links, guides and examples.",
    }
    cat_html = "".join(
        f'<div class="cat"><b>{cats.get(c, 0)}</b><div><h3>{c}</h3><p>{cat_desc[c]}</p></div></div>'
        for c in ("code", "i18n", "docs"))

    def pr_li(k, show_repo=True):
        tag = f'<span class="tag t-{k["cat"]}">{k["cat"]}</span>'
        repo = f'<span class="repo">{e(k["repo"])}</span>' if show_repo else ""
        return (f'<li><a href="{e(k["url"])}">{e(k["title"])}</a>'
                f'<span class="meta">{repo}{tag}<time>{fmt_date(k["date"])}</time></span></li>')

    recent_html = "".join(pr_li(k) for k in kept[:25])

    org_rows = []
    for o in sorted(by_org, key=lambda o: (o not in BACKED, -len(by_org[o]), o.lower())):
        items = by_org[o]
        label = ""
        if o in BACKED:
            name, kind, site = BACKED[o]
            label = f' <a class="badge" href="{e(site)}">{e(name)}, {kind}</a>'
        stars = max(i["stars"] for i in items)
        org_rows.append(
            f'<details><summary><span class="org">{e(o)}</span>{label}'
            f'<span class="count">{len(items)} PR{"s" if len(items) != 1 else ""}'
            f' &middot; top repo {stars:,} stars</span></summary>'
            f'<ul class="prs">{"".join(pr_li(i) for i in items)}</ul></details>')
    orgs_html = "".join(org_rows)

    drop_words = {"own": "PRs to my own repos", "private": "PRs in private repos",
                  "listing": "PRs that only add my own products to awesome lists and registries"}
    drop_txt = ", ".join(f"{dropped[k]} {w}" for k, w in drop_words.items() if dropped.get(k))
    gen = now.strftime("%-d %b %Y, %H:%M UTC")
    mail = (f"mailto:{EMAIL}?subject=" + "Maintenance%20for%20%3Crepo%3E")

    import build_audit
    return TEMPLATE.format(
        audit_found=sum(r["found"] for r in build_audit.REPOS), audit_repos=len(build_audit.REPOS),
        n=len(kept), r=len(repos), o=len(by_org), b=len(backed), bp=backed_prs,
        lead=e(lead_txt), first=fmt_date(first), stat_html=stat_html, cat_html=cat_html,
        recent_html=recent_html, orgs_html=orgs_html, total=len(prs), drop=e(drop_txt),
        gen=gen, email=EMAIL, mail=mail, owner=OWNER,
        start=start_block("pilot", mail), start_css=START_CSS)


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OSS maintenance by theluckystrike</title>
<meta name="description" content="{n} merged PRs in {r} public repos, and a flat monthly offer to keep doing that work for your repo, in writing.">
<style>
:root {{
  --bg: #fbfaf7; --fg: #1d1d1b; --muted: #5f5e58; --line: #e3e1da; --card: #ffffff;
  --accent: #1f5f4a; --accent-soft: #e4efe9; --code: #3d4f8a; --i18n: #8a4b1f; --docs: #5b5b5b;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --bg: #141513; --fg: #ecebe6; --muted: #a3a29b; --line: #2d2e2a; --card: #1b1c1a;
    --accent: #7fc4a6; --accent-soft: #1f2b26; --code: #9fb0ea; --i18n: #e0a77c; --docs: #b8b8b8;
  }}
}}
:root[data-theme="dark"] {{
  --bg: #141513; --fg: #ecebe6; --muted: #a3a29b; --line: #2d2e2a; --card: #1b1c1a;
  --accent: #7fc4a6; --accent-soft: #1f2b26; --code: #9fb0ea; --i18n: #e0a77c; --docs: #b8b8b8;
}}
* {{ box-sizing: border-box; }}
html {{ -webkit-text-size-adjust: 100%; }}
body {{ margin: 0; background: var(--bg); color: var(--fg);
  font: 17px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
main {{ max-width: 760px; margin: 0 auto; padding: 40px 16px 64px; }}
a {{ color: var(--accent); text-underline-offset: 2px; }}
h1 {{ font-size: clamp(28px, 6vw, 40px); line-height: 1.15; margin: 8px 0 16px; letter-spacing: -0.01em; }}
h2 {{ font-size: 22px; margin: 48px 0 12px; }}
h3 {{ font-size: 17px; margin: 0; }}
p {{ margin: 0 0 14px; }}
.kicker {{ color: var(--muted); font-size: 15px; }}
.lead {{ font-size: 19px; }}
.muted {{ color: var(--muted); font-size: 15px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 10px; margin: 24px 0 8px; }}
.stat {{ background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 12px 14px; }}
.stat b {{ display: block; font-size: 28px; line-height: 1.1; }}
.stat span {{ color: var(--muted); font-size: 14px; line-height: 1.3; display: block; margin-top: 4px; }}
.cat {{ display: flex; gap: 14px; align-items: baseline; padding: 10px 0; border-bottom: 1px solid var(--line); }}
.cat b {{ font-size: 24px; min-width: 52px; }}
.cat p {{ margin: 2px 0 0; color: var(--muted); font-size: 15px; }}
ul.prs {{ list-style: none; padding: 0; margin: 0; }}
ul.prs li {{ padding: 10px 0; border-bottom: 1px solid var(--line); overflow-wrap: anywhere; }}
ul.prs a {{ text-decoration: none; color: var(--fg); }}
ul.prs a:hover {{ color: var(--accent); text-decoration: underline; }}
.meta {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; font-size: 13px; color: var(--muted); margin-top: 3px; }}
.repo {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
.tag {{ border: 1px solid currentColor; border-radius: 4px; padding: 0 5px; font-size: 12px; }}
.t-code {{ color: var(--code); }} .t-i18n {{ color: var(--i18n); }} .t-docs {{ color: var(--docs); }}
details {{ border-bottom: 1px solid var(--line); }}
summary {{ cursor: pointer; padding: 10px 0; display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }}
summary .org {{ font-weight: 600; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 15px; }}
summary .count {{ color: var(--muted); font-size: 13px; margin-left: auto; }}
.badge {{ background: var(--accent-soft); color: var(--accent); border-radius: 999px; padding: 1px 9px; font-size: 13px; text-decoration: none; }}
details ul.prs {{ padding-left: 12px; margin-bottom: 8px; }}
.tiers {{ display: grid; gap: 14px; margin-top: 16px; }}
.tier {{ background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 18px 18px 8px; }}
.tier.main {{ border-color: var(--accent); }}
.tier header {{ display: flex; flex-wrap: wrap; justify-content: space-between; gap: 6px 16px; align-items: baseline; margin-bottom: 8px; }}
.tier h3 {{ font-size: 19px; }}
.price {{ font-size: 20px; font-weight: 700; }}
.price small {{ font-weight: 400; color: var(--muted); font-size: 14px; }}
.tier ul {{ padding-left: 20px; margin: 0 0 12px; }}
.tier li {{ margin-bottom: 4px; }}
.terms li, .not li {{ margin-bottom: 6px; }}
.agency {{ background: var(--accent-soft); border-radius: 12px; padding: 4px 20px 8px; margin-top: 32px; }}
.agency h2 {{ margin-top: 16px; }}
.agency a.more {{ font-weight: 600; }}
.start {{ background: var(--accent-soft); border-radius: 12px; padding: 20px; margin-top: 16px; }}
.start a.mail {{ font-size: 20px; font-weight: 700; overflow-wrap: anywhere; }}
{start_css}
footer {{ margin-top: 56px; padding-top: 16px; border-top: 1px solid var(--line); color: var(--muted); font-size: 14px; }}
</style>
</head>
<body>
<main>
<p class="kicker">Michael, <a href="https://github.com/{owner}">github.com/{owner}</a>, based in Poland, works in writing</p>
<h1>Maintenance for teams that already merged my work</h1>
<p class="lead">{n} of my pull requests are merged in {r} public repos that belong to {o} different owners. {b} of those owners are companies or foundations, {lead} among them.</p>
<p>If your team merged one of these, you've already reviewed how I work. This page lists every one of them, then offers the same kind of work on a schedule for a flat monthly fee.</p>
<p><a class="btn go" href="#start">Start now</a> <a class="btn alt" href="#offer">See prices</a></p>
<div class="stats">{stat_html}</div>
<p class="muted">Counted live from GitHub search on {gen}. Left out on purpose: {drop}. First external merge in this set was on {first}.</p>

<section class="agency">
<h2>White-label capacity for agencies</h2>
<p>If you build Medusa, Strapi or similar stores for clients, I can take the upgrades and i18n work for your client stores, as PRs your team reviews. The easiest start is a <a href="i18n-audit/">$400 fixed-price i18n audit</a> of one client repo: a written report plus one PR that fixes every broken placeholder, tag and brand leak. In a sample run on {audit_repos} open-source apps it found {audit_found} broken strings, like white-label customers seeing the vendor's name.</p>
<p><a class="more" href="i18n-audit/">See the audit and the sample report</a></p>
</section>

<h2>What the merged work is</h2>
{cat_html}
<p class="muted" style="margin-top:10px">Categories come from the PR titles, so a few borderline PRs could sit in a neighbouring bucket. Every PR is linked below if you want to check.</p>

<h2>Recent merges</h2>
<ul class="prs">{recent_html}</ul>

<h2>Every repo, grouped by owner</h2>
<p class="muted">Company and foundation labels were checked against each org's GitHub profile and website. {bp} of the {n} PRs went to those owners.</p>
{orgs_html}

<h2 id="offer">The offer</h2>
<p>Same kind of PRs, on a schedule, for a flat fee. All of it happens in writing, in your issues, PR threads and email. I don't do calls.</p>
<p>Four prices, all in USD. A $400 pilot month, $750 a month for locale upkeep, $1,500 a month for maintenance, and a $400 fixed-price i18n audit for one repo.</p>
<div class="tiers">
<section class="tier">
<header><h3>Pilot month</h3><span class="price">$400 <small>first month, up to 4 hours</small></span></header>
<p>You pick one problem. A red CI job, a lockfile nobody dares to touch, a locale that's half empty. I fix it in PRs you review. At the end of the month you tell me in writing whether to continue. If you don't, nothing renews.</p>
</section>
<section class="tier">
<header><h3>Locale upkeep</h3><span class="price">$750 <small>per month, up to 6 hours</small></span></header>
<ul>
<li>After each release I fill the keys your existing locales are missing, one PR per release.</li>
<li>Up to 8 locales.</li>
<li>Placeholders, plural forms and any glossary you keep get checked by script before the PR goes up.</li>
<li>I draft with machine translation and correct by hand. I'm not a native speaker of most target languages, so native review stays on your side.</li>
</ul>
</section>
<section class="tier main">
<header><h3>Maintenance</h3><span class="price">$1,500 <small>per month, up to 10 hours</small></span></header>
<ul>
<li>Dependency updates where I read the changelog and fix what breaks, instead of merging whatever a bot opened.</li>
<li>CI drift. Jobs that went red because a runner image, an action or a toolchain moved under you.</li>
<li>Issue triage with labels, a repro attempt and a short written note on each issue.</li>
<li>Small fixes that come out of triage.</li>
<li>A written summary at the end of each month, with what changed and what's waiting on you.</li>
</ul>
</section>
<section class="tier">
<header><h3>i18n audit and fix</h3><span class="price">$400 <small>fixed price, one repo, up to 40 locales</small></span></header>
<p>A one-off job, not a subscription. I check every locale against your source language for broken placeholders, ICU syntax, lost tags and brand leaks, then send a written report and one PR that fixes every objective bug, within 3 business days. <a href="i18n-audit/">Details and a sample report</a>.</p>
</section>
</div>

<h2>How it runs</h2>
<ul class="terms">
<li>I reply in writing within 24 hours.</li>
<li>Work arrives as normal PRs. You review and merge, like you already did.</li>
<li>I don't need production access, deploy rights or secrets.</li>
<li>Hours stop at the cap. If a month needs more, I ask in writing before going over.</li>
<li>Unused hours don't roll over.</li>
<li>Monthly tiers are billed in advance, in USD, by card payment link or bank transfer invoice. Cancel by email any time and the next month isn't billed. The audit is billed once.</li>
</ul>

<h2>Not included</h2>
<ul class="not">
<li>Calls or meetings of any kind.</li>
<li>On-call, incident response or uptime promises.</li>
<li>New features and roadmap work.</li>
<li>Security audits or guarantees.</li>
<li>Native-speaker sign-off on translations.</li>
</ul>

{start}

<h2>To be clear</h2>
<p>None of the projects on this page pays me. Their maintainers reviewed and merged public PRs, and being listed here doesn't mean they endorse this offer. I have no paying maintenance clients yet, so there are no testimonials. The numbers above are the whole track record, and each one links to the PR.</p>

<footer>
<p>Built by <a href="https://github.com/{owner}/oss-maintenance/blob/main/build.py">build.py</a> from GitHub search ({total} merged PRs found before filtering). Last built {gen}.</p>
<p><a href="https://github.com/{owner}">github.com/{owner}</a></p>
</footer>
</main>
</body>
</html>
"""


def main():
    import build_audit
    build_audit.main()
    prs, kept, dropped = collect()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(prs, kept, dropped))
    (OUT.parent / "data.json").write_text(json.dumps(
        {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
         "dropped": dropped, "merged_external": kept}, indent=1))
    cats = Counter(k["cat"] for k in kept)
    print(f"{len(kept)} PRs, {len({k['repo'] for k in kept})} repos, "
          f"{len({k['org'] for k in kept})} owners, cats {dict(cats)}, dropped {dict(dropped)}")


if __name__ == "__main__":
    main()
