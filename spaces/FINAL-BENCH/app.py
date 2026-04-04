"""
FINAL-BENCH: Kimi K2.5 Live Coding Benchmark
Real-time coding problem evaluation using Kimi K2.5 via Fireworks AI.
"""

import os
import re
import json
import time
import traceback
import requests
import gradio as gr
import plotly.graph_objects as go
import pandas as pd

from benchmark_data import PROBLEMS, DIFFICULTY_COUNTS, CATEGORY_SET

FIREWORKS_API_KEY = os.getenv("FIREWORKS_API_KEY")
API_URL = "https://api.fireworks.ai/inference/v1/chat/completions"
MODEL = "accounts/fireworks/models/kimi-k2p5"

# ── Global results store ───────────────────────────────────────────────

results_store = {}  # {problem_id: {status, code, time, error, ...}}


# ── Kimi K2.5 API call ────────────────────────────────────────────────

def call_kimi(prompt, system="You are an expert Python programmer. Write clean, correct code. Output ONLY the Python code, no explanations, no markdown fences."):
    if not FIREWORKS_API_KEY:
        return None, "FIREWORKS_API_KEY not set"

    payload = {
        "model": MODEL,
        "max_tokens": 2048,
        "temperature": 0.2,
        "top_p": 1, "top_k": 40,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    }
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {FIREWORKS_API_KEY}",
    }

    try:
        resp = requests.post(API_URL, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return content, None
    except Exception as e:
        return None, str(e)


def extract_code(raw):
    """Extract Python code from response, stripping markdown fences if present."""
    if raw is None:
        return ""
    # Remove markdown code fences
    match = re.search(r"```(?:python)?\s*\n(.*?)```", raw, re.DOTALL)
    if match:
        return match.group(1).strip()
    # If no fences, return as-is (strip leading/trailing whitespace)
    return raw.strip()


def run_tests(code, test_code):
    """Execute generated code + test cases in isolated namespace."""
    namespace = {}
    try:
        exec(code, namespace)
        exec(test_code, namespace)
        return True, None
    except AssertionError as e:
        return False, f"AssertionError: {e}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


# ── Single problem solver ──────────────────────────────────────────────

def solve_single(problem_id):
    """Solve a single problem and return result dict."""
    prob = next((p for p in PROBLEMS if p["id"] == problem_id), None)
    if not prob:
        return {"status": "error", "error": "Problem not found"}

    start = time.time()
    raw_code, api_error = call_kimi(prob["prompt"])
    elapsed = time.time() - start

    if api_error:
        return {
            "status": "api_error", "error": api_error,
            "time": round(elapsed, 2), "code": "", "raw": "",
        }

    code = extract_code(raw_code)
    passed, test_error = run_tests(code, prob["test_code"])

    result = {
        "status": "PASS" if passed else "FAIL",
        "time": round(elapsed, 2),
        "code": code,
        "raw": raw_code,
        "error": test_error,
    }
    results_store[problem_id] = result
    return result


# ── Run all benchmark ──────────────────────────────────────────────────

def run_full_benchmark(progress=gr.Progress()):
    """Run all problems sequentially, yielding progress updates."""
    results_store.clear()
    total = len(PROBLEMS)
    rows = []

    for i, prob in enumerate(PROBLEMS):
        progress((i) / total, f"Solving {prob['id']}: {prob['title']}...")
        result = solve_single(prob["id"])
        rows.append({
            "ID": prob["id"],
            "Problem": prob["title"],
            "Category": prob["category"],
            "Difficulty": prob["difficulty"],
            "Status": result["status"],
            "Time(s)": result["time"],
            "Error": (result.get("error") or "")[:80],
        })

    progress(1.0, "Complete!")

    df = pd.DataFrame(rows)
    summary = build_summary_text()
    pass_chart = build_results_chart()
    cat_chart = build_category_chart()
    diff_chart = build_difficulty_chart()

    return df, summary, pass_chart, cat_chart, diff_chart


# ── Run single problem ─────────────────────────────────────────────────

def run_single_problem(problem_choice):
    """Run a single selected problem."""
    if not problem_choice:
        return "Select a problem", "", "", ""

    prob_id = problem_choice.split(" - ")[0]
    prob = next((p for p in PROBLEMS if p["id"] == prob_id), None)
    if not prob:
        return "Problem not found", "", "", ""

    result = solve_single(prob_id)
    status_text = f"## {result['status']}\n**Time:** {result['time']}s"
    if result.get("error"):
        status_text += f"\n\n**Error:** `{result['error']}`"

    return status_text, prob["prompt"], result.get("code", ""), prob["test_code"]


# ── Chart builders ─────────────────────────────────────────────────────

def build_results_chart():
    if not results_store:
        fig = go.Figure()
        fig.update_layout(title="No results yet - run benchmark first",
                          template="plotly_dark", height=350)
        return fig

    passed = sum(1 for r in results_store.values() if r["status"] == "PASS")
    failed = sum(1 for r in results_store.values() if r["status"] == "FAIL")
    errors = sum(1 for r in results_store.values() if r["status"] == "api_error")

    fig = go.Figure(data=[go.Pie(
        labels=["PASS", "FAIL", "API Error"],
        values=[passed, failed, errors],
        marker=dict(colors=["#10b981", "#ef4444", "#6b7280"]),
        textinfo="label+value+percent",
        hole=0.4,
    )])
    fig.update_layout(
        title=f"Overall Results: {passed}/{len(results_store)} Passed ({passed/max(len(results_store),1)*100:.0f}%)",
        template="plotly_dark", height=380,
    )
    return fig


def build_category_chart():
    if not results_store:
        fig = go.Figure()
        fig.update_layout(title="No results yet", template="plotly_dark", height=350)
        return fig

    cat_pass = {}
    cat_total = {}
    for prob in PROBLEMS:
        if prob["id"] in results_store:
            cat = prob["category"]
            cat_total[cat] = cat_total.get(cat, 0) + 1
            if results_store[prob["id"]]["status"] == "PASS":
                cat_pass[cat] = cat_pass.get(cat, 0) + 1

    cats = sorted(cat_total.keys())
    pass_vals = [cat_pass.get(c, 0) for c in cats]
    fail_vals = [cat_total[c] - cat_pass.get(c, 0) for c in cats]

    fig = go.Figure()
    fig.add_trace(go.Bar(name="PASS", x=cats, y=pass_vals, marker_color="#10b981"))
    fig.add_trace(go.Bar(name="FAIL", x=cats, y=fail_vals, marker_color="#ef4444"))
    fig.update_layout(
        title="Results by Category", barmode="stack",
        template="plotly_dark", height=380, xaxis_tickangle=-30,
    )
    return fig


def build_difficulty_chart():
    if not results_store:
        fig = go.Figure()
        fig.update_layout(title="No results yet", template="plotly_dark", height=350)
        return fig

    diff_pass = {}
    diff_total = {}
    for prob in PROBLEMS:
        if prob["id"] in results_store:
            d = prob["difficulty"]
            diff_total[d] = diff_total.get(d, 0) + 1
            if results_store[prob["id"]]["status"] == "PASS":
                diff_pass[d] = diff_pass.get(d, 0) + 1

    diffs = ["Easy", "Medium", "Hard"]
    rates = [diff_pass.get(d, 0) / max(diff_total.get(d, 1), 1) * 100 for d in diffs]
    colors = ["#10b981", "#eab308", "#ef4444"]

    fig = go.Figure(data=[go.Bar(
        x=diffs, y=rates, marker_color=colors,
        text=[f"{r:.0f}%" for r in rates], textposition="auto",
    )])
    fig.update_layout(
        title="Pass Rate by Difficulty",
        template="plotly_dark", height=380,
        yaxis_title="Pass Rate (%)", yaxis_range=[0, 100],
    )
    return fig


def build_time_chart():
    if not results_store:
        fig = go.Figure()
        fig.update_layout(title="No results yet", template="plotly_dark", height=350)
        return fig

    ids = []
    times = []
    colors = []
    for prob in PROBLEMS:
        if prob["id"] in results_store:
            ids.append(prob["id"])
            times.append(results_store[prob["id"]]["time"])
            colors.append("#10b981" if results_store[prob["id"]]["status"] == "PASS" else "#ef4444")

    fig = go.Figure(data=[go.Bar(x=ids, y=times, marker_color=colors)])
    fig.update_layout(
        title="Response Time per Problem (green=PASS, red=FAIL)",
        template="plotly_dark", height=380,
        yaxis_title="Time (seconds)",
    )
    return fig


def build_summary_text():
    if not results_store:
        return "No results yet. Click **Run Full Benchmark** to start."

    total = len(results_store)
    passed = sum(1 for r in results_store.values() if r["status"] == "PASS")
    failed = sum(1 for r in results_store.values() if r["status"] == "FAIL")
    errors = sum(1 for r in results_store.values() if r["status"] == "api_error")
    avg_time = sum(r["time"] for r in results_store.values()) / max(total, 1)
    total_time = sum(r["time"] for r in results_store.values())

    return f"""## Kimi K2.5 Benchmark Results

| Metric | Value |
|--------|-------|
| **Model** | Kimi K2.5 (Fireworks AI) |
| **Total Problems** | {total} |
| **Passed** | {passed} ({passed/total*100:.1f}%) |
| **Failed** | {failed} |
| **API Errors** | {errors} |
| **Avg Response Time** | {avg_time:.1f}s |
| **Total Time** | {total_time:.1f}s |

### Difficulty Breakdown
| Difficulty | Pass Rate |
|------------|-----------|
| Easy | {sum(1 for p in PROBLEMS if p['difficulty']=='Easy' and results_store.get(p['id'],{}).get('status')=='PASS')}/{DIFFICULTY_COUNTS['Easy']} |
| Medium | {sum(1 for p in PROBLEMS if p['difficulty']=='Medium' and results_store.get(p['id'],{}).get('status')=='PASS')}/{DIFFICULTY_COUNTS['Medium']} |
| Hard | {sum(1 for p in PROBLEMS if p['difficulty']=='Hard' and results_store.get(p['id'],{}).get('status')=='PASS')}/{DIFFICULTY_COUNTS['Hard']} |
"""


# ── AI Chat about results ─────────────────────────────────────────────

def chat_analysis(message, history):
    if not FIREWORKS_API_KEY:
        yield "Error: FIREWORKS_API_KEY not set."
        return

    ctx = build_summary_text()
    details = ""
    for prob in PROBLEMS:
        if prob["id"] in results_store:
            r = results_store[prob["id"]]
            details += f"\n- {prob['id']} {prob['title']} ({prob['difficulty']}): {r['status']} in {r['time']}s"
            if r.get("error"):
                details += f" | Error: {r['error'][:100]}"

    system = f"""You are a coding benchmark analysis expert. You are analyzing Kimi K2.5's performance on a coding benchmark.

{ctx}

### Per-Problem Details:{details}

Provide specific, data-driven analysis. Reference problem IDs and categories when discussing patterns."""

    messages = [{"role": "system", "content": system}]
    for user_msg, bot_msg in history:
        messages.append({"role": "user", "content": user_msg})
        if bot_msg:
            messages.append({"role": "assistant", "content": bot_msg})
    messages.append({"role": "user", "content": message})

    payload = {
        "model": MODEL,
        "max_tokens": 4096,
        "temperature": 0.6,
        "top_p": 1, "top_k": 40,
        "messages": messages,
        "stream": True,
    }
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {FIREWORKS_API_KEY}",
    }

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


# ── Problem list for dropdown ──────────────────────────────────────────

PROBLEM_CHOICES = [f"{p['id']} - {p['title']} ({p['difficulty']})" for p in PROBLEMS]


# ── Gradio UI ──────────────────────────────────────────────────────────

CSS = """
.metric-box { text-align: center; padding: 18px; border-radius: 12px; margin: 6px; }
.pass-box { background: linear-gradient(135deg, #064e3b, #059669); }
.total-box { background: linear-gradient(135deg, #312e81, #4338ca); }
.time-box { background: linear-gradient(135deg, #78350f, #d97706); }
.metric-value { font-size: 2em; font-weight: bold; color: white; }
.metric-label { font-size: 0.9em; color: #d1d5db; margin-top: 4px; }
"""

with gr.Blocks(theme=gr.themes.Soft(primary_hue="indigo"), css=CSS, title="FINAL-BENCH") as demo:

    gr.Markdown("""
# FINAL-BENCH: Kimi K2.5 Live Coding Benchmark
**Real-time coding evaluation** — Kimi K2.5 solves problems, code is executed, tests are verified.

> Model: `kimi-k2p5` via Fireworks AI | 20 Problems | Easy/Medium/Hard | 12 Categories
    """)

    with gr.Tabs():

        # ── Tab 1: Run Benchmark ──────────────────────────────────
        with gr.Tab("Run Benchmark"):
            gr.Markdown("### Full Benchmark (20 Problems)")
            run_btn = gr.Button("Run Full Benchmark", variant="primary", size="lg")

            summary_md = gr.Markdown("Click the button above to start the benchmark.")
            results_table = gr.Dataframe(
                headers=["ID", "Problem", "Category", "Difficulty", "Status", "Time(s)", "Error"],
                interactive=False,
            )

            with gr.Row():
                pass_chart = gr.Plot(label="Overall Results")
                cat_chart = gr.Plot(label="By Category")

            with gr.Row():
                diff_chart = gr.Plot(label="By Difficulty")

            run_btn.click(
                fn=run_full_benchmark,
                outputs=[results_table, summary_md, pass_chart, cat_chart, diff_chart],
            )

        # ── Tab 2: Single Problem ─────────────────────────────────
        with gr.Tab("Test Single Problem"):
            gr.Markdown("### Select and run a single problem")
            with gr.Row():
                problem_dd = gr.Dropdown(choices=PROBLEM_CHOICES, label="Problem", scale=3)
                single_btn = gr.Button("Solve", variant="primary", scale=1)

            single_status = gr.Markdown()

            with gr.Row():
                with gr.Column():
                    gr.Markdown("**Problem Prompt**")
                    prompt_box = gr.Textbox(label="Prompt", interactive=False, lines=6)
                with gr.Column():
                    gr.Markdown("**Kimi K2.5 Solution**")
                    code_box = gr.Code(language="python", label="Generated Code", interactive=False)

            test_box = gr.Code(language="python", label="Test Cases", interactive=False)

            single_btn.click(
                fn=run_single_problem,
                inputs=[problem_dd],
                outputs=[single_status, prompt_box, code_box, test_box],
            )

        # ── Tab 3: Analysis Chat ──────────────────────────────────
        with gr.Tab("AI Analysis"):
            gr.Markdown("""
### Benchmark Result Analyst (Kimi K2.5)
Ask about benchmark results, failure patterns, and model strengths/weaknesses.
*Run the benchmark first for meaningful analysis.*
            """)
            gr.ChatInterface(
                fn=chat_analysis,
                type="tuples",
                examples=[
                    "Summarize the benchmark results and key strengths of Kimi K2.5",
                    "Which problem categories does Kimi K2.5 struggle with and why?",
                    "How does performance degrade from Easy to Hard problems?",
                    "What types of bugs appear in failed solutions?",
                    "Compare Kimi K2.5's speed vs accuracy tradeoff",
                ],
                cache_examples=False,
            )

        # ── Tab 4: Problem Set ────────────────────────────────────
        with gr.Tab("Problem Set"):
            gr.Markdown(f"""
### Benchmark Problem Set
**{len(PROBLEMS)} problems** across **{len(CATEGORY_SET)} categories** | Easy: {DIFFICULTY_COUNTS['Easy']} · Medium: {DIFFICULTY_COUNTS['Medium']} · Hard: {DIFFICULTY_COUNTS['Hard']}
            """)
            prob_rows = []
            for p in PROBLEMS:
                prob_rows.append({
                    "ID": p["id"],
                    "Title": p["title"],
                    "Category": p["category"],
                    "Difficulty": p["difficulty"],
                    "Prompt Preview": p["prompt"][:100] + "...",
                })
            gr.Dataframe(pd.DataFrame(prob_rows), interactive=False)

    gr.Markdown("""
---
**FINAL-BENCH** | Kimi K2.5 via Fireworks AI | Real-time code generation + execution + test verification
    """)


if __name__ == "__main__":
    demo.launch()
