"""LLM-based paper review module for AI-Scientist."""

import os
import json
import re
from typing import Any, Dict, Optional

import pymupdf


def load_paper(pdf_path: str) -> str:
    """
    Load a PDF paper and extract its text content as markdown-like text.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Extracted text content from the PDF.
    """
    if not os.path.exists(pdf_path):
        return ""

    try:
        doc = pymupdf.open(pdf_path)
        text_parts = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text")
            if text.strip():
                text_parts.append(f"--- Page {page_num + 1} ---\n{text}")
        doc.close()
        return "\n\n".join(text_parts)
    except Exception as e:
        print(f"Error loading paper from {pdf_path}: {e}")
        return ""


def perform_review(
    paper_text: str,
    model: str,
    client: Any,
    num_reflections: int = 1,
) -> Dict[str, Any]:
    """
    Perform an automated review of a paper.

    Args:
        paper_text: The extracted text of the paper.
        model: LLM model identifier.
        client: LLM client instance.
        num_reflections: Number of review refinement rounds.

    Returns:
        Dictionary containing review scores and text.
    """
    from ai_scientist.llm import get_response_from_llm

    review_system_prompt = (
        "You are an AI researcher acting as a reviewer for a machine learning workshop paper. "
        "Be critical but constructive. Evaluate the paper on: "
        "1) Novelty and significance, 2) Clarity and writing quality, "
        "3) Experimental methodology, 4) Results and conclusions, "
        "5) Overall recommendation."
    )

    review_prompt = f"""Please review the following paper and provide your assessment.

Paper text:
{paper_text[:15000]}

Respond in the following JSON format:
```json
{{
    "Summary": "Brief summary of the paper",
    "Strengths": ["strength 1", "strength 2", ...],
    "Weaknesses": ["weakness 1", "weakness 2", ...],
    "Questions": ["question 1", "question 2", ...],
    "Soundness": <1-4 score>,
    "Presentation": <1-4 score>,
    "Contribution": <1-4 score>,
    "Overall": <1-10 score>,
    "Confidence": <1-5 score>,
    "Decision": "Accept/Reject/Weak Accept/Weak Reject"
}}
```"""

    try:
        response, _ = get_response_from_llm(
            prompt=review_prompt,
            client=client,
            model=model,
            system_message=review_system_prompt,
        )

        # Extract JSON from response
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            review = json.loads(json_match.group(1))
        else:
            # Try to parse the whole response as JSON
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                review = json.loads(json_match.group())
            else:
                review = {
                    "Summary": response[:500],
                    "Overall": 5,
                    "Decision": "Cannot parse",
                    "raw_response": response,
                }

        return review

    except Exception as e:
        print(f"Error performing review: {e}")
        return {
            "Summary": f"Review failed: {str(e)}",
            "Overall": 0,
            "Decision": "Error",
        }
