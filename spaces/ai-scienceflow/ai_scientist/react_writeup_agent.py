"""
ReACT Writeup Agent for AI-Scientist
Adapted from MiroFish's ReACT Report Agent pattern.

Uses Thought → Action → Observation loops to iteratively
search for citations, validate figures, and refine paper sections.
"""

import json
import re
import os
import traceback
from typing import Dict, Any, List, Optional, Callable

from ai_scientist.llm import get_response_from_llm, create_client
from ai_scientist.tools.semantic_scholar import search_for_papers
from ai_scientist.tools.brave_search import search_with_fallback


# ── Tool Definitions ──

TOOLS_DESCRIPTION = """Available tools:

1. **search_papers**: Search for academic papers on Semantic Scholar.
   Usage: <tool_call>{"tool": "search_papers", "query": "your search query"}</tool_call>
   Returns: List of papers with titles, authors, venue, year, citation count, and abstracts.

2. **check_figures**: List available figure files in the figures/ directory.
   Usage: <tool_call>{"tool": "check_figures"}</tool_call>
   Returns: List of figure filenames with descriptions.

3. **read_summary**: Read experiment summary data (draft, baseline, research, or ablation).
   Usage: <tool_call>{"tool": "read_summary", "stage": "draft|baseline|research|ablation"}</tool_call>
   Returns: JSON summary of the specified experiment stage.

4. **search_knowledge**: Search the knowledge graph for relevant experimental context.
   Usage: <tool_call>{"tool": "search_knowledge", "query": "your search query"}</tool_call>
   Returns: Relevant context snippets from experiment data and knowledge graph.
"""

REACT_SYSTEM_PROMPT = """You are an expert AI research paper writer using the ReACT (Reasoning-Action-Thinking) framework.

Your task is to write a section of a scientific paper. Before writing, you MUST gather information using the available tools.

## ReACT Protocol
Each response should follow ONE of these patterns:

**Pattern A - Tool Call (gather information):**
Thought: [Your reasoning about what information you need]
Action: I will search for relevant papers to cite.
<tool_call>{{"tool": "search_papers", "query": "your query"}}</tool_call>

**Pattern B - Final Answer (write the section):**
Thought: I have gathered enough information. Let me write the section.
Final Answer:
[Your LaTeX content here]

## Rules
1. You MUST call at least 2 tools before writing Final Answer.
2. Each response should contain EITHER a tool call OR a Final Answer, never both.
3. Use gathered information (paper citations, figure references, data) in your writing.
4. Write in LaTeX format suitable for an academic paper.
5. Include \\cite{{}} commands for papers you found via search_papers.

{tools_description}
"""

REACT_USER_PROMPT = """Write the following section of the paper:

## Section: {section_name}

## Paper Context:
Title: {paper_title}
Abstract: {paper_abstract}

## Experiment Summaries:
{summaries_brief}

## Available Figures:
{figure_list}

## Previous Sections Written:
{previous_sections}

Please start by searching for relevant papers to cite, then write the section.
"""

REACT_INSUFFICIENT_TOOLS = (
    "You have only used {count} tool(s) so far. "
    "Please use at least {min_calls} tools before writing your Final Answer. "
    "Try searching for more relevant papers or checking the figures."
)

REACT_TOOL_LIMIT = (
    "You have used {count}/{max_calls} tool calls. "
    "No more tool calls allowed. Please write your Final Answer now."
)


def _parse_tool_calls(response: str) -> List[Dict[str, Any]]:
    """Parse <tool_call>...</tool_call> blocks from LLM response."""
    pattern = r'<tool_call>(.*?)</tool_call>'
    matches = re.findall(pattern, response, re.DOTALL)
    calls = []
    for match in matches:
        try:
            call = json.loads(match.strip())
            calls.append(call)
        except json.JSONDecodeError:
            continue
    return calls


def _execute_tool(call: Dict[str, Any], base_folder: str, summaries: Dict) -> str:
    """Execute a tool call and return the observation."""
    tool_name = call.get("tool", "")

    if tool_name == "search_papers":
        query = call.get("query", "")
        if not query:
            return "Error: No query provided."
        try:
            # S2 with Brave fallback
            papers = search_with_fallback(query, result_limit=3)
            if not papers:
                return f"No papers found for query: {query}"
            results = []
            for p in papers:
                authors = ", ".join([a.get("name", "") for a in p.get("authors", [])[:3]])
                cite_key = re.sub(r'[^a-zA-Z0-9]', '', p.get("paperId", "")[:12])
                results.append(
                    f"- {p.get('title', 'Unknown')} ({p.get('year', 'N/A')})\n"
                    f"  Authors: {authors}\n"
                    f"  Venue: {p.get('venue', 'N/A')}\n"
                    f"  Citations: {p.get('citationCount', 0)}\n"
                    f"  Cite key: {cite_key}\n"
                    f"  Abstract: {(p.get('abstract') or 'N/A')[:200]}..."
                )
            return "\n".join(results)
        except Exception as e:
            return f"Search failed: {str(e)}"

    elif tool_name == "check_figures":
        figures_dir = os.path.join(base_folder, "figures")
        if not os.path.exists(figures_dir):
            return "No figures directory found."
        figs = [f for f in os.listdir(figures_dir) if f.endswith(".png")]
        if not figs:
            return "No PNG figures found."
        return "Available figures:\n" + "\n".join(f"- {f}" for f in sorted(figs))

    elif tool_name == "read_summary":
        stage = call.get("stage", "draft")
        stage_map = {
            "draft": "draft_summary.json",
            "baseline": "baseline_summary.json",
            "research": "research_summary.json",
            "ablation": "ablation_summary.json",
        }
        fname = stage_map.get(stage, "draft_summary.json")
        fpath = os.path.join(base_folder, "logs", "0-run", fname)
        if not os.path.exists(fpath):
            return f"Summary file not found: {fname}"
        try:
            with open(fpath) as f:
                data = json.load(f)
            # Truncate to avoid huge context
            text = json.dumps(data, indent=2, ensure_ascii=False)
            if len(text) > 3000:
                text = text[:3000] + "\n... (truncated)"
            return text
        except Exception as e:
            return f"Error reading summary: {e}"

    elif tool_name == "search_knowledge":
        query = call.get("query", "")
        if not query:
            return "Error: No query provided."
        try:
            from ai_scientist.knowledge_graph import KnowledgeContext
            kg = KnowledgeContext(base_folder)
            results = kg.search(query, limit=3)
            if not results:
                return f"No knowledge found for: {query}"
            return "\n\n".join(
                f"[Score: {r['score']:.2f}] {r['content'][:500]}"
                for r in results
            )
        except Exception as e:
            return f"Knowledge search failed: {e}"

    else:
        return f"Unknown tool: {tool_name}"


def react_write_section(
    section_name: str,
    paper_title: str,
    paper_abstract: str,
    summaries_brief: str,
    figure_list: str,
    previous_sections: str,
    base_folder: str,
    summaries: Dict,
    client: Any,
    model: str,
    max_iterations: int = 6,
    min_tool_calls: int = 2,
    max_tool_calls: int = 4,
) -> str:
    """
    Write a paper section using ReACT pattern.

    Returns:
        LaTeX content for the section.
    """
    system_prompt = REACT_SYSTEM_PROMPT.format(tools_description=TOOLS_DESCRIPTION)
    user_prompt = REACT_USER_PROMPT.format(
        section_name=section_name,
        paper_title=paper_title,
        paper_abstract=paper_abstract,
        summaries_brief=summaries_brief[:4000],
        figure_list=figure_list,
        previous_sections=previous_sections[:3000] if previous_sections else "(First section)",
    )

    msg_history = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    tool_calls_count = 0

    for iteration in range(max_iterations):
        try:
            # Call LLM
            response = client.chat.completions.create(
                model=model,
                messages=msg_history,
                temperature=0.5,
                max_tokens=4096,
            )
            content = response.choices[0].message.content
            if not content:
                continue

            # Strip <think> tags
            if '<think>' in content:
                content = re.sub(r'<think>[\s\S]*?</think>', '', content).strip()

        except Exception as e:
            print(f"[ReACT] LLM call failed at iteration {iteration}: {e}")
            continue

        # Parse response
        tool_calls = _parse_tool_calls(content)
        has_tool_calls = bool(tool_calls)
        has_final_answer = "Final Answer:" in content

        # Conflict: both tool call and final answer
        if has_tool_calls and has_final_answer:
            msg_history.append({"role": "assistant", "content": content})
            msg_history.append({
                "role": "user",
                "content": (
                    "Format error: You included both a tool call and Final Answer in one response. "
                    "Please respond with ONLY one: either a <tool_call> OR a Final Answer."
                ),
            })
            continue

        # Case 1: Final Answer
        if has_final_answer:
            if tool_calls_count < min_tool_calls:
                msg_history.append({"role": "assistant", "content": content})
                msg_history.append({
                    "role": "user",
                    "content": REACT_INSUFFICIENT_TOOLS.format(
                        count=tool_calls_count, min_calls=min_tool_calls
                    ),
                })
                continue

            final_answer = content.split("Final Answer:")[-1].strip()
            print(f"[ReACT] Section '{section_name}' done after {tool_calls_count} tool calls")
            return final_answer

        # Case 2: Tool call
        if has_tool_calls:
            if tool_calls_count >= max_tool_calls:
                msg_history.append({"role": "assistant", "content": content})
                msg_history.append({
                    "role": "user",
                    "content": REACT_TOOL_LIMIT.format(
                        count=tool_calls_count, max_calls=max_tool_calls
                    ),
                })
                continue

            # Execute first tool call
            call = tool_calls[0]
            tool_name = call.get("tool", "unknown")
            print(f"[ReACT] Iteration {iteration+1}: calling tool '{tool_name}'")

            observation = _execute_tool(call, base_folder, summaries)
            tool_calls_count += 1

            msg_history.append({"role": "assistant", "content": content})
            msg_history.append({
                "role": "user",
                "content": f"Observation from {tool_name}:\n{observation}\n\n"
                           f"Tool calls used: {tool_calls_count}/{max_tool_calls}. "
                           f"Continue with another tool call or write your Final Answer.",
            })
            continue

        # Case 3: No tool call and no final answer — nudge
        msg_history.append({"role": "assistant", "content": content})
        msg_history.append({
            "role": "user",
            "content": (
                "Please either call a tool using <tool_call> or write your Final Answer. "
                "Remember to follow the ReACT format."
            ),
        })

    # Fallback: force final answer
    print(f"[ReACT] Section '{section_name}' reached max iterations, forcing output")
    msg_history.append({
        "role": "user",
        "content": "Maximum iterations reached. Please write your Final Answer NOW based on all information gathered so far.",
    })
    try:
        response = client.chat.completions.create(
            model=model,
            messages=msg_history,
            temperature=0.5,
            max_tokens=4096,
        )
        content = response.choices[0].message.content or ""
        if '<think>' in content:
            content = re.sub(r'<think>[\s\S]*?</think>', '', content).strip()
        if "Final Answer:" in content:
            return content.split("Final Answer:")[-1].strip()
        return content
    except Exception:
        return f"% ReACT agent failed to generate section: {section_name}\n"


def react_enhance_writeup(
    base_folder: str,
    paper_title: str,
    paper_abstract: str,
    model: str = "fireworks/accounts/fireworks/models/kimi-k2p5",
    sections: Optional[List[str]] = None,
) -> Dict[str, str]:
    """
    Generate paper sections using ReACT agent.

    Args:
        base_folder: Path to experiment directory
        paper_title: Title of the paper
        paper_abstract: Abstract text
        model: LLM model identifier
        sections: List of section names to generate

    Returns:
        Dict mapping section names to LaTeX content
    """
    if sections is None:
        sections = [
            "Introduction",
            "Related Work",
            "Methodology",
            "Experiments",
            "Results and Discussion",
            "Conclusion",
        ]

    # Load summaries
    summaries = {}
    logs_dir = os.path.join(base_folder, "logs", "0-run")
    for stage in ["draft_summary.json", "baseline_summary.json", "research_summary.json", "ablation_summary.json"]:
        fpath = os.path.join(logs_dir, stage)
        if os.path.exists(fpath):
            try:
                with open(fpath) as f:
                    summaries[stage] = json.load(f)
            except Exception:
                pass

    summaries_brief = json.dumps(summaries, indent=2, ensure_ascii=False)[:4000]

    # List figures
    figures_dir = os.path.join(base_folder, "figures")
    figure_list = ""
    if os.path.exists(figures_dir):
        figs = sorted([f for f in os.listdir(figures_dir) if f.endswith(".png")])
        figure_list = ", ".join(figs) if figs else "No figures available"

    # Create LLM client
    client, client_model = create_client(model)

    # Generate each section
    results = {}
    previous_sections = ""
    for section_name in sections:
        print(f"[ReACT] Generating section: {section_name}")
        try:
            content = react_write_section(
                section_name=section_name,
                paper_title=paper_title,
                paper_abstract=paper_abstract,
                summaries_brief=summaries_brief,
                figure_list=figure_list,
                previous_sections=previous_sections,
                base_folder=base_folder,
                summaries=summaries,
                client=client,
                model=client_model,
            )
            results[section_name] = content
            previous_sections += f"\n\n\\section{{{section_name}}}\n{content}"
        except Exception as e:
            print(f"[ReACT] Failed to generate section '{section_name}': {e}")
            traceback.print_exc()
            results[section_name] = f"% Section generation failed: {e}\n"

    return results
