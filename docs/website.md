# Website development

The static leaderboard and example explorer live in `website/`. For model evaluation, start with the [repository README](../README.md) or [evaluation quickstart](quickstart.md).

## Run locally

Python 3.10+ is sufficient; no frontend dependencies or API credentials are needed.

```bash
python scripts/build_site.py
python -m http.server 8000 --directory website
```

Open http://localhost:8000. The build downloads only public JSON/JSONL, CSV, and citation files from pinned Hugging Face revisions. It verifies source hashes and metric consistency. Images load on demand from the pinned public dataset. The default build fetches its own required files. `--release-dir` requires a full published HF repository snapshot with all suites, `dataset_info.json`, `results/asr.csv`, citation files and their manifest entries; the smaller `decisionrobust download` evaluation snapshot is not sufficient.


## Deployment

In repository **Settings → Pages → Build and deployment**, select **GitHub Actions** as the source. The `Build and deploy website` workflow then builds and publishes `website/` on pushes to `main`, or when run manually from Actions.


## Optional browser checks

Install Playwright in a development environment (`pip install playwright` and `playwright install chromium`), start the local server, and run `python scripts/browser_smoke.py`. The checks cover all populated suite/scenario combinations, sorting and model filtering, image display, shareable URLs, and mobile overflow. Set `SITE_URL` to check a deployed site.


## Interactive charts

- **Ranked bars:** vertical bars place models on the horizontal axis and ASR on the vertical axis. All eligible models are shown by default, with angled model labels. Choose one of the five release datasets, or optionally narrow the display to the 10 or 20 lowest ASRs. Search and manual model selections apply to the chart.
- **Across datasets:** compare ASR or within-dataset rank. Without manual selections, the six lowest-ASR models on the reference dataset form the default comparison. Use **Choose models** or the table checkboxes to customize it.
- **Full coverage only:** excludes partial-coverage evaluations from the chart and its ranking pool. Ranks use all eligible models in each dataset, not just the displayed selection; tied ASRs share a rank. The underlying table always retains coverage details.
- Missing results remain gaps. Hover or keyboard-focus marks for ASR, numerator/denominator, clean accuracy, coverage, and selection status. Export the current plot as SVG.

Run `python scripts/chart_smoke.py` for chart-value, rank, filtering, export, and responsive-layout checks. Chart changes do not alter the pinned dataset or result metrics.


## Website files

- `website/`: HTML, CSS and browser JavaScript.
- `scripts/build_site.py`: builds a static snapshot from pinned public release files.
- `site_config.json`: data, results and citation revision pins. Keep these aligned with the installed package’s `src/decisionrobust/release.json`.
- `.github/workflows/pages.yml`: GitHub Pages deployment.
- `website/data/`: generated files, ignored by Git.

Run commands from the repository root. Rebuilding the website does not run models or change benchmark membership.
