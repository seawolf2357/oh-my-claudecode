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

## Fixes Applied (v3.1)

### 1. Missing Module Files (Critical — 5 ImportErrors fixed)

| Missing File | Dependents | Fix |
|---|---|---|
| `tools/base_tool.py` | `semantic_scholar.py` | Created BaseTool base class |
| `perform_llm_review.py` | `perform_vlm_review.py` → writeup | Created with `load_paper()` + `perform_review()` |
| `perform_review.py` | `app.py` (v3) | Created compatibility re-export module |
| `utils/token_tracker.py` | `llm.py`, `vlm.py` | Created TokenTracker with `@track_token_usage` decorator |
| `__init__.py` (6 files) | All module imports | Created for all packages |

### 2. Blank LaTeX Template Missing (Critical — Root cause of empty papers)

`blank_icbinb_latex/template.tex` did not exist. Writeup pipeline copied from this directory to create `latex/template.tex`. Without it, no paper content could be generated.

**Fix**: Created complete ICBINB workshop template with all sections.

### 3. Semantic Scholar 429 Giveup (High)

Added `giveup` handler to both `@backoff.on_exception` decorators — immediately stops retrying on 403/429 instead of infinite exponential backoff.

### 4. VLM Client Crash in Writeup (High)

`perform_icbinb_writeup.py` created VLM client with `small_model` (defaults to `gpt-4o`) which fails when only Fireworks API key is available.

**Fixes**:
- VLM client now uses `big_model` (fireworks) instead of `small_model`
- VLM client initialized before try block, used as guard in reflection loops
- All VLM calls wrapped in try/except with graceful fallback

### 5. Plot Aggregation Code Extraction (Medium)

`extract_code_snippet` already had multi-strategy fallbacks. Verified working for: standard fences, generic fences, partial fences, raw Python.

## Module Structure

```
ai_scientist/
├── __init__.py
├── llm.py                          # LLM client + routing (Fireworks/Claude/GPT/Ollama/Gemini)
├── vlm.py                          # Vision-Language Model support
├── perform_plotting.py             # Plot aggregation with LLM
├── perform_icbinb_writeup.py       # Full writeup pipeline (citations + ReACT + reflections)
├── perform_llm_review.py           # Paper review (load_paper + perform_review)
├── perform_review.py               # Compatibility re-export
├── perform_vlm_review.py           # VLM-based figure review
├── react_writeup_agent.py          # ReACT pattern section writer
├── knowledge_graph.py              # Optional Zep GraphRAG / keyword fallback
├── blank_icbinb_latex/
│   └── template.tex                # ICBINB workshop LaTeX template
├── tools/
│   ├── base_tool.py                # BaseTool abstract class
│   └── semantic_scholar.py         # Semantic Scholar API with backoff
├── utils/
│   └── token_tracker.py            # Token usage tracking
└── treesearch/
    ├── bfts_utils.py               # BFTS utilities
    ├── journal.py                  # Experiment journal
    ├── agent_manager.py            # Agent orchestration
    ├── parallel_agent.py           # Parallel agent execution
    ├── perform_experiments_bfts_with_agentmanager.py
    ├── backend/
    │   ├── backend_openai.py       # OpenAI-compatible backend
    │   └── backend_anthropic.py    # Anthropic backend
    └── utils/
        └── response.py
```

## Deployment

Requires: `FIREWORKS_API_KEY`, `HF_TOKEN` environment variables.

```bash
docker build -t ai-scienceflow .
docker run -p 7860:7860 -e FIREWORKS_API_KEY=... -e HF_TOKEN=... ai-scienceflow
```
