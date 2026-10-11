# DecisionRobust

A benchmark for decision model reliability across text, structured inputs, and images.

- **Website:** https://Yifan-Lan.github.io/DecisionRobust/
- **Dataset and results:** https://huggingface.co/datasets/yflantmy/DecisionRobust

The website provides a sortable leaderboard, model comparison, and clean/attacked example explorer across five curated release sets. Paper and evaluation code are being prepared for release.

## Run locally

Python 3.10+ is sufficient; no frontend dependencies or API credentials are needed.

```bash
python scripts/build_site.py
python -m http.server 8000 --directory website
```

Open http://localhost:8000. The build downloads only public JSON/JSONL, CSV, and citation files from pinned Hugging Face revisions. It verifies source hashes and metric consistency. Images load on demand from the pinned public dataset.

## Deployment

In repository **Settings → Pages → Build and deployment**, select **GitHub Actions** as the source. The `Build and deploy website` workflow then builds and publishes `website/` on pushes to `main`, or when run manually from Actions.

## Structure

- `website/`: HTML, CSS, and browser JavaScript.
- `scripts/build_site.py`: reproducible public-data exporter and validation.
- `site_config.json`: independently pinned data and result revisions.
- `.github/workflows/pages.yml`: GitHub Pages deployment.
- `website/data/`: generated and ignored; the workflow builds it before deployment.

Update the revision pins to publish new results. Do not copy experiment directories, credentials, weights, or private logs into this repository. This repository currently contains the website, not the attack/evaluation implementation.

## Reading results

ASR is successful attacks divided by valid clean-correct candidate pairs. Multiple candidates derived from one original count separately. Accuracy is candidate-weighted on valid pairs. Coverage, exclusions, and selection-model markers are shown beside the results. Missing or unsupported evaluations are not reported as zero.

Keep complete requests, including questions without ground truth; score only `task.question_ids`. These selected challenges are not unbiased estimates of real-world error rates. Historical model adapters differ; consult the [evaluation protocol](https://huggingface.co/datasets/yflantmy/DecisionRobust/blob/main/docs/evaluation.md).

Dataset provenance and licensing are documented in the [dataset card](https://huggingface.co/datasets/yflantmy/DecisionRobust). Upstream datasets retain their respective terms.

## Optional browser checks

Install Playwright in a development environment (`pip install playwright` and `playwright install chromium`), start the local server, and run `python scripts/browser_smoke.py`. The checks cover all populated suite/scenario combinations, sorting and model filtering, image display, shareable URLs, and mobile overflow. Set `SITE_URL` to check a deployed site.
