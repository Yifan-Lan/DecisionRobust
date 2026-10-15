# Data construction and future attack-code release

The published suites are curated challenges, not a random sample of all generated candidates. The construction stages were candidate generation, validity review, multi-model selection, scenario coverage adjustment and versioned export. Semantic adversarial examples additionally underwent human semantic review; image subsets had their applicable readability reviews. The specific policies differ by suite; see the pinned HF [selection](https://huggingface.co/datasets/yflantmy/DecisionRobust/blob/8b6bac5de7ed66842b6c0c86c87f0944f6cf83b6/docs/selection.md) and [composition](https://huggingface.co/datasets/yflantmy/DecisionRobust/blob/8b6bac5de7ed66842b6c0c86c87f0944f6cf83b6/docs/composition.md) documentation.

Do not infer that every suite used an identical verifier, threshold or cap. Original selection membership was based on historical model failure outcomes; later reporting of injection Target ASR did not reselect that membership. Original questions can contribute multiple candidate scoring items. Model-selection bias must be disclosed when reporting results.

The experiment-specific attack runners and historical human-review tools are **not included in this first code release**. Their extraction requires checking frozen edit-region adapters, search budgets, stopping criteria, dependency licenses and provenance. No placeholder `attacks` package is presented as a working implementation. The evaluation interface already accepts the final public candidates.

Future attack-code release scope includes the final text attack implementations and S2/S3 generation settings, fixed injection construction, image perturbation/overlay generation, validity-review interfaces and audited export tools. Historical credentials, account pools, private paths, drafts and unreviewed vendor code will not be copied with them.

For community examples, external model validation is not required. Contributors explain label consistency and applicable semantic preservation/readability, provide paired success evidence on at least two models, and maintainers review each submission. See [the contribution guide](example-submissions.md).
