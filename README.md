# oss-maintenance

Source for https://theluckystrike.github.io/oss-maintenance/

The page lists my merged PRs in other people's public repos and describes a flat monthly maintenance offer. `build.py` regenerates `docs/index.html` and `docs/data.json` from live GitHub search data.

```
python3 build.py
git add docs && git commit -m "Refresh merged PR data" && git push
```

Needs the `gh` CLI, logged in. Contact lipmichal@gmail.com, in writing.
