# Published results

`published_asr.json` preserves the aggregate already published with the pinned results revision. `model_catalog.json` lists 61 model configurations and available public checkpoint bindings. It is a compact index, not an assertion that every model has a standalone adapter in this code release. `manifest.json` binds these files to the release and records their SHA256 values.

Detailed historical model policies and per-source summaries remain in the pinned Hugging Face `results/` directory. New evaluations write to ignored `runs/` directories; they do not overwrite these published reference numbers or publish themselves to the leaderboard.
