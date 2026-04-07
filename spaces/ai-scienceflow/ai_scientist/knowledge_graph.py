"""
Optional Knowledge Graph integration for AI-Scientist.
Uses Zep Cloud GraphRAG when ZEP_API_KEY is available,
falls back to simple in-memory context otherwise.

Adapted from MiroFish's graph_builder.py and zep_tools.py patterns.
"""

import os
import json
from typing import Dict, Any, List, Optional


# Check if Zep is available
ZEP_AVAILABLE = False
try:
    if os.getenv("ZEP_API_KEY"):
        from zep_cloud.client import Zep
        ZEP_AVAILABLE = True
except ImportError:
    pass


class KnowledgeContext:
    """
    Lightweight knowledge context manager.
    If Zep is available, uses GraphRAG for semantic search.
    Otherwise, uses simple keyword-based context from experiment summaries.
    """

    def __init__(self, base_folder: str):
        self.base_folder = base_folder
        self.summaries = {}
        self.zep_client = None
        self._load_summaries()

        if ZEP_AVAILABLE:
            try:
                self.zep_client = Zep(api_key=os.getenv("ZEP_API_KEY"))
                print("[KnowledgeGraph] Zep Cloud connected")
            except Exception as e:
                print(f"[KnowledgeGraph] Zep connection failed, using fallback: {e}")
                self.zep_client = None

    def _load_summaries(self):
        """Load experiment summaries from disk."""
        logs_dir = os.path.join(self.base_folder, "logs", "0-run")
        for stage in ["draft_summary.json", "baseline_summary.json",
                       "research_summary.json", "ablation_summary.json"]:
            fpath = os.path.join(logs_dir, stage)
            if os.path.exists(fpath):
                try:
                    with open(fpath) as f:
                        self.summaries[stage.replace("_summary.json", "")] = json.load(f)
                except Exception:
                    pass

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search for relevant context.

        If Zep is available, uses semantic search.
        Otherwise, searches through experiment summaries.

        Returns:
            List of context snippets with relevance info.
        """
        if self.zep_client:
            return self._zep_search(query, limit)
        return self._fallback_search(query, limit)

    def _zep_search(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Search using Zep Cloud GraphRAG."""
        try:
            # Use Zep's graph search
            results = self.zep_client.graph.search(
                query=query,
                limit=limit,
            )
            return [
                {
                    "content": r.content if hasattr(r, 'content') else str(r),
                    "score": r.score if hasattr(r, 'score') else 0.0,
                    "source": "zep_graph",
                }
                for r in results
            ]
        except Exception as e:
            print(f"[KnowledgeGraph] Zep search failed: {e}")
            return self._fallback_search(query, limit)

    def _fallback_search(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Simple keyword search through experiment summaries."""
        results = []
        query_lower = query.lower()
        query_terms = query_lower.split()

        for stage_name, summary in self.summaries.items():
            text = json.dumps(summary, ensure_ascii=False)
            # Score by keyword overlap
            score = sum(1 for term in query_terms if term in text.lower())
            if score > 0:
                # Extract relevant snippet
                snippet = text[:500]
                results.append({
                    "content": f"[{stage_name}] {snippet}",
                    "score": score / len(query_terms),
                    "source": f"summary_{stage_name}",
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    def get_context_for_section(self, section_name: str) -> str:
        """Get relevant context for a paper section."""
        results = self.search(section_name, limit=3)
        if not results:
            return ""
        return "\n\n".join(r["content"][:500] for r in results)

    @property
    def is_graph_available(self) -> bool:
        """Check if full graph capabilities are available."""
        return self.zep_client is not None
