# Submit a model

Community results are welcome. Submissions are public and remain off the leaderboard until Yifan Lan reviews and approves them. Automatic checks verify formatting and recompute metrics; they do not prove that a model produced the submitted outputs.

## 1. Prepare an evaluation

Use the pinned public release in `site_config.json`. You may submit any supported subset of the five suites. Preserve complete clean and adversarial inputs, including questions without ground truth. Score only `task.question_ids`. Disclose any necessary adapter or image transformation, model/checkpoint version, quantization, inference settings, and whether this benchmark was used for training, tuning, prompt selection, or checkpoint selection.

Clone this repository, then create the result skeleton (Python 3.10+, standard library only):

```bash
python scripts/build_site.py
python scripts/prepare_submission.py your-model-version --configs text_adversarial_curated text_injection_curated
```

This creates `submissions/entries/your-model-version/manifest.json` and `predictions.jsonl`. Fill in the manifest, including a public model link and a versioned evaluation-code URL. Use a unique model ID; community submissions cannot overwrite existing model IDs.

Run your model on every clean/adv request in your chosen suites. The request files are in the public dataset; `website/data/samples/<id>.json` also preserves their native JSON. Image paths resolve relative to `raw/<config>/` in the pinned dataset, not relative to the submission folder. Retain all questions when evaluating, even though only designated questions are scored.

If you use the included evaluation CLI, run a complete evaluation of your claimed suites and copy its `predictions.jsonl` into the generated submission directory. A `--limit` smoke run does not satisfy the full-suite submission requirement. Fill in the generated model/evaluator metadata and disclosures yourself; the evaluation CLI does not create an approval or a complete submission manifest.

## 2. Record outputs

One JSONL line represents one `(config, id)` candidate with both clean and adv outputs. Every candidate in each claimed suite needs a line. Replace every generated `pending` status with `ok`, `unsupported`, or `error`.

```json
{
  "config": "text_adversarial_curated",
  "id": 469,
  "clean": {
    "request_sha256": "COPY_THE_GENERATED_CLEAN_HASH",
    "status": "ok",
    "answers": {"q": {"choice": "negative"}}
  },
  "adv": {
    "request_sha256": "COPY_THE_GENERATED_ADV_HASH",
    "status": "ok",
    "answers": {"q": {"choice": "positive"}}
  }
}
```

This is an illustrative output, not a measured model result. Actual files contain one compact JSON object per line. The generated hashes bind outputs to the canonical complete dataset requests, not to model-specific transport wrappers; they do not prove the requests were actually sent. Explain transport/adapter changes in the manifest and retain raw model receipts for review.

Output fields under each question ID:

| Type | Required output | Optional native distribution |
|---|---|---|
| Choice | `{"choice": "option_key"}` using the native returned label | `probabilities`, with all option keys |
| Noul | `{"noul": 0.73}` for each scored predicate | Use the affirmative probability for each predicate |
| Score | `{"score": 1.42}` on the question's zero-based scale | `probabilities`, with string indices `"0"`, `"1"`, etc. |

Include native probability distributions whenever available. Score must be the probability-weighted value, not the most likely level or a rounded value. Native Choice remains authoritative even if its probability is not maximal. Multi-predicate Noul probabilities are normalized by the official scorer. Score uses the published ±0.5 tolerance.

For a failure or unsupported case, retain `request_sha256`, set the status, and provide a nonempty `reason`. These pairs are excluded explicitly and reduce coverage; they are not model successes or attack successes. A suite with zero valid pairs cannot be submitted. A suite with no clean-correct denominator displays an undefined ASR rather than zero.

Local validation:

```bash
python scripts/validate_submission.py submissions/entries/your-model-version --output /tmp/submission-check.json
```

The validator checks versions, IDs, full request hashes, scored outputs, ranges, distributions, duplicates and coverage. It recomputes candidate-level Flip ASR for text adversarial/image perturbation and Target ASR for injection. Both use valid clean-correct pairs as the denominator. Invalid `ok` outputs fail validation; represent genuine model/API failures explicitly as `error`. Raw responses and extra evidence may be linked from the issue; do not include credentials, model weights, executables or images in the result files. Each JSON/JSONL file is limited to 16 MiB.

## 3. Request review

Open [a model submission issue](https://github.com/Yifan-Lan/DecisionRobust/issues/new?template=model_submission.yml), and link a PR adding only your two result files under `submissions/entries/<submission-id>/`. Alternatively link publicly downloadable files in the issue; the maintainer can stage them in a PR. **Automatic checks run on a results PR, not merely on a pasted URL in an issue.**

PR checks use the trusted base-branch scorer and fetch JSON blobs only; they never execute submitted evaluation code. The report appears under the PR's **Validate model submission** workflow as a `submission-checks` artifact. A passing check means the submission is ready for human inspection, not accepted. The maintainer may request original receipts, adapter changes or a rerun. Merely merging an entry does not add it to the leaderboard.

## Maintainer review and publication

1. Inspect model version, dataset exposure, inference settings, exclusions and raw receipts. Reproduce the metric report. Decide whether to rerun a sample or the full evaluation; do not describe receipt-only checks as independently reproduced inference.
2. Record the decision and evidence in the issue/PR. Use `receipt_review`, `sample_rerun`, or `full_rerun` to describe what was actually verified.
3. Add one entry to `submissions/approved.json`, using the **exact two hashes produced by the validator**:

```json
{
  "submission": "your-model-version",
  "reviewer": "Yifan-Lan",
  "reviewed_at": "YYYY-MM-DD",
  "verification": "sample_rerun",
  "review_url": "https://github.com/Yifan-Lan/DecisionRobust/issues/NUMBER",
  "files_sha256": {
    "manifest.json": "SHA256_FROM_VALIDATOR",
    "predictions.jsonl": "SHA256_FROM_VALIDATOR"
  }
}
```

4. Run `python scripts/build_site.py`, review the resulting leaderboard and merge the approval PR. The website rebuild recomputes approved submissions; mismatched hashes stop publication. Pending entries are ignored. There is no automatic approval, merge or publishing credential in the validation workflow.

The leaderboard marks these models **Community · reviewed** and shows the verification scope under model details. Existing benchmark-run results remain **Maintainer-evaluated**. Downloaded result CSVs include approved community results. This workflow does not automatically change the Hugging Face dataset or its published result snapshot.

`CODEOWNERS` names Yifan Lan for the approval registry and validation code. GitHub only enforces required code-owner approval when repository branch/ruleset settings enable it; CODEOWNERS by itself is not branch protection. Repository write access must remain limited to trusted maintainers. Review and merge are manual gates in this first version.
