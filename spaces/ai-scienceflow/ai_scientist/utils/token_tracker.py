"""Token usage tracking utility for AI-Scientist LLM calls."""

import functools
import time
from typing import Dict, Any

# Global token tracker
_token_counts: Dict[str, int] = {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
    "calls": 0,
}


class TokenTracker:
    """Simple token usage tracker."""

    def __init__(self):
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.calls = 0

    def update(self, response):
        """Update token counts from an API response."""
        try:
            if hasattr(response, 'usage') and response.usage:
                self.prompt_tokens += getattr(response.usage, 'prompt_tokens', 0) or 0
                self.completion_tokens += getattr(response.usage, 'completion_tokens', 0) or 0
                self.total_tokens += getattr(response.usage, 'total_tokens', 0) or 0
            self.calls += 1
        except Exception:
            self.calls += 1

    def get_summary(self) -> Dict[str, int]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "calls": self.calls,
        }

    def __str__(self):
        return (
            f"Tokens - Prompt: {self.prompt_tokens}, "
            f"Completion: {self.completion_tokens}, "
            f"Total: {self.total_tokens}, "
            f"Calls: {self.calls}"
        )


# Global instance
token_tracker = TokenTracker()


def track_token_usage(func):
    """Decorator to track token usage from LLM API calls."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        try:
            if result is not None:
                token_tracker.update(result)
        except Exception:
            pass
        return result
    return wrapper
