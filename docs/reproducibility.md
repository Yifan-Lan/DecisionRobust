# Reproducibility and release scope

This first portable code release covers data loading, scoring, evaluation orchestration, reviewed model transports, offline tests, website generation and contribution review. It does not claim to reproduce every historical attack or inference environment with one command.

## Frozen references

`site_config.json` and the installed package's `release.json` pin the same dataset, data revision, results revision and citation revision. Data and results revisions are separate because result coverage can change without changing dataset membership. Tests check that the two pins agree.

The loader checks file hashes against the release manifests. A local release directory is explicitly trusted as a user-supplied snapshot; its manifest is not cryptographically signed. Keep the original version/revision information when copying it.

`results/published_asr.json` is a copy of the pinned public aggregate, not new measurements. `results/model_catalog.json` contains public checkpoint references extracted from the pinned model metadata. The manifest records their hashes. Full normalized inference outputs are created only in ignored local run directories. Historical private logs are not distributed here.

Resume binds the release, selected full records (including GT), exact image content, model configuration, package source hashes, adapter source and recorded runtime versions. A model revision supplied in a config is declarative; users must ensure their local checkpoint really matches it. API providers can change a model behind an alias. Returned identities are preserved when available, but are not an immutable provider-side weight pin.

## Known historical differences

Historical evaluations include different native/adapted prompts and vision preprocessing. Some optimized-image measurements used pre-PNG float tensors, whereas the public release contains saved PNGs; a new saved-image evaluation is not automatically a bitwise reproduction of those historical values. Some upstream revisions were incompletely recorded. These limitations remain documented in the public evaluation notes and must not be hidden by repackaging the code.

The portable runner always reads the distributed image bytes without modifying them. Model-native preprocessing happens only inside an explicitly chosen adapter and must be disclosed. There is no task-conditioned calibration or GT-aware readout in the included evaluation transports.

## Checks before a code release

```bash
python -m unittest discover -s tests -v
python scripts/test_submissions.py
python examples/offline_demo.py --output runs/offline-demo
python scripts/audit_public_tree.py
```

Rebuild the website with `python scripts/build_site.py` to check the pinned public manifests and metric bounds. This fetches public metadata and JSONL, not model weights. Use `--release-dir` only for a full published HF snapshot, not the evaluation-only snapshot created by `decisionrobust download`. See [website development](website.md) for the required files.

`scripts/package_public.py` packages only explicitly reviewed file paths whose hashes match the supplied manifest. It excludes Git history by construction. Generate and review the manifest outside the repository after testing. Without Git metadata, the disclosure scanner omits generated directories such as caches, virtual environments and run outputs, while still flagging unexpected credential files in the source tree. An explicit packaging manifest is checked strictly, including any prohibited paths it names. The scanner reports locations/categories without echoing matched values; automated scans supplement manual inspection and do not prove absence of sensitive content.
