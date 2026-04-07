---
title: AI ScienceFlow
emoji: 🔬
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: true
license: mit
short_description: Autonomous Scientific Research Platform
---

# AI ScienceFlow

Autonomous Scientific Research Platform powered by multi-agent AI.

## Architecture

FastAPI backend + vanilla JS/CSS/HTML SPA with 4-step workflow:

1. **Setup** — LLM API config (Fireworks/Anthropic/OpenAI) + file upload with ontology graph (D3.js)
2. **Ideation** — LLM-powered research idea generation
3. **Experiment** — BFTS tree search pipeline with live WebSocket logs
4. **Results** — Figures, summaries, review, PDF paper

## Known Issues & Fixes

### 1. Semantic Scholar Infinite Backoff (Critical)

**File**: `ai_scientist/tools/semantic_scholar.py`
**Problem**: `@backoff.on_exception` has no `max_tries` — 429 rate limits cause infinite retry with exponential wait (1647s+ observed).
**Fix**: `patches/fix_semantic_scholar_backoff.py` — adds `max_tries=5, max_time=120`

### 2. Plot Aggregation SyntaxError (High)

**File**: `ai_scientist/perform_plotting.py`
**Problem**: `extract_code_snippet` fails on malformed LLM output (partial markdown fences, mixed text+code).
**Fix**: `patches/fix_plot_aggregation_syntax.py` — robust multi-strategy code extraction

### 3. Paper Generation Empty Templates (Medium)

All 3 completed experiments produced placeholder `template.tex` with no actual content written. The writeup pipeline (`perform_icbinb_writeup.py`) needs investigation — the ReACT agent generates section drafts but they may not be injected into the LaTeX template.

### 4. Missing Review Module (Low)

`perform_review.py` and `perform_vlm_review.py` need to be copied from v2 Space to v3.

## Experiment Results Analysis

Three experiments completed on the platform (stored in `SeaWolf-AI/ai-scientist-results`):

| Experiment | Quality | Key Finding |
|---|---|---|
| Neuro-Symbolic Epistemic Gates | 2/10 | 100% hallucination, broken evaluation metrics |
| Context-Aware Multimodal Translation | 3/10 | Trivially easy synthetic task, 100% accuracy meaningless |
| Neurosurgical Crossover | 5/10 | Genuine proof-of-concept: 86-89% capability retention |

### Detailed Findings

**Neurosurgical Crossover** (best result):
- Parent A accuracy: 97.84%, Offspring: 84.55%
- Demonstrates real neural network crossover with capability retention
- Legitimate proof-of-concept despite simplified setup

**Key pipeline issues across all experiments**:
- Stage 1 (BFTS tree search) works correctly
- Writeup stage fails to populate template.tex with actual content
- Citation gathering blocked by Semantic Scholar rate limits
- Plot aggregation crashes on malformed LLM code output

## Deployment

```bash
# Apply patches before deploying
python patches/fix_semantic_scholar_backoff.py ai_scientist/tools/semantic_scholar.py
python patches/fix_plot_aggregation_syntax.py  # self-test mode

# Deploy to HF Space
# Requires: FIREWORKS_API_KEY, HF_TOKEN environment variables
```
