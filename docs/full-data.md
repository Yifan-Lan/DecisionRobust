# Full data release — v1.3.0

The Hugging Face repository now provides `_full` alongside `_curated` for each of the five suites. All use a `test` split. Curated remains the default for the evaluation CLI, website explorer and leaderboard.

| Suite | Curated | Full |
|---|---:|---:|
| Text adversarial | 141 | 3,713 |
| Text injection | 374 | 9,716 |
| Image perturbation | 200 | 759 |
| Image overlay | 223 | 4,362 |
| Image instruction | 120 | 640 |
| Total | 1,058 | 19,190 |

Full includes every curated record verbatim, with matching IDs; do not concatenate the editions. The full pool has 1,048 distinct original questions (curated: 441). Full retains historical quality gates and human exclusions without the extra curated success-count thresholds, balancing or per-original caps. Most full additions have not received the extra curated human review. Neither edition is an unbiased estimate of real-world error rates.

```python
from datasets import load_dataset
full = load_dataset("yflantmy/DecisionRobust", "text_adversarial_full", split="test")
```

Full uses the same nine native fields. Keep the complete request and score only `task.question_ids`. For the precise gates, overlay verification exception, native JSONL, embedded images and injection target locations, see the [dataset documentation](https://huggingface.co/datasets/yflantmy/DecisionRobust/blob/main/docs/full.md).

68 full GUI records, including 6 curated text-injection records, now use a generic page identifier. New candidate IDs identify changed input; original IDs remain stable. Labels, options, payloads and image bytes are unchanged. See the [ID mapping](https://huggingface.co/datasets/yflantmy/DecisionRobust/blob/main/metadata/gui_id_migration_v1_3_0.json).

No full performance or new inference is included. Published aggregate results retain their v1.2.0 evaluations; the six modified curated inputs have not been re-evaluated. The current evaluation CLI loads v1.3.0 inputs, so future submissions should report the pinned revision and may differ from these historical scores. [Evaluation scope](https://huggingface.co/datasets/yflantmy/DecisionRobust/blob/main/results/evaluation_scope.json).
