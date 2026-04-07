"""
Brave Search integration for AI ScienceFlow.

Provides web search as fallback when Semantic Scholar hits rate limits,
and bulk keyword search for comprehensive literature discovery.

Requires BRAVE_API_KEY environment variable.
Free tier: 2,000 requests/month, 1 req/sec.
"""

import os
import re
import json
import time
import requests
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed


BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "")
BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
_last_call_time = 0.0


def _rate_limit():
    """Enforce 1 req/sec for Brave free tier."""
    global _last_call_time
    elapsed = time.time() - _last_call_time
    if elapsed < 1.1:
        time.sleep(1.1 - elapsed)
    _last_call_time = time.time()


def brave_search(query: str, count: int = 5) -> List[Dict]:
    """
    Search Brave and return results.

    Returns list of dicts with keys: title, url, description, age
    """
    if not BRAVE_API_KEY:
        return []

    _rate_limit()

    try:
        resp = requests.get(
            BRAVE_ENDPOINT,
            headers={
                "X-Subscription-Token": BRAVE_API_KEY,
                "Accept": "application/json",
            },
            params={"q": query, "count": count},
            timeout=10,
        )
        if resp.status_code == 429:
            print(f"[BraveSearch] Rate limited, waiting 2s...")
            time.sleep(2)
            return []
        resp.raise_for_status()
        data = resp.json()

        results = []
        for item in data.get("web", {}).get("results", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "description": item.get("description", ""),
                "age": item.get("age", ""),
            })
        return results
    except Exception as e:
        print(f"[BraveSearch] Error: {e}")
        return []


def brave_search_papers(query: str, count: int = 5) -> List[Dict]:
    """
    Search for academic papers via Brave, targeting arxiv/scholar sites.

    Returns results formatted like Semantic Scholar output for compatibility.
    """
    # Target academic sources
    academic_query = f"site:arxiv.org OR site:scholar.google.com OR site:semanticscholar.org {query}"
    results = brave_search(academic_query, count=count)

    papers = []
    for r in results:
        # Extract year from URL or description
        year_match = re.search(r'20[12]\d', r.get("url", "") + r.get("description", ""))
        year = int(year_match.group()) if year_match else None

        # Extract arxiv ID if present
        arxiv_match = re.search(r'(\d{4}\.\d{4,5})', r.get("url", ""))
        paper_id = arxiv_match.group(1) if arxiv_match else r.get("url", "")[:50]

        papers.append({
            "title": r["title"],
            "authors": [],  # Brave doesn't provide structured authors
            "venue": "arXiv" if "arxiv" in r.get("url", "") else "Web",
            "year": year,
            "abstract": r.get("description", ""),
            "citationCount": 0,
            "paperId": paper_id,
            "url": r.get("url", ""),
            "source": "brave_search",
        })
    return papers


def generate_search_keywords(topic: str, num_keywords: int = 100) -> List[str]:
    """
    Generate expanded search keywords from a research topic using LLM.

    Returns a list of diverse search queries covering:
    - Core concepts, methods, datasets
    - Related work, competing approaches
    - Key authors and papers
    - Application domains
    """
    try:
        from ai_scientist.llm import create_client, get_response_from_llm
        model_name = os.getenv("FIREWORKS_MODEL", "fireworks/accounts/fireworks/models/kimi-k2p5")
        client, model = create_client(model_name)

        prompt = f"""Generate exactly {num_keywords} diverse academic search queries for this research topic.
Cover: core methods, related work, key papers, datasets, competing approaches, application domains, foundational theories.
Each query should be 3-8 words, optimized for finding relevant papers.

Topic: {topic}

Return as JSON array of strings. Example:
["evolutionary model merging survey", "neural architecture search fitness landscape", ...]
Return ONLY the JSON array."""

        response, _ = get_response_from_llm(
            prompt=prompt, client=client, model=model,
            system_message="You are a research librarian. Output only a JSON array of search queries.",
        )

        # Strip <think> tags
        if '<think>' in response:
            response = re.sub(r'<think>[\s\S]*?</think>', '', response).strip()

        # Extract JSON array
        m = re.search(r'\[[\s\S]*\]', response)
        if m:
            keywords = json.loads(m.group())
            if isinstance(keywords, list):
                return [str(k).strip() for k in keywords if k][:num_keywords]
    except Exception as e:
        print(f"[KeywordGen] Error: {e}")

    # Fallback: basic keyword expansion
    words = topic.split()
    fallback = [topic]
    if len(words) > 3:
        fallback.extend([" ".join(words[i:i+3]) for i in range(len(words)-2)])
    fallback.extend([f"{topic} survey", f"{topic} benchmark", f"{topic} recent advances"])
    return fallback[:num_keywords]


def bulk_search(
    keywords: List[str],
    max_workers: int = 3,
    results_per_query: int = 3,
    max_total: int = 200,
) -> List[Dict]:
    """
    Search multiple keywords in parallel (respecting rate limits).

    Args:
        keywords: List of search queries
        max_workers: Parallel threads (kept low for rate limiting)
        results_per_query: Results per individual search
        max_total: Maximum total results to return

    Returns:
        Deduplicated list of paper results
    """
    if not BRAVE_API_KEY:
        print("[BraveSearch] No BRAVE_API_KEY set, skipping bulk search")
        return []

    all_results = []
    seen_titles = set()

    print(f"[BraveSearch] Searching {len(keywords)} keywords...")

    # Sequential with rate limiting (Brave free tier = 1 req/sec)
    for i, kw in enumerate(keywords):
        if len(all_results) >= max_total:
            break

        papers = brave_search_papers(kw, count=results_per_query)
        for p in papers:
            title_lower = p["title"].lower().strip()
            if title_lower not in seen_titles and len(all_results) < max_total:
                seen_titles.add(title_lower)
                p["search_query"] = kw
                all_results.append(p)

        if (i + 1) % 10 == 0:
            print(f"[BraveSearch] Progress: {i+1}/{len(keywords)} queries, {len(all_results)} unique results")

    print(f"[BraveSearch] Complete: {len(all_results)} unique results from {len(keywords)} queries")
    return all_results


def search_with_fallback(query: str, result_limit: int = 10) -> Optional[List[Dict]]:
    """
    Try Semantic Scholar first, fall back to Brave Search.

    This is the main entry point that replaces direct S2 calls.
    """
    # Try Semantic Scholar first
    try:
        from ai_scientist.tools.semantic_scholar import search_for_papers
        papers = search_for_papers(query, result_limit=result_limit)
        if papers:
            return papers
    except Exception as e:
        print(f"[SearchFallback] S2 failed: {e}")

    # Fallback to Brave Search
    if BRAVE_API_KEY:
        print(f"[SearchFallback] Using Brave Search for: {query[:60]}...")
        papers = brave_search_papers(query, count=result_limit)
        if papers:
            return papers

    return None


def comprehensive_literature_search(topic: str, num_keywords: int = 50) -> Dict:
    """
    Full literature search pipeline:
    1. Generate expanded keywords from topic
    2. Bulk search all keywords via Brave
    3. Deduplicate and rank results

    Returns dict with 'papers', 'keywords_used', 'stats'
    """
    keywords = generate_search_keywords(topic, num_keywords=num_keywords)
    papers = bulk_search(keywords, results_per_query=3, max_total=200)

    # Sort by presence of arxiv (higher quality)
    papers.sort(key=lambda p: (
        1 if "arxiv" in p.get("url", "") else 0,
        p.get("year") or 0,
    ), reverse=True)

    return {
        "papers": papers,
        "keywords_used": keywords,
        "stats": {
            "total_keywords": len(keywords),
            "total_results": len(papers),
            "arxiv_papers": sum(1 for p in papers if "arxiv" in p.get("url", "")),
        },
    }
