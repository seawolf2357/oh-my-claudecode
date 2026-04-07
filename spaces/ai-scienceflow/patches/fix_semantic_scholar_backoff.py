"""
Patch: Fix Semantic Scholar infinite backoff loop

Problem:
  The @backoff.on_exception decorator in semantic_scholar.py has no max_tries
  or max_time limit. When Semantic Scholar returns 429 (rate limit), the
  exponential backoff grows indefinitely (observed 1647+ seconds wait).

Fix:
  Add max_tries=5 and max_time=120 to both backoff decorators.
  Add a giveup handler that logs and returns gracefully on 429.

Apply to: ai_scientist/tools/semantic_scholar.py
"""

# --- BEFORE (line ~52-56, class method) ---
# @backoff.on_exception(
#     backoff.expo, requests.exceptions.HTTPError, on_backoff=on_backoff
# )
# def search(self, query, limit=10, ...):

# --- AFTER ---
# @backoff.on_exception(
#     backoff.expo, requests.exceptions.HTTPError, on_backoff=on_backoff,
#     max_tries=5, max_time=120,
#     giveup=lambda e: e.response is not None and e.response.status_code == 403
# )
# def search(self, query, limit=10, ...):


# --- BEFORE (line ~101-103, standalone function) ---
# @backoff.on_exception(
#     backoff.expo, requests.exceptions.HTTPError, on_backoff=on_backoff
# )
# def search_papers(query, ...):

# --- AFTER ---
# @backoff.on_exception(
#     backoff.expo, requests.exceptions.HTTPError, on_backoff=on_backoff,
#     max_tries=5, max_time=120,
#     giveup=lambda e: e.response is not None and e.response.status_code == 403
# )
# def search_papers(query, ...):


# Additionally, wrap callers to handle empty results gracefully:
# In perform_icbinb_writeup.py, gather_citations() should catch
# exceptions from search_papers and return "" instead of propagating.


def apply_patch(source_code: str) -> str:
    """Apply this patch to the semantic_scholar.py source code."""
    import re

    # Pattern: @backoff.on_exception(\n    backoff.expo, requests.exceptions.HTTPError, on_backoff=on_backoff\n)
    old_pattern = r'@backoff\.on_exception\(\s*\n\s*backoff\.expo,\s*requests\.exceptions\.HTTPError,\s*on_backoff=on_backoff\s*\n\s*\)'
    new_text = '''@backoff.on_exception(
    backoff.expo, requests.exceptions.HTTPError, on_backoff=on_backoff,
    max_tries=5, max_time=120,
    giveup=lambda e: e.response is not None and e.response.status_code == 403
)'''

    patched = re.sub(old_pattern, new_text, source_code)
    return patched


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python fix_semantic_scholar_backoff.py <path_to_semantic_scholar.py>")
        sys.exit(1)

    filepath = sys.argv[1]
    with open(filepath, 'r') as f:
        original = f.read()

    patched = apply_patch(original)

    if patched == original:
        print("WARNING: No changes applied. Pattern not found.")
        sys.exit(1)

    with open(filepath, 'w') as f:
        f.write(patched)

    count = original.count('@backoff.on_exception') - patched.count('@backoff.on_exception') + patched.count('max_tries=5')
    print(f"Patched {count} backoff decorator(s) with max_tries=5, max_time=120")
