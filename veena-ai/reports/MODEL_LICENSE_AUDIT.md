# Model and component licence audit

Verified on **9 November 2026** from each model's official Hugging Face model card (`cardData.license`, via `https://huggingface.co/api/models/<id>`) and each project's `LICENSE` file. This is an engineering audit, not legal advice; have a lawyer review before selling the product.

## Finding (P0, fixed)

VEENA's **Lite and Balanced profiles recommended Qwen2.5-VL-3B for vision, and Balanced recommended Qwen2.5-3B for text. Both are under the Qwen Research License**, which grants use "FOR NON-COMMERCIAL PURPOSES ONLY" and defines non-commercial as "research or evaluation purposes only" (Qwen2.5-VL-3B-Instruct `LICENSE`, lines 16 and 19). Shipping them as defaults in a commercially distributed product was a licensing blocker.

**Fix:** every default is now Apache 2.0, chosen by testing on VEENA's own tasks ([REAL_MODEL_EVALUATION.md](REAL_MODEL_EVALUATION.md)):

| Profile | Text model | Vision model |
|---|---|---|
| Lite | qwen2.5:1.5b (Apache 2.0) | qwen3-vl:2b-instruct (Apache 2.0) |
| Balanced | qwen3:1.7b (Apache 2.0) | qwen3-vl:2b-instruct (Apache 2.0) |
| Performance | qwen2.5:7b (Apache 2.0) | qwen2.5vl:7b (Apache 2.0) |

Guards so it cannot regress:
- `backend/models/profiles.py: MODEL_CATALOG` records each model's licence, and `license_of()` looks it up.
- The unit test `test_every_recommended_model_allows_commercial_use` fails if any profile default is non-commercial or unlisted.
- The CI `security` job fails on the same condition.
- Setup marks any installed model with a non-commercial licence "(non-commercial licence)" and shows a notice if one is selected.

## Language and vision models

| Ollama tag | Model card | Licence | Commercial use | Role in VEENA |
|---|---|---|---|---|
| qwen2.5:1.5b | Qwen/Qwen2.5-1.5B-Instruct | Apache 2.0 | Yes | Lite text default |
| qwen2.5:0.5b | Qwen/Qwen2.5-0.5B-Instruct | Apache 2.0 | Yes | CI first-run test only |
| qwen2.5:3b | Qwen/Qwen2.5-3B-Instruct | **Qwen Research License** | **No** | Removed from defaults |
| qwen2.5:7b | Qwen/Qwen2.5-7B-Instruct | Apache 2.0 | Yes | Performance text default |
| qwen3:1.7b | Qwen/Qwen3-1.7B | Apache 2.0 | Yes | Balanced text default |
| qwen3:4b | Qwen/Qwen3-4B | Apache 2.0 | Yes | Rejected on quality (reasoning leaked into answers, 64–197 s) |
| qwen3:8b | Qwen/Qwen3-8B | Apache 2.0 | Yes | Catalogued only |
| qwen2.5vl:3b | Qwen/Qwen2.5-VL-3B-Instruct | **Qwen Research License** | **No** | Removed from defaults |
| qwen2.5vl:7b | Qwen/Qwen2.5-VL-7B-Instruct | Apache 2.0 | Yes | Performance vision default |
| qwen3-vl:2b-instruct | Qwen/Qwen3-VL-2B-Instruct | Apache 2.0 | Yes | Lite and Balanced vision default |
| qwen3-vl:4b, :8b | Qwen/Qwen3-VL-4B/8B-Instruct | Apache 2.0 | Yes | Catalogued only |
| granite3.2-vision:2b | ibm-granite/granite-vision-3.2-2b | Apache 2.0 | Yes | Tested; slower than qwen3-vl |
| gemma4:e2b / e4b | google/gemma-4-E2B-it / E4B-it | Apache 2.0 | Yes | Not tested here: 4.6 GB did not fit this machine's free disk |
| gemma3 (any) | google/gemma-3-*-it | Gemma Terms of Use (gated) | Allowed with use restrictions | Not recommended (custom terms) |

Note: Ollama's `qwen3-vl:2b` tag is the **thinking** variant, which reasons before answering even with thinking disabled. It returned empty answers after 6+ minutes in our test, so VEENA uses the `-instruct` tag. Do not assume that every size or tag of one model family shares a licence or behaviour: Qwen2.5-1.5B is Apache 2.0, while Qwen2.5-3B is research-only.

## Speech, embeddings and other bundled or downloaded components

| Component | Licence | Source checked |
|---|---|---|
| Whisper weights via faster-whisper (Systran/faster-whisper-tiny/base/small) | MIT | Hugging Face model cards |
| faster-whisper library | MIT | SYSTRAN/faster-whisper LICENSE |
| Silero VAD | MIT | snakers4/silero-vad LICENSE |
| all-MiniLM-L6-v2 embeddings | Apache 2.0 | Hugging Face model card |
| FAISS | MIT | facebookresearch/faiss LICENSE |
| Tesseract OCR (optional, user-installed) | Apache 2.0 | tesseract-ocr/tesseract LICENSE |
| Ollama runtime (downloaded at setup) | MIT | ollama/ollama LICENSE |
| Electron | MIT | electron/electron LICENSE |
| Python dependencies | per package | `pip-licenses` report in CI artifact `veena-ai-sbom-and-licences` |

## VEENA itself

VEENA's source is **GPL-3.0**. Selling or distributing GPL software commercially is allowed, provided recipients get the source under the same licence. All the components above have permissive licences compatible with that. If the owner later wants a closed-source edition, the GPL licence of VEENA's own code must be revisited by its copyright holder.

## Open items

- Gemma 4 (Apache 2.0) is a promising Balanced option but was not evaluated here, because it did not fit this machine's disk. Evaluate it on a machine with 10+ GB free before considering it.
- Model weights are downloaded from the Ollama library, not bundled. Ollama's library terms and the upstream model licences both apply to customers; the release notes and installation guide should keep linking this audit.
