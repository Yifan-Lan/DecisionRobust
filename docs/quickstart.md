# Evaluate a model

Python 3.10+ is required. The resumable runner currently targets Linux/macOS (POSIX file locking). The core package uses only the standard library. GPU adapters need separate upstream environments; do not install every model runtime into one environment.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python examples/offline_demo.py --output runs/offline-demo
```

The demo uses explicitly synthetic data and invented outputs to exercise the software. It makes no network or model calls. Its output is not a benchmark result.

## Get the published data

```bash
decisionrobust inspect
decisionrobust download --output downloads/release-v1.3.0
```

The loader uses the immutable data/results revisions in `src/decisionrobust/release.json`, checks file SHA256 values against the release manifests, and downloads only native JSONL, referenced original image bytes and the required result metadata. It does not also download Parquet. Use `--suites text_adversarial_curated` to download only one suite, or `--pins your-release.json` for an explicitly different version.

Downloading the complete image release can take time. A local raw snapshot can be used with `--release-dir`. Keep its manifest and `release.json`; when using nondefault pins, pass `--pins` explicitly. The local manifest is a trusted local input, not a signature or proof of provenance. This is an evaluation-only snapshot; it lacks the citation, CSV and dataset-info files used by the website builder. See [website development](website.md) for that separate workflow.

## Run a small real evaluation

Choose an adapter in [model-adapters.md](model-adapters.md). Store credentials in shell environment variables; do not put them in a model config or repository file. `.env.example` contains names only. This package deliberately does not automatically read `.env`.

For a user-managed native decision server:

```bash
mkdir -p runs
cp configs/models/local_server.json runs/my-model-config.json
# Edit the model name and exact revision in runs/my-model-config.json.
export DECISION_ENDPOINT=http://127.0.0.1:8000/systemone
decisionrobust evaluate \
  --release-dir downloads/release-v1.3.0 \
  --model-config runs/my-model-config.json \
  --suites text_adversarial_curated \
  --limit 3 --output runs/my-model-smoke
```

The server must already implement the native state/questions request and answers response; this command does not start a server. For the OpenAI Decisions transport, use `configs/models/openai_decisions.json` and export `OPENAI_API_KEY`. Running an API adapter makes billable calls according to your provider account; tests and the offline demo do not.

For a full evaluation, omit `--limit` and use a new output directory. The limit selects the first N candidates per suite and is recorded in `run.json`. Summary coverage is measured within that selected subset, not against the full published suite; do not present a smoke run as full-suite coverage. HTTP adapters allow `--workers 4 --requests-per-second 2` for shared request-level pacing; the default is one worker and one request per second. JEV SDK and GPU adapters run with one worker. Providers can also enforce question/token limits; the CLI request rate is not a guarantee against those limits.

## Resume and inspect

Repeat exactly the same command and output directory to reuse completed requests. Add `--retry-failed` to retry stored errors; successful outputs are reused. Unsupported cases remain explicitly excluded. A changed model config, software fingerprint, task selection, GT, question, or image content prevents unsafe resume. On interrupted writes, only an unterminated final JSONL record is discarded.

```bash
decisionrobust summarize \
  --release-dir downloads/release-v1.3.0 \
  --output runs/my-model-smoke
```

The summary command uses the run's recorded release, suites and limit; it deliberately does not accept `--pins` or `--suites` overrides. Do not summarize concurrently with a live evaluation.

Outputs:

- `run.json`: release, model/config hash, source-code hash, runtime versions and selected request keys.
- `requests.jsonl`: one final outcome per processed request per invocation, with its attempt count, normalized native answers, returned model identity, usage when supplied and elapsed time. Intermediate failed attempts inside a retry loop are not written as separate receipts. Final failures use error codes, without response bodies or credentials.
- `progress.json`: completed requests, unresolved errors and authentication/balance halt status.
- `predictions.jsonl`: candidate-level clean/adv outputs with canonical request hashes, compatible with the existing submission validator. A stopped run can contain `pending` entries.
- `outcomes.jsonl`: explicit eligibility, success and exclusions per candidate.
- `summary.json`: per-suite and per-source/scenario/attack/mode coverage, accuracy, denominator and ASR.

Multiple candidates can share a cached clean request, but each candidate still contributes separately to the metric denominator. Usage covers the final returned receipts, not provider billing for every failed attempt. No hardcoded dollar prices are included.

## Submit results

Follow [the model submission guide](submissions.md), generate its manifest, and copy your completed `predictions.jsonl` into that submission directory. Fill in model version, inference details, data exposure and evaluator information yourself. The runner stores normalized outputs, not full provider response bodies. If review requires original receipts, retain them separately with an appropriate model integration and remove credentials before sharing. Raw run directories are private working artifacts and are ignored by Git. Submissions undergo maintainer review; running this CLI does not publish anything.
