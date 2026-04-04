"""
FINAL-BENCH: Kimi K2.5 A/B Coding Benchmark
A (Vanilla) vs B (OMC-Enhanced) — same model, same problems, different prompting strategy.
Demonstrates the value of multi-agent orchestration patterns.
"""

import os
import re
import json
import time
import requests
import gradio as gr
import plotly.graph_objects as go
import pandas as pd

from benchmark_data import PROBLEMS, DIFFICULTY_COUNTS, CATEGORY_SET

FIREWORKS_API_KEY = os.getenv("FIREWORKS_API_KEY")
API_URL = "https://api.fireworks.ai/inference/v1/chat/completions"
MODEL = "accounts/fireworks/models/kimi-k2p5"

# ── Global results ─────────────────────────────────────────────────────

results_a = {}  # Vanilla
results_b = {}  # OMC-Enhanced


# ── API call ───────────────────────────────────────────────────────────

def call_kimi(messages, max_tokens=2048, temperature=0.2):
    if not FIREWORKS_API_KEY:
        return None, "FIREWORKS_API_KEY not set"
    payload = {
        "model": MODEL, "max_tokens": max_tokens,
        "temperature": temperature, "top_p": 1, "top_k": 40,
        "messages": messages,
    }
    headers = {
        "Accept": "application/json", "Content-Type": "application/json",
        "Authorization": f"Bearer {FIREWORKS_API_KEY}",
    }
    try:
        resp = requests.post(API_URL, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"], None
    except Exception as e:
        return None, str(e)


def extract_code(raw):
    if not raw:
        return ""
    m = re.search(r"```(?:python)?\s*\n(.*?)```", raw, re.DOTALL)
    return m.group(1).strip() if m else raw.strip()


def run_tests(code, test_code):
    ns = {}
    try:
        exec(code, ns)
        exec(test_code, ns)
        return True, None
    except AssertionError as e:
        return False, f"AssertionError: {e}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


# ── Mode A: Vanilla (single prompt) ───────────────────────────────────

VANILLA_SYSTEM = "You are an expert Python programmer. Write clean, correct code. Output ONLY the Python code, no explanations, no markdown fences."

def solve_vanilla(prob):
    start = time.time()
    raw, err = call_kimi([
        {"role": "system", "content": VANILLA_SYSTEM},
        {"role": "user", "content": prob["prompt"]},
    ])
    elapsed = time.time() - start
    if err:
        return {"status": "api_error", "error": err, "time": round(elapsed, 2), "code": "", "raw": ""}
    code = extract_code(raw)
    passed, test_err = run_tests(code, prob["test_code"])
    return {"status": "PASS" if passed else "FAIL", "time": round(elapsed, 2),
            "code": code, "raw": raw, "error": test_err}


# ── Mode B: OMC-Enhanced (4-step pipeline) ─────────────────────────────

def solve_omc(prob):
    start = time.time()
    steps = {}

    # Step 1: Analyst
    analysis, err = call_kimi([
        {"role": "system", "content": "You are a requirements analyst. Analyze the coding problem thoroughly."},
        {"role": "user", "content": f"""Analyze this problem:

{prob['prompt']}

List:
1. **Inputs/Outputs**: exact types, constraints
2. **Edge cases**: empty input, single element, negative values, duplicates, etc.
3. **Constraints**: time/space requirements, special conditions
4. **Potential pitfalls**: off-by-one, overflow, mutability, etc.

Be concise and specific."""},
    ], max_tokens=1024)
    if err:
        return {"status": "api_error", "error": f"Analyst: {err}", "time": round(time.time()-start, 2),
                "code": "", "steps": {}}
    steps["analysis"] = analysis

    # Step 2: Planner
    plan, err = call_kimi([
        {"role": "system", "content": "You are an algorithm planner. Design the implementation strategy."},
        {"role": "user", "content": f"""Problem:
{prob['prompt']}

Analysis:
{analysis}

Plan the implementation:
1. **Algorithm**: which approach and why
2. **Data structures**: what to use
3. **Steps**: step-by-step pseudocode
4. **Complexity**: time and space

Be concise."""},
    ], max_tokens=1024)
    if err:
        return {"status": "api_error", "error": f"Planner: {err}", "time": round(time.time()-start, 2),
                "code": "", "steps": steps}
    steps["plan"] = plan

    # Step 3: Executor
    raw_code, err = call_kimi([
        {"role": "system", "content": "You are an expert Python programmer. Implement the solution based on the analysis and plan provided. Output ONLY the Python code, no explanations, no markdown fences."},
        {"role": "user", "content": f"""Problem:
{prob['prompt']}

Analysis:
{analysis}

Plan:
{plan}

Implement the solution now. Handle all edge cases identified. Output ONLY Python code."""},
    ])
    if err:
        return {"status": "api_error", "error": f"Executor: {err}", "time": round(time.time()-start, 2),
                "code": "", "steps": steps}
    code = extract_code(raw_code)
    steps["executor_code"] = code

    # Step 4: Verifier — check and fix
    verified, err = call_kimi([
        {"role": "system", "content": "You are a code verifier. Review the code for correctness. If you find any bugs, output the FIXED code. If the code is correct, output it unchanged. Output ONLY the final Python code, no explanations, no markdown fences."},
        {"role": "user", "content": f"""Problem:
{prob['prompt']}

Edge cases to handle:
{analysis}

Code to verify:
```python
{code}
```

Check:
1. Does it handle all edge cases?
2. Are there off-by-one errors?
3. Does it return the correct type?
4. Will it work for empty/minimal inputs?

Output ONLY the final (fixed if needed) Python code."""},
    ])
    if err:
        # Use executor code if verifier fails
        final_code = code
    else:
        final_code = extract_code(verified)
    steps["final_code"] = final_code

    elapsed = time.time() - start
    passed, test_err = run_tests(final_code, prob["test_code"])

    return {"status": "PASS" if passed else "FAIL", "time": round(elapsed, 2),
            "code": final_code, "raw": verified or raw_code, "error": test_err, "steps": steps}


# ── Run full A/B benchmark ─────────────────────────────────────────────

def run_ab_benchmark(progress=gr.Progress()):
    results_a.clear()
    results_b.clear()
    total = len(PROBLEMS)
    rows = []

    for i, prob in enumerate(PROBLEMS):
        progress(i / total, f"[{i+1}/{total}] {prob['id']}: {prob['title']} — Running A...")

        # Mode A
        res_a = solve_vanilla(prob)
        results_a[prob["id"]] = res_a

        progress((i + 0.5) / total, f"[{i+1}/{total}] {prob['id']}: {prob['title']} — Running B (OMC)...")

        # Mode B
        res_b = solve_omc(prob)
        results_b[prob["id"]] = res_b

        # Determine change
        a_pass = res_a["status"] == "PASS"
        b_pass = res_b["status"] == "PASS"
        if not a_pass and b_pass:
            change = "B FIXED"
        elif a_pass and not b_pass:
            change = "B BROKE"
        elif a_pass and b_pass:
            change = "BOTH PASS"
        else:
            change = "BOTH FAIL"

        rows.append({
            "ID": prob["id"], "Problem": prob["title"], "Diff": prob["difficulty"],
            "A (Vanilla)": res_a["status"], "B (OMC)": res_b["status"],
            "A Time": f"{res_a['time']}s", "B Time": f"{res_b['time']}s",
            "Change": change,
        })

    progress(1.0, "Complete!")
    df = pd.DataFrame(rows)
    summary = build_ab_summary()
    compare_chart = build_compare_chart()
    diff_chart = build_diff_compare_chart()
    cat_chart = build_cat_compare_chart()
    return df, summary, compare_chart, diff_chart, cat_chart


# ── Run single A/B ─────────────────────────────────────────────────────

def run_single_ab(problem_choice):
    if not problem_choice:
        return "Select a problem", "", "", "", "", ""
    prob_id = problem_choice.split(" - ")[0]
    prob = next((p for p in PROBLEMS if p["id"] == prob_id), None)
    if not prob:
        return "Not found", "", "", "", "", ""

    res_a = solve_vanilla(prob)
    results_a[prob["id"]] = res_a
    res_b = solve_omc(prob)
    results_b[prob["id"]] = res_b

    status = f"""## A (Vanilla): {res_a['status']} ({res_a['time']}s) → B (OMC): {res_b['status']} ({res_b['time']}s)"""
    if res_a.get("error"):
        status += f"\n**A Error:** `{res_a['error']}`"
    if res_b.get("error"):
        status += f"\n**B Error:** `{res_b['error']}`"

    steps_text = ""
    if res_b.get("steps"):
        s = res_b["steps"]
        steps_text = f"### Step 1: Analysis\n{s.get('analysis','N/A')}\n\n### Step 2: Plan\n{s.get('plan','N/A')}"

    return status, res_a.get("code", ""), res_b.get("code", ""), steps_text, prob["prompt"], prob["test_code"]


# ── Charts ─────────────────────────────────────────────────────────────

def build_compare_chart():
    if not results_a:
        fig = go.Figure()
        fig.update_layout(title="Run benchmark first", template="plotly_dark", height=380)
        return fig
    a_pass = sum(1 for r in results_a.values() if r["status"] == "PASS")
    b_pass = sum(1 for r in results_b.values() if r["status"] == "PASS")
    total = len(results_a)
    a_rate = a_pass / max(total, 1) * 100
    b_rate = b_pass / max(total, 1) * 100

    fig = go.Figure()
    fig.add_trace(go.Bar(name="A (Vanilla)", x=["Pass Rate"], y=[a_rate],
                         marker_color="#6366f1", text=[f"{a_rate:.0f}% ({a_pass}/{total})"], textposition="auto"))
    fig.add_trace(go.Bar(name="B (OMC-Enhanced)", x=["Pass Rate"], y=[b_rate],
                         marker_color="#10b981", text=[f"{b_rate:.0f}% ({b_pass}/{total})"], textposition="auto"))
    fig.update_layout(title="A/B Pass Rate Comparison", barmode="group",
                      template="plotly_dark", height=400, yaxis_range=[0, 100], yaxis_title="%")
    return fig


def build_diff_compare_chart():
    if not results_a:
        fig = go.Figure()
        fig.update_layout(title="Run benchmark first", template="plotly_dark", height=380)
        return fig
    diffs = ["Easy", "Medium", "Hard"]
    a_rates, b_rates = [], []
    for d in diffs:
        probs = [p for p in PROBLEMS if p["difficulty"] == d]
        a_p = sum(1 for p in probs if results_a.get(p["id"], {}).get("status") == "PASS")
        b_p = sum(1 for p in probs if results_b.get(p["id"], {}).get("status") == "PASS")
        t = max(len(probs), 1)
        a_rates.append(a_p / t * 100)
        b_rates.append(b_p / t * 100)

    fig = go.Figure()
    fig.add_trace(go.Bar(name="A (Vanilla)", x=diffs, y=a_rates, marker_color="#6366f1",
                         text=[f"{r:.0f}%" for r in a_rates], textposition="auto"))
    fig.add_trace(go.Bar(name="B (OMC)", x=diffs, y=b_rates, marker_color="#10b981",
                         text=[f"{r:.0f}%" for r in b_rates], textposition="auto"))
    fig.update_layout(title="Pass Rate by Difficulty", barmode="group",
                      template="plotly_dark", height=400, yaxis_range=[0, 100], yaxis_title="%")
    return fig


def build_cat_compare_chart():
    if not results_a:
        fig = go.Figure()
        fig.update_layout(title="Run benchmark first", template="plotly_dark", height=380)
        return fig
    cats = {}
    for p in PROBLEMS:
        c = p["category"]
        if c not in cats:
            cats[c] = {"a": 0, "b": 0, "total": 0}
        cats[c]["total"] += 1
        if results_a.get(p["id"], {}).get("status") == "PASS":
            cats[c]["a"] += 1
        if results_b.get(p["id"], {}).get("status") == "PASS":
            cats[c]["b"] += 1

    names = sorted(cats.keys())
    a_vals = [cats[n]["a"] for n in names]
    b_vals = [cats[n]["b"] for n in names]

    fig = go.Figure()
    fig.add_trace(go.Bar(name="A (Vanilla)", x=names, y=a_vals, marker_color="#6366f1"))
    fig.add_trace(go.Bar(name="B (OMC)", x=names, y=b_vals, marker_color="#10b981"))
    fig.update_layout(title="Passed by Category", barmode="group",
                      template="plotly_dark", height=420, xaxis_tickangle=-30)
    return fig


def build_ab_summary():
    if not results_a:
        return "Click **Run A/B Benchmark** to start."
    total = len(results_a)
    a_pass = sum(1 for r in results_a.values() if r["status"] == "PASS")
    b_pass = sum(1 for r in results_b.values() if r["status"] == "PASS")
    a_time = sum(r["time"] for r in results_a.values())
    b_time = sum(r["time"] for r in results_b.values())
    fixed = sum(1 for pid in results_a if results_a[pid]["status"] != "PASS" and results_b.get(pid, {}).get("status") == "PASS")
    broke = sum(1 for pid in results_a if results_a[pid]["status"] == "PASS" and results_b.get(pid, {}).get("status") != "PASS")

    delta = b_pass - a_pass
    delta_str = f"+{delta}" if delta >= 0 else str(delta)

    return f"""## A/B Benchmark Results

| Metric | A (Vanilla) | B (OMC-Enhanced) | Delta |
|--------|-------------|------------------|-------|
| **Pass Rate** | **{a_pass}/{total} ({a_pass/total*100:.0f}%)** | **{b_pass}/{total} ({b_pass/total*100:.0f}%)** | **{delta_str}** |
| Total Time | {a_time:.1f}s | {b_time:.1f}s | +{b_time-a_time:.1f}s |
| Avg Time | {a_time/total:.1f}s | {b_time/total:.1f}s | |
| **B Fixed (A fail → B pass)** | | | **{fixed}** |
| **B Broke (A pass → B fail)** | | | **{broke}** |

### OMC Pipeline Overhead
B mode makes **4 API calls** per problem (Analyst → Planner → Executor → Verifier) vs A's **1 call**.
Extra time is the cost of orchestration — the question is whether it buys enough accuracy to justify it.
"""


# ── AI Chat ────────────────────────────────────────────────────────────

def chat_analysis(message, history):
    if not FIREWORKS_API_KEY:
        yield "Error: FIREWORKS_API_KEY not set."
        return

    ctx = build_ab_summary()
    details = ""
    for prob in PROBLEMS:
        pid = prob["id"]
        ra = results_a.get(pid, {})
        rb = results_b.get(pid, {})
        if ra or rb:
            details += f"\n- {pid} {prob['title']} ({prob['difficulty']}): A={ra.get('status','N/A')} B={rb.get('status','N/A')}"
            if ra.get("error"):
                details += f" | A err: {ra['error'][:60]}"
            if rb.get("error"):
                details += f" | B err: {rb['error'][:60]}"

    system = f"""You are a benchmark analysis expert comparing two prompting strategies:
- A (Vanilla): Single prompt, direct code generation
- B (OMC-Enhanced): 4-step pipeline (Analyst→Planner→Executor→Verifier) inspired by oh-my-claudecode multi-agent orchestration

Both use the same model: Kimi K2.5 via Fireworks AI.

{ctx}

### Per-Problem Details:{details}

Analyze WHY orchestration helps or hurts. Reference specific problems. Be data-driven."""

    messages = [{"role": "system", "content": system}]
    for user_msg, bot_msg in history:
        messages.append({"role": "user", "content": user_msg})
        if bot_msg:
            messages.append({"role": "assistant", "content": bot_msg})
    messages.append({"role": "user", "content": message})

    payload = {"model": MODEL, "max_tokens": 4096, "temperature": 0.6,
               "top_p": 1, "top_k": 40, "messages": messages, "stream": True}
    headers = {"Accept": "application/json", "Content-Type": "application/json",
               "Authorization": f"Bearer {FIREWORKS_API_KEY}"}

    try:
        response = requests.post(API_URL, headers=headers, json=payload, stream=True, timeout=120)
        response.raise_for_status()
    except requests.RequestException as e:
        yield f"API Error: {e}"
        return

    partial = ""
    for line in response.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data: "):
            continue
        data = line[len("data: "):]
        if data.strip() == "[DONE]":
            break
        try:
            chunk = json.loads(data)
        except json.JSONDecodeError:
            continue
        choices = chunk.get("choices", [])
        if not choices:
            continue
        token = choices[0].get("delta", {}).get("content", "")
        if token:
            partial += token
            yield partial


# ── UI ─────────────────────────────────────────────────────────────────

PROBLEM_CHOICES = [f"{p['id']} - {p['title']} ({p['difficulty']})" for p in PROBLEMS]

CSS = """
.metric-box { text-align: center; padding: 18px; border-radius: 12px; margin: 6px; }
.a-box { background: linear-gradient(135deg, #312e81, #4338ca); }
.b-box { background: linear-gradient(135deg, #064e3b, #059669); }
.d-box { background: linear-gradient(135deg, #78350f, #d97706); }
.metric-value { font-size: 2em; font-weight: bold; color: white; }
.metric-label { font-size: 0.9em; color: #d1d5db; margin-top: 4px; }
"""

with gr.Blocks(theme=gr.themes.Soft(primary_hue="indigo"), css=CSS, title="FINAL-BENCH") as demo:

    gr.Markdown("""
# FINAL-BENCH: A/B Coding Benchmark
**Same model (Kimi K2.5), same problems, different strategy**

| | A (Vanilla) | B (OMC-Enhanced) |
|---|---|---|
| **Method** | Single prompt → code | Analyst → Planner → Executor → Verifier |
| **API Calls** | 1 per problem | 4 per problem |
| **Hypothesis** | Baseline | Orchestration improves accuracy |
    """)

    with gr.Tabs():

        # ── Tab 1: A/B Benchmark ──────────────────────────────────
        with gr.Tab("A/B Benchmark"):
            run_btn = gr.Button("Run A/B Benchmark (20 problems × 2 modes)", variant="primary", size="lg")

            summary_md = gr.Markdown("Click the button to start.")
            results_table = gr.Dataframe(
                headers=["ID", "Problem", "Diff", "A (Vanilla)", "B (OMC)", "A Time", "B Time", "Change"],
                interactive=False,
            )

            with gr.Row():
                compare_chart = gr.Plot(label="A/B Pass Rate")
                diff_chart = gr.Plot(label="By Difficulty")

            cat_chart = gr.Plot(label="By Category")

            run_btn.click(
                fn=run_ab_benchmark,
                outputs=[results_table, summary_md, compare_chart, diff_chart, cat_chart],
            )

        # ── Tab 2: Single A/B ─────────────────────────────────────
        with gr.Tab("Single Problem A/B"):
            gr.Markdown("### Compare A vs B on a single problem")
            with gr.Row():
                problem_dd = gr.Dropdown(choices=PROBLEM_CHOICES, label="Problem", scale=3)
                single_btn = gr.Button("Run A/B", variant="primary", scale=1)

            single_status = gr.Markdown()

            with gr.Row():
                with gr.Column():
                    gr.Markdown("#### A (Vanilla) Code")
                    code_a = gr.Code(language="python", label="Vanilla", interactive=False)
                with gr.Column():
                    gr.Markdown("#### B (OMC-Enhanced) Code")
                    code_b = gr.Code(language="python", label="OMC", interactive=False)

            gr.Markdown("#### B Mode: OMC Pipeline Steps")
            steps_md = gr.Markdown()

            with gr.Accordion("Problem Details", open=False):
                prompt_box = gr.Textbox(label="Problem Prompt", interactive=False, lines=4)
                test_box = gr.Code(language="python", label="Test Cases", interactive=False)

            single_btn.click(
                fn=run_single_ab,
                inputs=[problem_dd],
                outputs=[single_status, code_a, code_b, steps_md, prompt_box, test_box],
            )

        # ── Tab 3: AI Analysis ────────────────────────────────────
        with gr.Tab("AI Analysis"):
            gr.Markdown("""
### Benchmark Analyst (Kimi K2.5)
Ask about A/B results, why orchestration helps or hurts, and optimization ideas.
*Run the benchmark first for meaningful analysis.*
            """)
            gr.ChatInterface(
                fn=chat_analysis, type="tuples",
                examples=[
                    "Compare A vs B results. Where does orchestration help most?",
                    "Which problems did B fix that A couldn't? Why?",
                    "Is the 4x API cost worth the accuracy improvement?",
                    "What types of problems don't benefit from orchestration?",
                    "How could the OMC pipeline be optimized for better results?",
                ],
                cache_examples=False,
            )

    gr.Markdown("""
---
**FINAL-BENCH** | A: Vanilla (1 call) vs B: OMC Pipeline (4 calls) | Kimi K2.5 via Fireworks AI | Real-time execution & testing
    """)


if __name__ == "__main__":
    demo.launch()
