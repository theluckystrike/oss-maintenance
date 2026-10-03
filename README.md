# oss-maintenance

Source for https://theluckystrike.github.io/oss-maintenance/

The page lists my merged PRs in other people's public repos and describes a flat monthly maintenance offer. `build.py` regenerates `docs/index.html` and `docs/data.json` from live GitHub search data. It also runs `build_audit.py`, which writes `docs/i18n-audit/index.html` (the fixed-price i18n audit and its sample report) with PR states read live from GitHub.

```
python3 build.py
git add docs && git commit -m "Refresh merged PR data" && git push
```

Needs the `gh` CLI, logged in. Contact lipmichal@gmail.com, in writing.
