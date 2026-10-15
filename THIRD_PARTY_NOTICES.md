# Licensing scope and external dependencies

Original code and documentation in this repository are provided under the MIT license in `LICENSE`. This license does not relicense upstream datasets, benchmark images, model weights, third-party inference runtimes or logos.

- Benchmark text/images remain in the Hugging Face release and retain their applicable upstream terms. This source-code package does not copy the full dataset. Consult the dataset's source and licensing information before redistribution.
- Model weights and upstream runtime source are not bundled. Users install/download them separately and follow their respective licenses. `results/model_catalog.json` identifies available public repositories and revisions; a reference is not a grant of redistribution rights.
- The local adapters are project integration code derived from the project's experiments, not copies of vendored model implementations. KEV, Bosun and the JEV SDK still require their upstream dependencies. The full 30-model historical runtime collection is not included.
- The existing Hugging Face brand asset is retained for the dataset link; see `website/assets/brand/README.md`. Its branding/trademark status is independent of the code license.
- The website loads DM Sans and Manrope through Google Fonts; font binaries are not included in this archive. Their upstream licenses continue to apply.

The site retains its existing schematic benchmark overview. This code-release preparation does not revise that figure or make new claims about the example it depicts.
