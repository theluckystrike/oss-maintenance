#!/usr/bin/env python3
"""Rebuild docs/i18n-audit/index.html, the fixed-price i18n audit page.

Needs the gh CLI, logged in. Run: python3 build_audit.py (build.py also runs it).

The finding counts below come from the audit runs of 2026-10-03 (one TSV row
per broken string, per locale). The before/after strings are quoted from the
diffs of the linked PRs. PR state (open, merged, closed) is read live from
GitHub every time this script runs, so the page never calls an open PR merged.
"""
import datetime as dt
import html
import json
import subprocess
from pathlib import Path

EMAIL = "lipmichal@gmail.com"
OWNER = "theluckystrike"
OUT = Path(__file__).resolve().parent / "docs" / "i18n-audit" / "index.html"
PRICE = 400
MAX_LOCALES = 40
DAYS = 3

# kind labels, plain words
K = {
    "dropped": "placeholder dropped",
    "renamed": "placeholder renamed or translated",
    "broken": "ICU message does not parse",
    "extra": "placeholder the source does not have",
    "mixed": "mixed placeholder syntax",
    "syntax": "wrong placeholder syntax",
    "tags": "rich text tags lost",
    "plural": "plural form drops {{count}}",
    "markup": "raw markup shown to users",
    "key": "key the code asks for is missing",
}

REPOS = [
    {
        "name": "Medusa", "repo": "medusajs/medusa", "pr": 17118,
        "app": "Admin dashboard, i18next",
        "found": 37, "locales": 5, "locales_note": "ar 15, el 11, fr 6, es 4, ptPT 1. The other 29 locales were clean.",
        "kinds": [("dropped", 14), ("tags", 11), ("plural", 9), ("extra", 2), ("syntax", 1)],
        "fixed": 32, "fixed_locales": 5,
        "fixed_note": "5 Arabic singular forms left as they are on purpose, because they spell out \"one\" in words, which is natural Arabic. The repo's own i18n-validation-admin-dashboard CI check passed on the PR.",
        "examples": [
            ("es", "Shipping price rule summary",
             "Rango",
             "Si <0>{{attribute}}</0> está entre <1>{{gte}}</1> y <2>{{lte}}</2>",
             "The Spanish admin showed only \"Rango\" (range). It never said which attribute the rule checks or what the bounds are."),
            ("fr", "Type to confirm prompt",
             "Veuillez entrer {{val}} pour confirmer :",
             "Veuillez entrer {val} pour confirmer :",
             "The code fills {val}. With double braces the French prompt never showed the value the user has to type."),
            ("ptPT", "Delete variant warning",
             "Tens a certeza que queres eliminar esta variante?",
             "Estás prestes a eliminar a variante {{title}}. Esta ação não pode ser anulada.",
             "The warning now names the variant that is about to be deleted, like the English one does."),
        ],
    },
    {
        "name": "Strapi", "repo": "strapi/strapi", "pr": 27908,
        "app": "Admin panel and plugins, react-intl (ICU)",
        "found": 326, "locales": 32, "locales_note": "Across the admin, content manager, upload, i18n and users-permissions packages.",
        "kinds": [("dropped", 168), ("renamed", 93), ("broken", 58), ("mixed", 6), ("extra", 1)],
        "fixed": 68, "fixed_locales": 19,
        "fixed_note": "134 findings left out because other open PRs already edit those keys, and 124 sit on keys no code uses any more. Of the 68 old strings, 40 made intl-messageformat throw with the values the code passes, so the admin fell back to English. Another 26 rendered without the value.",
        "examples": [
            ("hi", "Delete component label",
             "{नाम} हटाएं",
             "{name} हटाएं",
             "The argument name itself was translated into Hindi, so the code's {name} value had nowhere to go."),
            ("eu", "Settings page title",
             "Konfigurazioa - {name}}",
             "Konfigurazioa - {name}",
             "One stray closing brace and the whole message stops parsing."),
            ("pl", "i18n plugin, delete locale action",
             "Usuń",
             "Usuń język {name}",
             "The Polish action label said only \"Delete\". It now says which locale gets deleted."),
        ],
    },
    {
        "name": "OpenMetadata", "repo": "open-metadata/OpenMetadata", "pr": 34584,
        "app": "Web UI, i18next",
        "found": 174, "locales": 18, "locales_note": "Every translated UI locale had at least one.",
        "kinds": [("dropped", 123), ("extra", 39), ("renamed", 10), ("broken", 1), ("mixed", 1)],
        "fixed": 152, "fixed_locales": 18,
        "fixed_note": "22 left out because two other open PRs (#34084, #33416) edit the same keys. The project's CI only runs after a maintainer adds the safe to test label, so most checks show as failed until then.",
        "examples": [
            ("es-es", "Change domain warning",
             "Cambiar el dominio moverá _ 0 _ activos) del dominio actual a _1 __.¿Quieres continuar?",
             "Cambiar el dominio moverá {{count}} activo(s) del dominio actual a {{domain}}. ¿Quieres continuar?",
             "Machine translation mangled both placeholders. Spanish users were asked to confirm a move without seeing how many assets or which domain."),
            ("es-es", "Copy action",
             "Copiar URL",
             "Copiar {{item}}",
             "The button said \"Copy URL\" whatever it was copying."),
            ("ar-sa", "Uninstall app message",
             "ستؤدي إزالة تثبيت تطبيق {{app}} هذا إلى إزالته من OpenMetaData",
             "ستؤدي إزالة تثبيت تطبيق {{app}} هذا إلى إزالته من {{brandName}}",
             "The product name was typed in by hand where the code passes {{brandName}}, so this string ignores the brand setting."),
        ],
    },
    {
        "name": "ToolJet", "repo": "ToolJet/ToolJet", "pr": 18211,
        "app": "Frontend, i18next, white-label support",
        "found": 57, "locales": 8, "locales_note": "de, es, fr, id, it, ru, uk, zh.",
        "kinds": [("dropped", 57)],
        "fixed": 57, "fixed_locales": 8,
        "fixed_note": "46 of the 57 dropped {{whiteLabelText}}, and 44 of those printed \"ToolJet\" instead, on the login, sign-up, verification, Slack and Google Sheets screens. The other 11 dropped {{appName}}, {{version}} or {{componentName}}.",
        "examples": [
            ("es", "Sign-up page",
             "¿Nuevo en ToolJet?",
             "¿Nuevo en {{whiteLabelText}}?",
             "A white-label customer's Spanish users saw the vendor's brand instead of the customer's."),
            ("de", "Slack connection help",
             "ToolJet kann eine Verbindung zu Slack herstellen und Benutzer auflisten, Nachrichten senden, usw. Bitte wählen Sie entsprechende Berechtigungsbereiche.",
             "{{whiteLabelText}} kann eine Verbindung zu Slack herstellen und Benutzer auflisten, Nachrichten senden, usw. Bitte wählen Sie entsprechende Berechtigungsbereiche.",
             "Same brand leak, in German, on a setup screen."),
            ("de", "Delete app confirmation",
             "Die App und die zugehörigen Daten werden endgültig gelöscht. Möchten Sie fortfahren?",
             "Die App {{appName}} und die zugehörigen Daten werden endgültig gelöscht. Möchten Sie fortfahren?",
             "A permanent delete prompt that did not say which app."),
        ],
    },
    {
        "name": "OpenAEV", "repo": "OpenAEV-Platform/openaev", "pr": 8258,
        "app": "Frontend, react-intl (ICU)",
        "found": 4, "locales": 3, "locales_note": "ja, ko and zh. Separately, one key mismatch kept the lessons learned email in English in all 8 translated languages.",
        "kinds": [("dropped", 1), ("renamed", 1), ("broken", 1), ("extra", 1)],
        "fixed": 13, "fixed_locales": 9,
        "fixed_note": "13 lines in 9 language files: the 4 placeholder bugs, the email key in every file, and an unclosed <a/> tag in it and ja. Commits are signed, as the repo requires.",
        "examples": [
            ("zh", "Launch atomic testing dialog",
             "你想启动这个原子测试吗: {truc}?",
             "你想启动这个原子测试吗: {title}?",
             "\"truc\" is French for \"thing\". The Chinese dialog showed an empty value where the test title belongs."),
            ("ko", "Getting started, test more scenarios",
             "에서 더 많은 시나리오를 테스트하세요 !",
             "{xtmHubLink}에서 더 많은 시나리오를 테스트하세요 !",
             "The link to XTM Hub was gone, so the sentence started with a dangling particle."),
            ("all 9", "Lessons learned email key",
             "<a href='${lessons_uri}'>",
             "<a href=\"${lessons_uri}\">",
             "The code asks for the key with double quotes, the language files stored it with single quotes. The lookup never matched, so the email went out in English in every language."),
        ],
    },
    {
        "name": "Infisical", "repo": "Infisical/infisical", "pr": 8419,
        "app": "Frontend, i18next",
        "found": 4, "locales": 2, "locales_note": "ko and pt-BR. The other 3 translated locales were clean.",
        "kinds": [("markup", 4)],
        "fixed": 4, "fixed_locales": 2,
        "fixed_note": "Checked by calling t() in i18next before and after. Only the ko and pt-BR output changed.",
        "examples": [
            ("ko", "Email verification and MFA step",
             "<email>{{email}}</email><wrapper>로 인증 메일을 전송하였습니다</wrapper><email>{{email}}</email>",
             "다음 주소로 인증 메일을 전송하였습니다",
             "Korean users saw raw tags and an unfilled {{email}} above the code field, at sign-up and at every email MFA login."),
            ("pt-BR", "Email verification and MFA step",
             "<wrapper>Enviamos um e-mail de verificação para</wrapper><email>{{email}}</email>",
             "Enviamos um e-mail de verificação para",
             "Same leftover markup from an older layout, in Brazilian Portuguese."),
        ],
    },
]

# Repos audited where translations come from a translation management system.
# Fixes there belong in the TMS, so no PR was opened.
TMS = [
    ("calcom/cal.diy", "Lingo.dev", 213, 39, "Fix branch with 30 fixes is pushed. The PR is not open yet, because the account has 5 other open PRs there."),
    ("formbricks/formbricks", "Lingo.dev", 45, 13, "The repo's AGENTS.md says not to edit non en-US locales by hand."),
    ("RocketChat/Rocket.Chat", "LingoHub", 44, 33, "Mostly %s and __x__ placeholders."),
    ("twentyhq/twenty", "Crowdin", 11, 6, "Includes an Italian ICU quote that makes {x} render literally."),
    ("baptisteArno/typebot.io", "Tolgee", 4, 2, ""),
]


def e(s):
    return html.escape(str(s), quote=True)


def pr_state(repo, n):
    r = subprocess.run(["gh", "pr", "view", str(n), "-R", repo, "--json",
                        "state,mergedAt,closedAt,url,title"],
                       capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def state_badge(p):
    if p["state"] == "MERGED":
        d = dt.date.fromisoformat(p["mergedAt"][:10]).strftime("%-d %b %Y")
        return f'<span class="st st-merged">Merged {d}</span>'
    if p["state"] == "CLOSED":
        return '<span class="st st-closed">Closed, not merged</span>'
    return '<span class="st st-open">Open, waiting for review</span>'


def render():
    now = dt.datetime.now(dt.timezone.utc)
    gen = now.strftime("%-d %b %Y, %H:%M UTC")
    live = {r["repo"]: pr_state(r["repo"], r["pr"]) for r in REPOS}
    found = sum(r["found"] for r in REPOS)
    fixed = sum(r["fixed"] for r in REPOS)
    merged = sum(1 for p in live.values() if p["state"] == "MERGED")
    open_ = sum(1 for p in live.values() if p["state"] == "OPEN")
    tms_found = sum(t[2] for t in TMS)

    cards = []
    for r in REPOS:
        p = live[r["repo"]]
        kinds = "".join(f"<li><b>{n}</b> {e(K[k])}</li>" for k, n in r["kinds"])
        ex = []
        for loc, where, before, after, why in r["examples"]:
            rtl = ' dir="rtl"' if loc.startswith("ar") else ""
            ex.append(
                f'<div class="ex"><p class="ex-h"><span class="loc">{e(loc)}</span> {e(where)}</p>'
                f'<p class="ba"><span class="lbl lbl-b">Before</span><code{rtl}>{e(before)}</code></p>'
                f'<p class="ba"><span class="lbl lbl-a">After</span><code{rtl}>{e(after)}</code></p>'
                f'<p class="why">{e(why)}</p></div>')
        cards.append(f"""
<section class="repo-card" id="{e(r['name'].lower())}">
<header><h3>{e(r['name'])}</h3>{state_badge(p)}</header>
<p class="muted">{e(r['app'])}. <a href="{e(p['url'])}">{e(r['repo'])}#{r['pr']}</a></p>
<div class="nums">
<div><b>{r['found']}</b><span>broken strings found</span></div>
<div><b>{r['locales']}</b><span>locales affected</span></div>
<div><b>{r['fixed']}</b><span>strings changed in the PR</span></div>
</div>
<ul class="kinds">{kinds}</ul>
<p class="muted">{e(r['locales_note'])} {e(r['fixed_note'])}</p>
{''.join(ex)}
</section>""")

    tms_rows = "".join(
        f'<tr><td><a href="https://github.com/{e(t[0])}">{e(t[0])}</a></td><td>{e(t[1])}</td>'
        f'<td>{t[2]}</td><td>{t[3]}</td><td>{e(t[4])}</td></tr>' for t in TMS)

    mail = f"mailto:{EMAIL}?subject=i18n%20audit%20for%20%3Crepo%3E"
    return TEMPLATE.format(
        price=PRICE, maxloc=MAX_LOCALES, days=DAYS, found=found, fixed=fixed,
        merged=merged, open=open_, nrepos=len(REPOS), cards="".join(cards),
        tms_rows=tms_rows, tms_found=tms_found, ntms=len(TMS), gen=gen,
        email=EMAIL, mail=mail, owner=OWNER), live


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>i18n audit and fix</title>
<meta name="description" content="A ${price} fixed-price audit of every locale in your app, with a PR that fixes every objective bug. Sample: {found} broken strings found in {nrepos} open-source apps.">
<style>
:root {{
  --bg: #fbfaf7; --fg: #1d1d1b; --muted: #5f5e58; --line: #e3e1da; --card: #ffffff;
  --accent: #1f5f4a; --accent-soft: #e4efe9; --bad: #9a2f22; --bad-soft: #f7e7e3;
  --good: #1f5f4a; --good-soft: #e4efe9; --open: #7a5a12; --open-soft: #f5edd8; --code-bg: #f2f0ea;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --bg: #141513; --fg: #ecebe6; --muted: #a3a29b; --line: #2d2e2a; --card: #1b1c1a;
    --accent: #7fc4a6; --accent-soft: #1f2b26; --bad: #f0a093; --bad-soft: #3a211d;
    --good: #7fc4a6; --good-soft: #1f2b26; --open: #e6c27a; --open-soft: #33291a; --code-bg: #232421;
  }}
}}
:root[data-theme="dark"] {{
  --bg: #141513; --fg: #ecebe6; --muted: #a3a29b; --line: #2d2e2a; --card: #1b1c1a;
  --accent: #7fc4a6; --accent-soft: #1f2b26; --bad: #f0a093; --bad-soft: #3a211d;
  --good: #7fc4a6; --good-soft: #1f2b26; --open: #e6c27a; --open-soft: #33291a; --code-bg: #232421;
}}
* {{ box-sizing: border-box; }}
html {{ -webkit-text-size-adjust: 100%; }}
body {{ margin: 0; background: var(--bg); color: var(--fg);
  font: 17px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
main {{ max-width: 760px; margin: 0 auto; padding: 40px 16px 64px; }}
a {{ color: var(--accent); text-underline-offset: 2px; }}
h1 {{ font-size: clamp(28px, 6vw, 40px); line-height: 1.15; margin: 8px 0 16px; letter-spacing: -0.01em; }}
h2 {{ font-size: 22px; margin: 48px 0 12px; }}
h3 {{ font-size: 19px; margin: 0; }}
p {{ margin: 0 0 14px; }}
code {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 14px; }}
.kicker {{ color: var(--muted); font-size: 15px; }}
.lead {{ font-size: 19px; }}
.muted {{ color: var(--muted); font-size: 15px; }}
.damage {{ list-style: none; padding: 0; margin: 16px 0; }}
.damage li {{ padding: 12px 0 12px 14px; border-left: 3px solid var(--bad); margin-bottom: 10px; background: var(--card); border-radius: 0 8px 8px 0; padding-right: 12px; }}
.damage b {{ display: block; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; margin: 24px 0 8px; }}
.stat {{ background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 12px 14px; }}
.stat b {{ display: block; font-size: 28px; line-height: 1.1; }}
.stat span {{ color: var(--muted); font-size: 14px; line-height: 1.3; display: block; margin-top: 4px; }}
.offer {{ background: var(--card); border: 1px solid var(--accent); border-radius: 12px; padding: 18px; margin-top: 16px; }}
.offer header {{ display: flex; flex-wrap: wrap; justify-content: space-between; gap: 6px 16px; align-items: baseline; margin-bottom: 8px; }}
.price {{ font-size: 24px; font-weight: 700; }}
.price small {{ font-weight: 400; color: var(--muted); font-size: 14px; }}
ul.plain {{ padding-left: 20px; margin: 0 0 12px; }}
ul.plain li {{ margin-bottom: 6px; }}
.start {{ background: var(--accent-soft); border-radius: 12px; padding: 20px; margin-top: 16px; }}
.start a.mail {{ font-size: 20px; font-weight: 700; overflow-wrap: anywhere; }}
.repo-card {{ background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 18px; margin: 16px 0; }}
.repo-card header {{ display: flex; flex-wrap: wrap; gap: 8px 12px; align-items: center; justify-content: space-between; margin-bottom: 4px; }}
.st {{ font-size: 13px; border-radius: 999px; padding: 2px 10px; white-space: nowrap; }}
.st-open {{ background: var(--open-soft); color: var(--open); }}
.st-merged {{ background: var(--good-soft); color: var(--good); }}
.st-closed {{ background: var(--bad-soft); color: var(--bad); }}
.nums {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin: 12px 0; }}
.nums div {{ border: 1px solid var(--line); border-radius: 8px; padding: 8px 10px; }}
.nums b {{ display: block; font-size: 22px; line-height: 1.1; }}
.nums span {{ font-size: 13px; color: var(--muted); line-height: 1.25; display: block; margin-top: 2px; }}
.kinds {{ list-style: none; padding: 0; margin: 0 0 12px; display: flex; flex-wrap: wrap; gap: 6px; }}
.kinds li {{ font-size: 13px; border: 1px solid var(--line); border-radius: 6px; padding: 2px 8px; }}
.ex {{ border-top: 1px solid var(--line); padding-top: 12px; margin-top: 12px; }}
.ex-h {{ font-weight: 600; margin-bottom: 6px; font-size: 15px; }}
.loc {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 13px; background: var(--code-bg); border-radius: 4px; padding: 1px 6px; margin-right: 4px; font-weight: 400; }}
.ba {{ display: flex; gap: 8px; align-items: flex-start; margin-bottom: 6px; }}
.ba code {{ flex: 1; min-width: 0; background: var(--code-bg); border-radius: 6px; padding: 6px 8px; overflow-wrap: anywhere; white-space: pre-wrap; display: block; }}
.lbl {{ font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; width: 52px; flex: none; padding-top: 7px; color: var(--muted); }}
.lbl-b {{ color: var(--bad); }} .lbl-a {{ color: var(--good); }}
.why {{ font-size: 15px; color: var(--muted); margin: 4px 0 0; }}
.table-wrap {{ overflow-x: auto; }}
table {{ border-collapse: collapse; width: 100%; font-size: 14px; }}
th, td {{ text-align: left; vertical-align: top; padding: 8px 8px 8px 0; border-bottom: 1px solid var(--line); }}
th {{ color: var(--muted); font-weight: 600; }}
td:first-child {{ overflow-wrap: anywhere; }}
footer {{ margin-top: 56px; padding-top: 16px; border-top: 1px solid var(--line); color: var(--muted); font-size: 14px; }}
@media (max-width: 520px) {{
  .tms td:nth-child(5), .tms th:nth-child(5) {{ display: none; }}
  .nums b {{ font-size: 19px; }}
}}
</style>
</head>
<body>
<main>
<p class="kicker"><a href="../">OSS maintenance</a> by Michael, <a href="https://github.com/{owner}">github.com/{owner}</a>, works in writing</p>
<h1>Your translated app is showing customers broken text</h1>
<p class="lead">I check every locale file in your app against the source language, then send one PR that fixes every objective bug. ${price} fixed, one repo, written report in {days} business days.</p>
<p>Translations break quietly. Few teams can read most of their own locales, tests run in English, and the bug only shows up on a customer's screen. In {nrepos} open-source apps that companies ship to their own customers, I found these this week.</p>
<ul class="damage">
<li><b>White-label customers saw the vendor's name.</b> In ToolJet, 46 strings in 8 languages lost the white-label name, and 44 of them printed "ToolJet" instead on the login, sign-up, Slack and Google Sheets screens.</li>
<li><b>A price rule with no numbers.</b> Medusa's Spanish admin summarized a shipping price rule as "Rango" (range), without the attribute or the bounds.</li>
<li><b>Whole screens falling back to English.</b> In Strapi, 40 of the 68 strings I fixed made the message formatter throw, so the admin showed English instead.</li>
<li><b>Emails that never got translated.</b> OpenAEV's lessons learned email went out in English in all 8 translated languages, because the key in the language files did not match the one the code asks for.</li>
<li><b>Raw markup on a login screen.</b> Infisical's Korean and Brazilian Portuguese users saw <code>&lt;email&gt;{{{{email}}}}&lt;/email&gt;&lt;wrapper&gt;</code> above the verification code field.</li>
<li><b>Placeholders mangled by machine translation.</b> OpenMetadata's Spanish domain change warning read "moverá _ 0 _ activos) del dominio actual a _1 __."</li>
</ul>
<div class="stats">
<div class="stat"><b>{found}</b><span>broken strings found in {nrepos} apps</span></div>
<div class="stat"><b>{fixed}</b><span>strings changed in {nrepos} PRs</span></div>
<div class="stat"><b>{open}</b><span>of those PRs open, waiting for review</span></div>
<div class="stat"><b>{merged}</b><span>merged so far</span></div>
</div>
<p class="muted">PR states are read live from GitHub each time this page is built. Last built {gen}. The full sample report is <a href="#sample">further down</a>.</p>

<h2>What the audit checks</h2>
<p>Every string in every locale, compared with the same key in your source language.</p>
<ul class="plain">
<li>Placeholders that were dropped, renamed, translated or added: <code>{{{{name}}}}</code>, <code>{{name}}</code>, <code>%{{name}}</code>, <code>%s</code>, <code>${{name}}</code>.</li>
<li>ICU messages: plural and select keywords that got translated, braces that don't balance, and whether each message parses and formats with the values your code passes.</li>
<li>Rich text and Trans tags like <code>&lt;0&gt;</code>, <code>&lt;b&gt;</code> and <code>&lt;a&gt;</code> that were lost, left unclosed or shown as raw text.</li>
<li>Brand names typed into a translation where your code passes a variable. That's the white-label leak.</li>
<li>Keys your code asks for that the locale files don't match, and findings on keys no code uses any more. Those dead keys are listed, not fixed blindly.</li>
</ul>
<p class="muted">The string checks run by script on every locale. Each finding is then checked by hand against the code that calls it, so the PR only changes what users actually see.</p>

<h2>What you get</h2>
<ul class="plain">
<li>A written report. Every finding with locale, key, the current text, the fixed text and what the user sees today.</li>
<li>One PR that fixes every objective bug: placeholders, syntax, tags and brand leaks. Wording only changes where a value has to fit into the sentence.</li>
<li>Checked with your repo's own tooling (lint, translation validator, JSON parse) and a render test that formats every changed string with real values before and after.</li>
<li>If your translations live in a TMS like Crowdin, Lokalise, Lingo.dev or Tolgee, you get the fixes as a file to import there instead of a PR, since edits to the repo would be overwritten.</li>
</ul>

<h2>Price and terms</h2>
<div class="offer">
<header><h3>i18n audit and fix</h3><span class="price">${price} <small>fixed price, one repo</small></span></header>
<ul class="plain">
<li>One app's locale files in one repo, up to {maxloc} locales.</li>
<li>Report and PR within {days} business days after I can read the repo.</li>
<li>A public repo needs only the link. A private one needs a read invite on GitHub. No production access, deploy rights or secrets.</li>
<li>Everything happens in writing, by email and in the PR. I don't do calls.</li>
<li>Billed by invoice, in USD.</li>
</ul>
<p class="muted">Not included: native-speaker review, translating keys that are missing entirely, and new languages. Keeping locales filled after every release is the <a href="../#offer">$750 a month locale upkeep</a> on the main page.</p>
</div>

<h2>For agencies</h2>
<p>If you build Medusa, Strapi or similar stores and admin apps for clients, I can run this audit on a client's repo as white-label capacity. The report can go out under your agency's name, and the PR goes to the client repo for your team to review. Framework upgrades and ongoing locale work are on the <a href="../#offer">main page</a>.</p>

<h2>To start</h2>
<div class="start">
<p>Email me the repo link. If it's private, say so and I'll send the GitHub username to invite. I reply in writing within 24 hours.</p>
<p><a class="mail" href="{mail}">{email}</a></p>
</div>

<h2 id="sample">Sample report</h2>
<p>The same audit, run on {nrepos} public apps on 3 Oct 2026. "Broken strings found" counts one string in one locale. Every before and after below is quoted from the PR diff.</p>
{cards}

<h3 style="margin-top:32px">Audited without a PR, because translations come from a TMS</h3>
<p class="muted">These {ntms} repos had {tms_found} broken strings between them. Their translations are synced from a translation management system, so a repo edit would be overwritten. A client in this situation gets the fix file for the TMS instead.</p>
<div class="table-wrap">
<table class="tms">
<thead><tr><th>Repo</th><th>TMS</th><th>Found</th><th>Locales</th><th>Note</th></tr></thead>
<tbody>{tms_rows}</tbody>
</table>
</div>

<h2>To be clear</h2>
<p>None of these projects paid for this work or asked for it. The PRs were opened as normal public contributions, and listing them here doesn't mean their maintainers endorse this offer. {open} of the {nrepos} PRs are still open, and {merged} are merged so far. I have no paying audit clients yet, so there are no testimonials. The PRs above are the evidence.</p>

<footer>
<p>Built by <a href="https://github.com/{owner}/oss-maintenance/blob/main/build_audit.py">build_audit.py</a>. Finding counts are from the audit run on 3 Oct 2026. PR states are live from GitHub as of {gen}.</p>
<p><a href="../">Back to the main page</a> &middot; <a href="https://github.com/{owner}">github.com/{owner}</a></p>
</footer>
</main>
</body>
</html>
"""


def main():
    page, live = render()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page)
    states = {k: v["state"] for k, v in live.items()}
    print(f"i18n-audit: {sum(r['found'] for r in REPOS)} found, "
          f"{sum(r['fixed'] for r in REPOS)} fixed, PR states {states}")


if __name__ == "__main__":
    main()
