"""
AI Scientist v3 — FastAPI Backend
Autonomous Scientific Research Platform
"""
import asyncio
import gc
import json
import os
import os.path as osp
import queue
import re
import shutil
import signal
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

os.environ["AI_SCIENTIST_ROOT"] = os.path.dirname(os.path.abspath(__file__))
app = FastAPI(title="AI ScienceFlow")
app.mount("/static", StaticFiles(directory="static"), name="static")

# State
experiment_log_queue: queue.Queue = queue.Queue()
experiment_running = False
experiment_thread: Optional[threading.Thread] = None
current_ideas: list = []
uploaded_context: str = ""
uploaded_files_info: list = []

def _shutdown(sig, frame):
    gc.collect(); sys.exit(0)
signal.signal(signal.SIGTERM, _shutdown)
signal.signal(signal.SIGINT, _shutdown)


# ═══════════════════════════════════
# Pages
# ═══════════════════════════════════
@app.get("/", response_class=HTMLResponse)
async def index():
    return FileResponse("static/index.html")


# ═══════════════════════════════════
# Config API
# ═══════════════════════════════════
@app.get("/api/config")
async def get_config():
    return {
        "fireworks_key_set": bool(os.getenv("FIREWORKS_API_KEY")),
        "anthropic_key_set": bool(os.getenv("ANTHROPIC_API_KEY")),
        "openai_key_set": bool(os.getenv("OPENAI_API_KEY")),
    }

@app.post("/api/config")
async def set_config(data: dict):
    for k, env in {"fireworks_key":"FIREWORKS_API_KEY","anthropic_key":"ANTHROPIC_API_KEY","openai_key":"OPENAI_API_KEY"}.items():
        if k in data and data[k]:
            os.environ[env] = data[k].strip()
    return {"status": "ok"}


# ═══════════════════════════════════
# File Upload + Ontology
# ═══════════════════════════════════
@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    global uploaded_context
    upload_dir = Path("uploads"); upload_dir.mkdir(exist_ok=True)
    fpath = upload_dir / file.filename
    content = await file.read()
    fpath.write_bytes(content)

    text = ""
    fname = file.filename.lower()
    try:
        if fname.endswith(".pdf"):
            import pdfplumber
            with pdfplumber.open(str(fpath)) as pdf:
                text = "\n".join(p.extract_text() or "" for p in pdf.pages)
        elif fname.endswith(".csv"):
            import csv, io
            rows = list(csv.reader(io.StringIO(content.decode("utf-8", errors="ignore"))))
            text = "\n".join([", ".join(r) for r in rows[:200]])
        elif fname.endswith(".txt") or fname.endswith(".md"):
            text = content.decode("utf-8", errors="ignore")
        elif fname.endswith(".docx"):
            from docx import Document
            doc = Document(str(fpath))
            text = "\n".join(p.text for p in doc.paragraphs)
        else:
            text = content.decode("utf-8", errors="ignore")[:10000]
    except Exception as e:
        text = f"[Extract error: {e}]"

    uploaded_context = text[:20000]
    uploaded_files_info.append({"name": file.filename, "size": len(content), "text_len": len(text)})

    ontology = _generate_ontology(text[:6000])
    return {"filename": file.filename, "text_length": len(text), "preview": text[:500], "ontology": ontology}


def _fix_json(s: str) -> str:
    """Fix common JSON issues from LLM output."""
    # Remove trailing commas before } or ]
    s = re.sub(r',\s*([}\]])', r'\1', s)
    # Fix unescaped quotes inside strings (common LLM mistake)
    # Replace smart quotes with regular quotes
    s = s.replace('\u201c', '"').replace('\u201d', '"')
    s = s.replace('\u2018', "'").replace('\u2019', "'")
    # Remove control characters
    s = re.sub(r'[\x00-\x1f\x7f]', ' ', s)
    # Fix missing commas between objects: }{ -> },{
    s = re.sub(r'\}\s*\{', '},{', s)
    # Fix missing commas between strings: "..." "..." -> "...", "..."
    s = re.sub(r'"\s*\n\s*"', '",\n"', s)
    return s


def _generate_ontology(text: str) -> dict:
    try:
        from ai_scientist.llm import create_client, get_response_from_llm
        model_name = os.getenv("FIREWORKS_MODEL", "fireworks/accounts/fireworks/models/kimi-k2p5")
        client, model = create_client(model_name)
        prompt = f"""Extract a knowledge graph from the text below.
Return ONLY a JSON object with this exact structure (no other text):
{{"nodes":[{{"id":"n1","label":"Name","type":"concept"}}],"edges":[{{"source":"n1","target":"n2","label":"relation"}}]}}

Rules:
- type must be one of: person, org, concept, event, method
- id must be simple strings like n1, n2, n3...
- label must be short (under 30 chars), no special characters
- Extract 8-15 entities maximum
- All strings must use double quotes, no single quotes
- No trailing commas

Text:
{text[:3000]}"""
        response, _ = get_response_from_llm(prompt=prompt, client=client, model=model,
            system_message="Output ONLY valid JSON. No explanation, no markdown, no code fences.")
        # Strip <think> tags
        if '<think>' in response:
            response = re.sub(r'<think>[\s\S]*?</think>', '', response).strip()
        # Strip markdown fences
        response = re.sub(r'```(?:json)?\s*', '', response).strip()

        # Try parsing with progressive JSON fixing
        # Attempt 1: Find outermost { } and try direct parse
        depth = 0
        start = -1
        for i, c in enumerate(response):
            if c == '{':
                if depth == 0:
                    start = i
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0 and start >= 0:
                    candidate = response[start:i+1]
                    # Try direct parse
                    try:
                        result = json.loads(candidate)
                        if "nodes" in result:
                            print(f"[Ontology] OK: {len(result.get('nodes',[]))} nodes, {len(result.get('edges',[]))} edges")
                            return result
                    except json.JSONDecodeError:
                        pass
                    # Try with fixes
                    try:
                        fixed = _fix_json(candidate)
                        result = json.loads(fixed)
                        if "nodes" in result:
                            print(f"[Ontology] OK (fixed): {len(result.get('nodes',[]))} nodes, {len(result.get('edges',[]))} edges")
                            return result
                    except json.JSONDecodeError:
                        pass
                    # Try truncating at last valid point
                    for end in range(len(candidate) - 1, max(0, len(candidate) - 200), -1):
                        if candidate[end] == '}':
                            try:
                                truncated = candidate[:end+1]
                                result = json.loads(_fix_json(truncated))
                                if "nodes" in result:
                                    print(f"[Ontology] OK (truncated): {len(result.get('nodes',[]))} nodes")
                                    return result
                            except json.JSONDecodeError:
                                continue
                    start = -1  # Reset and try next outer block

        # Attempt 2: Build minimal valid JSON from what we can extract
        print("[Ontology] Direct parse failed, extracting nodes/edges manually...")
        nodes = []
        edges = []
        # Extract node-like objects
        for m in re.finditer(r'\{[^{}]*"id"\s*:\s*"([^"]+)"[^{}]*"label"\s*:\s*"([^"]+)"[^{}]*"type"\s*:\s*"([^"]+)"[^{}]*\}', response):
            nodes.append({"id": m.group(1), "label": m.group(2)[:30], "type": m.group(3)})
        for m in re.finditer(r'\{[^{}]*"source"\s*:\s*"([^"]+)"[^{}]*"target"\s*:\s*"([^"]+)"[^{}]*"label"\s*:\s*"([^"]+)"[^{}]*\}', response):
            edges.append({"source": m.group(1), "target": m.group(2), "label": m.group(3)[:30]})
        if nodes:
            print(f"[Ontology] Extracted manually: {len(nodes)} nodes, {len(edges)} edges")
            return {"nodes": nodes, "edges": edges}

        print(f"[Ontology] Failed to parse. Response preview: {response[:300]}")
    except Exception as e:
        print(f"[Ontology] Error: {e}")
    return {"nodes": [], "edges": []}


# ═══════════════════════════════════
# Ideation API
# ═══════════════════════════════════
@app.post("/api/ideation")
async def generate_ideas(data: dict):
    topic = data.get("topic", "")
    model = data.get("model", "fireworks/accounts/fireworks/models/kimi-k2p5")
    max_ideas = data.get("max_ideas", 3)

    if not topic.strip():
        return {"error": "Topic required"}
    try:
        from ai_scientist.llm import create_client, get_response_from_llm
        client, client_model = create_client(model)

        ctx = f"\n\nReference Materials:\n{uploaded_context[:4000]}\n" if uploaded_context else ""
        prompt = f"""Generate {max_ideas} novel research ideas on: {topic}{ctx}
For each idea provide: Name, Title, Short Hypothesis, Abstract, Experiments (list), Risk Factors and Limitations (list).
Return as JSON array."""

        response, _ = get_response_from_llm(prompt=prompt, client=client, model=client_model,
            system_message="You are an AI researcher. Return valid JSON array of research ideas.")

        m = re.search(r'\[[\s\S]*\]', response)
        ideas = json.loads(m.group()) if m else []
        if not ideas:
            m2 = re.search(r'\{[\s\S]*\}', response)
            ideas = [json.loads(m2.group())] if m2 else []

        global current_ideas
        current_ideas = ideas

        # Generate ontology from ideas for visualization
        ontology = {"nodes": [], "edges": []}
        try:
            ideas_text = json.dumps(ideas, ensure_ascii=False)[:6000]
            ontology = _generate_ontology(ideas_text)
        except Exception as oe:
            print(f"[Ideation Ontology] {oe}")

        return {"ideas": ideas, "count": len(ideas), "ontology": ontology}
    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════════════
# Experiments API
# ═══════════════════════════════════
@app.post("/api/experiments/start")
async def start_experiment(data: dict):
    global experiment_thread, experiment_running
    if experiment_running:
        return {"error": "Already running"}

    ideas_json = data.get("ideas_json", "")
    model = data.get("model", "fireworks/accounts/fireworks/models/kimi-k2p5")
    skip_writeup = data.get("skip_writeup", False)
    skip_review = data.get("skip_review", False)
    num_cite = data.get("num_cite_rounds", 3)

    if not ideas_json:
        return {"error": "No ideas"}

    while not experiment_log_queue.empty():
        try: experiment_log_queue.get_nowait()
        except queue.Empty: break

    experiment_thread = threading.Thread(
        target=_run_pipeline, args=(ideas_json, model, num_cite, skip_writeup, skip_review), daemon=True)
    experiment_thread.start()
    return {"status": "started"}


def _run_pipeline(ideas_json_text, model, num_cite, skip_writeup, skip_review):
    global experiment_running
    experiment_running = True
    try:
        experiment_log_queue.put("[INFO] Starting pipeline...")
        ideas = json.loads(ideas_json_text)
        if isinstance(ideas, dict): ideas = [ideas]
        idea = ideas[0]

        for key, default in {"Title": idea.get("Name","Untitled"), "Abstract": idea.get("Title",""),
            "Short Hypothesis": idea.get("Short_Hypothesis", idea.get("Title","")),
            "Experiments": ["Baseline"], "Risk Factors and Limitations": ["Computational constraints"]}.items():
            if key not in idea: idea[key] = default

        if uploaded_context and "Code" not in idea:
            idea["Code"] = f"# Reference:\n# {uploaded_context[:2000]}"

        date = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        name = idea.get("Name", "unnamed")
        idea_dir = f"experiments/{date}_{name}_attempt_0"
        os.makedirs(idea_dir, exist_ok=True)
        experiment_log_queue.put(f"[INFO] Dir: {idea_dir}")

        idea_json_path = osp.join(idea_dir, "idea.json")
        with open(idea_json_path, "w") as f: json.dump(idea, f, indent=4)

        from ai_scientist.treesearch.bfts_utils import idea_to_markdown, edit_bfts_config_file
        idea_to_markdown(idea, osp.join(idea_dir, "idea.md"), None)

        if not os.path.exists("bfts_config.yaml"):
            experiment_log_queue.put("[ERROR] bfts_config.yaml missing"); return

        cfg_path = edit_bfts_config_file("bfts_config.yaml", idea_dir, idea_json_path)
        experiment_log_queue.put("[INFO] Tree search starting...")

        from ai_scientist.treesearch.perform_experiments_bfts_with_agentmanager import perform_experiments_bfts
        perform_experiments_bfts(cfg_path)
        experiment_log_queue.put("[INFO] Experiments done!")
        gc.collect()

        # Upload intermediate
        try:
            _upload_hf(idea_dir, name, date)
            experiment_log_queue.put("[INFO] Intermediate results saved to HF")
        except Exception as e:
            experiment_log_queue.put(f"[WARN] HF upload: {e}")

        # Plot aggregation
        gc.collect()
        experiment_log_queue.put("[INFO] Aggregating plots...")
        res_dir = osp.join(idea_dir, "logs/0-run/experiment_results")
        if os.path.exists(res_dir):
            shutil.copytree(res_dir, osp.join(idea_dir, "experiment_results"), dirs_exist_ok=True)
        from ai_scientist.perform_plotting import aggregate_plots
        aggregate_plots(base_folder=idea_dir, model=model)
        if os.path.exists(osp.join(idea_dir, "experiment_results")):
            shutil.rmtree(osp.join(idea_dir, "experiment_results"))

        # Writeup
        if not skip_writeup:
            gc.collect()
            experiment_log_queue.put("[INFO] Writing paper...")
            from ai_scientist.perform_icbinb_writeup import perform_writeup as do_writeup, gather_citations
            cites = gather_citations(idea_dir, num_cite, model)
            do_writeup(idea_dir, big_model=model, small_model=model, citations_text=cites or "")
            experiment_log_queue.put("[INFO] Writeup done!")

        # Review
        if not skip_review:
            experiment_log_queue.put("[INFO] Reviewing...")
            try:
                from ai_scientist.perform_review import perform_review, load_paper
                from ai_scientist.llm import create_client
                pdf = [f for f in Path(idea_dir).glob("*.pdf")]
                if pdf:
                    paper = load_paper(str(pdf[0]))
                    c, m = create_client(model)
                    review = perform_review(paper, m, c)
                    with open(osp.join(idea_dir, "review_text.txt"), "w") as f:
                        f.write(json.dumps(review, indent=4))
                    experiment_log_queue.put("[INFO] Review done!")
            except Exception as e:
                experiment_log_queue.put(f"[WARN] Review: {e}")

        # Final upload
        try:
            _upload_hf(idea_dir, name, date)
        except Exception: pass

        experiment_log_queue.put(f"[DONE] Complete! {idea_dir}")
    except Exception as e:
        experiment_log_queue.put(f"[ERROR] {e}\n{traceback.format_exc()}")
    finally:
        experiment_running = False; gc.collect()


def _upload_hf(idea_dir, name, date):
    from huggingface_hub import HfApi
    token = os.getenv("HF_TOKEN", "")
    if not token: return
    api = HfApi(token=token)
    repo = "SeaWolf-AI/ai-scientist-results"
    try: api.create_repo(repo_id=repo, repo_type="dataset", private=True, exist_ok=True)
    except: pass
    api.upload_folder(folder_path=idea_dir, path_in_repo=f"{date}_{name}", repo_id=repo, repo_type="dataset",
        commit_message=f"Experiment: {name} ({date})")


@app.get("/api/experiments/status")
async def exp_status():
    logs = []
    while not experiment_log_queue.empty():
        try: logs.append(experiment_log_queue.get_nowait())
        except queue.Empty: break
    return {"running": experiment_running, "logs": logs}

@app.get("/api/experiments/list")
async def exp_list():
    d = Path("experiments")
    return {"experiments": sorted([x.name for x in d.iterdir() if x.is_dir()], reverse=True) if d.exists() else []}


# ═══════════════════════════════════
# Results API
# ═══════════════════════════════════
@app.get("/api/results/{exp}")
async def get_results(exp: str):
    d = Path("experiments") / exp
    if not d.exists(): return {"error": "Not found"}
    r = {"name": exp, "figures": [], "summary": {}, "pdf": None, "review": None}
    fig = d / "figures"
    if fig.exists():
        r["figures"] = [f"/api/results/{exp}/figure/{f.name}" for f in fig.glob("*.png")]
    logs = d / "logs" / "0-run"
    for s in ["draft","baseline","research","ablation"]:
        fp = logs / f"{s}_summary.json"
        if fp.exists():
            try: r["summary"][s] = json.loads(fp.read_text())
            except: pass
    for f in d.glob("*.pdf"): r["pdf"] = f"/api/results/{exp}/pdf/{f.name}"; break
    rev = d / "review_text.txt"
    if rev.exists(): r["review"] = rev.read_text()[:5000]
    return r

@app.get("/api/results/{exp}/figure/{fname}")
async def get_fig(exp: str, fname: str):
    p = Path("experiments")/exp/"figures"/fname
    return FileResponse(str(p)) if p.exists() else JSONResponse({"error":"not found"}, 404)

@app.get("/api/results/{exp}/pdf/{fname}")
async def get_pdf(exp: str, fname: str):
    p = Path("experiments")/exp/fname
    return FileResponse(str(p), media_type="application/pdf") if p.exists() else JSONResponse({"error":"not found"}, 404)


# ═══════════════════════════════════
# WebSocket logs
# ═══════════════════════════════════
@app.websocket("/ws/logs")
async def ws_logs(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            logs = []
            while not experiment_log_queue.empty():
                try: logs.append(experiment_log_queue.get_nowait())
                except queue.Empty: break
            await ws.send_json({"logs": logs, "running": experiment_running})
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass


# ═══════════════════════════════════
if __name__ == "__main__":
    for d in ["uploads","experiments","static"]: os.makedirs(d, exist_ok=True)
    uvicorn.run(app, host="0.0.0.0", port=7860)
