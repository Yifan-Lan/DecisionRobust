# Model results update — 2026-10-16

This results-only update adds **26 model/configuration entries** and image evaluations for **JEV-1.13.0**. The release now has **56 text configurations and 34 image configurations**, covering **54 model/version identities**; StartLux contributes three settings of one model. All 1,058 examples, original IDs, GT, images and data version 1.2.0 are unchanged.

## Versions and settings

- Historical **Liquid d1:free** stays in its existing row with its selection flags. The newer **d1** and **d1-ultra** APIs have separate dated rows. Provider weight revisions and parameter sizes are not disclosed.
- **JEV-1.14.0** is separate from **JEV-1.13.0**. Only image results are appended to the latter; its historical text results remain unchanged. JEV parameter size is not disclosed.
- **StartLux AutoThink-27B** is one model evaluated with `think_mode=never`, `auto` or `always`. The three rows use `gate=0.6`, `think_budget=4096`, `mix=0.75`, `none_check=true`, `allow_none=false`. API weight revision is provider-unpinned.
- H2O **Nemotron-Nano-4B** has a different backbone from the existing H2O-Lightning-4B. **SII-Decision-4B-Full** is the current model-card name at the requested InnerJev-4B-Full repository alias; it is separate from the existing 27B checkpoint.
- Model family sizes are shown in row names; Mapika 35B-A3B has 35B total / 3B active parameters. Pinned model revisions and native runtime settings are in [model_details.json](https://huggingface.co/datasets/yflantmy/DecisionRobust/blob/main/results/model_details.json).

## Newly evaluated configurations

| Model / setting | Parameter size | Inference configuration |
|---|---|---|
| JEV-1.14.0 | Not disclosed | API · jev-1.14.0 · 2026-10-16 |
| JEV-1.13.0 | Not disclosed | API · jev-1.13.0 · image evaluation 2026-10-16 |
| Liquid d1 (API, 2026-10-16) | Not disclosed | API · d1 · 2026-10-16 (separate from historical d1:free) |
| Liquid d1-ultra (API) | Not disclosed | API · d1-ultra · 2026-10-16 |
| StartLux AutoThink-27B · never | 27B | API · think_mode=never · gate=0.6 · budget=4096 · mix=0.75 |
| StartLux AutoThink-27B · auto (gate=0.6) | 27B | API · think_mode=auto · gate=0.6 · budget=4096 · mix=0.75 |
| StartLux AutoThink-27B · always | 27B | API · think_mode=always · gate=0.6 · budget=4096 · mix=0.75 |
| d3-27B | 27B | Native calibrated inference · 2026-10-16 |
| d3-flash-9B | 9B | Native calibrated inference · 2026-10-16 |
| d3-mini-4B | 4B | Native calibrated inference · 2026-10-16 |
| d3-nano-2B | 2B | Native calibrated inference · 2026-10-16 |
| Intern-Decision-4B | 4B | Native calibrated inference · 2026-10-16 |
| Intern-Decision-2B | 2B | Native calibrated inference · 2026-10-16 |
| Intern-Decision-0.8B | 0.8B | Native calibrated inference · 2026-10-16 |
| Aplomb-1-5.3B | 5.3B | Native calibrated inference · 2026-10-16 |
| Liquid d1-omni-600M | 600M | FP32 · native text and image token limits · partial coverage |
| Mapika decider-2B-vision | 2B | BF16 · native 10-option limit · partial text coverage |
| GLiNER2.5-Decide-1B | 1B | Native calibrated inference · 2026-10-16 |
| H2O-Lightning-4B-Nemotron-Nano | 4B | BF16 · Nemotron backbone (separate from H2O-Lightning-4B) |
| SII-Decision-4B-Full (InnerJev alias) | 4B | BF16 · SII-Decision-4B-Full (requested InnerJev repository alias) |
| JevK5-4B | 4B | Native calibrated inference · 2026-10-16 |
| KEV-0.8B | 0.8B | Native calibrated inference · 2026-10-16 |
| KEV-4B | 4B | Native calibrated inference · 2026-10-16 |
| Mapika decider-35B-A3B | 35B total / 3B active | BF16 · MoE, 35B total / 3B active · native calibration |
| Mapika decider-4B | 4B | Native calibrated inference · 2026-10-16 |
| Bespoke-Nimble-9B-v3 | 9B | Native calibrated inference · 2026-10-16 |
| Plumb-4B | 4B | Native calibrated inference · 2026-10-16 |

## Scoring and coverage

ASR is conditional on valid clean-correct candidate pairs, counting each attack candidate separately. Text adversarial and image perturbation use **Flip ASR**; the three injection suites use **Target ASR**. The website also reports clean accuracy, coverage, numerator and denominator. Newly evaluated configurations were not used to select these benchmark examples.

| Model | Text adversarial | Text injection | Image instruction |
|---|---:|---:|---:|
| Intern-Decision (0.8B / 2B / 4B) | 137/141 | 363/374 | 120/120 |
| Liquid d1-omni-600M | 110/141 | 311/374 | 119/120 |
| Mapika decider-2B-vision | 122/141 | 340/374 | 120/120 |

These fractions describe valid candidate-pair coverage, not the clean-correct ASR denominator. Unsupported native option counts or text budgets are excluded instead of silently dropping content. All other newly evaluated applicable cells have full coverage. Models with no image evaluation retain a dash.

JEV-1.14 uses native returned labels and scores, including cases where rounded probabilities differ slightly from normalization or the returned weighted score within the documented rounding envelope. Original returned distributions are retained in the experiment receipts. This restores full coverage without changing native answers.

[All primary aggregates](../results/published_asr.json) · [Flip comparison](https://huggingface.co/datasets/yflantmy/DecisionRobust/blob/main/results/flip_asr.json) · [New source/scenario/attack/mode aggregates](https://huggingface.co/datasets/yflantmy/DecisionRobust/blob/main/results/additional_20261016_by_group.json)

Not included in this public update: the optional StartLux gate=0.9 and local Instant experiments. H2O-Lightning-31B and Mapika decider-31B have no published results from this run.
