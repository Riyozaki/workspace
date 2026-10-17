# Provenance / third-party components

## Language-model weights (downloaded, not committed)

- Original model: **HuggingFaceTB/SmolLM2-135M-Instruct**, Apache-2.0.
- Quantized artifact: QuantFactory/SmolLM2-135M-Instruct-GGUF,
  revision `ab810cf68114990406fdf996510dd3d3c6adbdf5`, Q4_1.
- Delivery source: Simon Willison's **llm-smollm2==0.1.2** PyPI wheel,
  project <https://github.com/simonw/llm-smollm2>, Apache-2.0.
- The wheel is fetched from files.pythonhosted.org and verified by pinned SHA-256.
  Only the named GGUF DATA member is extracted; plugin Python code is not run.
- Expected distribution/model hashes and measured file bytes are recorded in
  [model_manifest.json](model_manifest.json). Setup does not bypass a disabled
  Hugging Face host or require an inference API/token.

This is NOT a model trained or invented by AIra. It is an explicitly named
pretrained control. Its observed factual/Russian/format failures are preserved.

## Runtime and UI

- llama-cpp-python0.3.7 / vendored llama.cpp: MIT; native CPU build.
- NumPy: BSD; FastAPI: MIT; Uvicorn: BSD; psutil: BSD; HTTPX/pytest: BSD/MIT.
  Actual pinned Python versions are in requirements.txt and the observed
  environment snapshot. See distributions for authoritative license text.
- UI is new HTML/CSS/JavaScript with original simple inline SVG; no external fonts,
  browser LLM service or image assets. It uses same-origin relative API URLs.
- Optional browser testing uses puppeteer-core24.4.0 and @sparticuz/chromium133.0.0
  from npm, including bundled native NSS libraries. Test binaries are ignored,
  are not the serving runtime and are not counted in backend process RSS.

## Authored prototype pieces

Tiny NumPy router/backward, limited AST calculator, local-note lookup, API,
feedback/promotion guard, data seeds and UI were implemented in this cycle.
They are small engineering components, not claims of new general ML algorithms.
The router training checkpoint is included because it is small and required;
large language weights and temporary candidate weights remain ignored.

The supplied historical AIra branches were read as references in the preceding
review. No code, model weights, corpus or numerical claims from those branches
are imported into this application. In particular, these tests do NOT validate
or fix the old donor_patch.py gradient path or TwoTimeCore causality issue.
