# Model results update — 2026-10-26

Added **five configurations**, bringing coverage to **61 text / 39 image configurations**. Each new row covers all **1,058 curated candidates** (1,585 unique complete clean/adv requests), with zero invalid or excluded pairs. None of these checkpoints was used to select the benchmark examples. This is a results-only update: data, labels, images and membership are unchanged; no full-pool model results are added.

## Results

ASR is conditional on valid clean-correct candidate pairs, counting attack candidates separately. Text adversarial and image perturbation use **Flip ASR**; the three injection suites use **Target ASR**. Lower is better. Fractions show successes / clean-correct candidates. The leaderboard also reports clean accuracy and coverage.

| Model / setting | Text adversarial — Flip ASR | Text injection — Target ASR | Image perturbation — Flip ASR | Image overlay — Target ASR | Image instruction — Target ASR |
|---|---:|---:|---:|---:|---:|
| Perplexity Decider Flash v1.2-4B | 24.19% (30/124) | 35.09% (113/322) | 34.25% (62/181) | 19.32% (40/207) | 7.87% (7/89) |
| d3-turbo-27B | 12.98% (17/131) | 39.03% (137/351) | 1.55% (3/193) | 8.70% (18/207) | 17.31% (18/104) |
| Perplexity Decider v1.2-27B | 14.50% (19/131) | 76.40% (272/356) | 2.07% (4/193) | 39.13% (81/207) | 40.40% (40/99) |
| OneJev1.6-27B | 29.06% (34/117) | 53.00% (168/317) | 2.91% (5/172) | 36.95% (75/203) | 24.72% (22/89) |
| StartLux Decision v1.1-27B Instant | 18.18% (24/132) | 54.86% (192/350) | 4.04% (8/198) | 19.14% (40/209) | 34.62% (36/104) |

## Versions and inference settings

- **d3-turbo-27B** is a separate checkpoint from the existing d3-27B row. Native BF16 inference, batch size 1, state-once enabled, permutation averaging disabled.
- **Perplexity Decider v1.2-27B** and **Flash v1.2-4B** are separate from the existing v1.1-27B row. Native BF16 inference with checkpoint calibration (temperatures 1.3823494678 and 1.5539092221 respectively), `fast=false`, complete joint requests, native context/image limits.
- **OneJev1.6-27B** is separate from the earlier OneJev checkpoints. Native BF16 Flide runtime, `debias=1`, token batching budget 8192, CUDA graph capture disabled and session cache disabled. The batching budget does not truncate the input.
- **StartLux Decision v1.1-27B Instant** is a different checkpoint from **AutoThink-27B**, including AutoThink with `think_mode=never`. Local BF16 inference with bidirectional prompt attention and `think_mode=never`, `none_check=true`, `allow_none=false`. Gate 0.6, budget 4096 and mix 0.75 are recorded defaults; no reasoning is invoked in this mode. The same checkpoint/runtime was evaluated privately on October 16: 1,574 exact complete-request and image-hash matches were reused, and 11 updated requests were evaluated on October 26. This row is newly published, not a new full rerun.

All requests retain native questions, including those without GT; only `task.question_ids` are scored. Original image bytes are passed to upstream preprocessing. No additional image resizing or quantization is applied. Four new models use Torch 2.14.0 / Transformers 5.17.0; StartLux retains Torch 2.13.0 / Transformers 5.8.1. Fixed checkpoint commits and runtime settings are recorded in [model_details.json](https://huggingface.co/datasets/yflantmy/DecisionRobust/blob/main/results/model_details.json).

## Data version and comparisons

These five rows use **v1.3.0 curated**, including six GUI text-injection inputs with portable page identifiers. Older rows retain their historical **v1.2.0** scope and were not rerun. All other curated inputs are unchanged. Differences between old and new rows on text injection may therefore also reflect these six changed inputs; they are not a controlled checkpoint-only comparison. See [evaluation scope](https://huggingface.co/datasets/yflantmy/DecisionRobust/blob/main/results/evaluation_scope.json).

[Primary aggregates](https://huggingface.co/datasets/yflantmy/DecisionRobust/blob/main/results/asr.json) · [Flip comparison](https://huggingface.co/datasets/yflantmy/DecisionRobust/blob/main/results/flip_asr.json) · [Source/scenario/attack/mode breakdowns](https://huggingface.co/datasets/yflantmy/DecisionRobust/blob/main/results/additional_20261026_by_group.json)
