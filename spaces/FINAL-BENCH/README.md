---
title: FINAL-BENCH
emoji: "\U0001F3C6"
colorFrom: blue
colorTo: green
sdk: gradio
sdk_version: 5.29.0
app_file: app.py
pinned: false
---

# FINAL-BENCH: A/B Coding Benchmark

**Same model (Kimi K2.5), same 20 problems, different prompting strategy.**

Demonstrates the value of multi-agent orchestration (oh-my-claudecode patterns):

- **A (Vanilla)**: Single prompt → direct code generation (1 API call)
- **B (OMC-Enhanced)**: Analyst → Planner → Executor → Verifier pipeline (4 API calls)

### Tabs
- **A/B Benchmark**: Run all 20 problems in both modes, compare pass rates
- **Single Problem A/B**: Deep-dive into a single problem with side-by-side code comparison
- **AI Analysis**: Kimi K2.5 analyzes its own A/B results
