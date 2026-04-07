"""
Patch: Fix plot aggregation SyntaxError from markdown fences in LLM output

Problem:
  The extract_code_snippet function in perform_plotting.py uses a simple regex
  to extract code from ```python...``` blocks. When the LLM returns malformed
  output (partial fences, explanatory text mixed with code, or nested fences),
  the function returns the raw text including markdown, causing SyntaxError
  when exec() is called.

Fix:
  Enhanced extract_code_snippet with multiple fallback strategies:
  1. Standard ```python ... ``` extraction (longest match)
  2. Generic ``` ... ``` extraction
  3. Partial fence cleanup (opening ``` without closing)
  4. Python code auto-detection (import/def/for/plt patterns)
  5. Line-by-line filtering of non-Python content

Apply to: ai_scientist/perform_plotting.py
"""

import re


def extract_code_snippet(text: str) -> str:
    """Extract Python code from LLM response with robust fallback handling.

    Handles:
    - Standard ```python ... ``` blocks
    - Generic ``` ... ``` blocks
    - Partial/malformed fence markers
    - Mixed explanation + code responses
    - Raw Python code without any fences
    """
    if not text or not text.strip():
        return ""

    text = text.strip()

    # Strategy 1: Extract from ```python ... ``` blocks (use longest match)
    pattern_python = r"```python\s*\n?(.*?)```"
    matches = re.findall(pattern_python, text, flags=re.DOTALL)
    if matches:
        # Return the longest match (most likely the complete code)
        return max(matches, key=len).strip()

    # Strategy 2: Extract from generic ``` ... ``` blocks
    pattern_generic = r"```\s*\n?(.*?)```"
    matches = re.findall(pattern_generic, text, flags=re.DOTALL)
    if matches:
        best = max(matches, key=len).strip()
        # Verify it looks like Python code
        if _looks_like_python(best):
            return best

    # Strategy 3: Handle partial fences (opening ``` without proper closing)
    lines = text.split('\n')
    if lines and lines[0].strip().startswith('```'):
        # Remove opening fence
        lines = lines[1:]
        # Remove closing fence if present
        if lines and lines[-1].strip() == '```':
            lines = lines[:-1]
        candidate = '\n'.join(lines).strip()
        if _looks_like_python(candidate):
            return candidate

    # Strategy 4: Check if the entire text is valid Python (no fences at all)
    if _looks_like_python(text):
        # Filter out obvious non-code lines (markdown headers, bullet points)
        filtered = _filter_python_lines(text)
        if filtered:
            return filtered

    # Strategy 5: Last resort - extract only lines that look like Python
    python_lines = []
    in_code = False
    for line in lines:
        stripped = line.strip()
        # Skip markdown artifacts
        if stripped.startswith('#') and not stripped.startswith('#!'):
            if '=' not in stripped and '(' not in stripped:
                continue  # Likely markdown header, not Python comment
        if stripped.startswith('```'):
            in_code = not in_code
            continue
        if stripped.startswith('- ') or stripped.startswith('* '):
            if not in_code:
                continue  # Markdown bullet points
        python_lines.append(line)

    result = '\n'.join(python_lines).strip()
    return result if result else text.strip()


def _looks_like_python(text: str) -> bool:
    """Heuristic check if text contains Python code patterns."""
    python_indicators = [
        r'\bimport\s+\w+',
        r'\bfrom\s+\w+\s+import\b',
        r'\bdef\s+\w+\s*\(',
        r'\bclass\s+\w+',
        r'\bfor\s+\w+\s+in\b',
        r'\bif\s+.*:',
        r'\bplt\.\w+',
        r'\bnp\.\w+',
        r'\bpd\.\w+',
        r'\bprint\s*\(',
        r'=\s*\[',
        r'=\s*\{',
    ]
    score = sum(1 for p in python_indicators if re.search(p, text))
    return score >= 2


def _filter_python_lines(text: str) -> str:
    """Filter text to keep only Python-like lines."""
    lines = text.split('\n')
    filtered = []
    for line in lines:
        stripped = line.strip()
        # Remove pure markdown lines
        if stripped.startswith('# ') and '=' not in stripped and '(' not in stripped:
            # Could be markdown header or Python comment - keep if indented or after code
            if filtered and not stripped.startswith('## '):
                filtered.append(line)
            continue
        if stripped.startswith('```'):
            continue
        if stripped.startswith('---'):
            continue
        if stripped.startswith('| '):
            continue
        filtered.append(line)
    return '\n'.join(filtered).strip()


def apply_patch(source_code: str) -> str:
    """Replace extract_code_snippet in perform_plotting.py source."""
    # Find the existing function definition
    pattern = r'def extract_code_snippet\(text.*?\).*?(?=\ndef |\nclass |\Z)'
    match = re.search(pattern, source_code, flags=re.DOTALL)

    if not match:
        print("WARNING: extract_code_snippet function not found in source")
        return source_code

    # Get the new function source
    import inspect
    new_func = inspect.getsource(extract_code_snippet)
    # Also include helper functions
    new_helpers = inspect.getsource(_looks_like_python) + '\n\n' + inspect.getsource(_filter_python_lines)

    # Replace the old function
    replacement = new_helpers + '\n\n' + new_func
    patched = source_code[:match.start()] + replacement + '\n\n' + source_code[match.end():]

    return patched


if __name__ == "__main__":
    # Self-test
    test_cases = [
        # Case 1: Standard python fence
        ('```python\nimport matplotlib\nplt.plot([1,2,3])\n```',
         'import matplotlib\nplt.plot([1,2,3])'),

        # Case 2: Mixed markdown + code
        ('Here is the code:\n```python\nimport numpy as np\nx = np.array([1,2])\n```\nThis plots data.',
         'import numpy as np\nx = np.array([1,2])'),

        # Case 3: Partial fence (no closing)
        ('```python\nimport matplotlib.pyplot as plt\nplt.figure()\nplt.show()',
         'import matplotlib.pyplot as plt\nplt.figure()\nplt.show()'),

        # Case 4: No fences at all
        ('import matplotlib.pyplot as plt\nimport numpy as np\nx = np.linspace(0,10)\nplt.plot(x, np.sin(x))',
         'import matplotlib.pyplot as plt\nimport numpy as np\nx = np.linspace(0,10)\nplt.plot(x, np.sin(x))'),
    ]

    passed = 0
    for i, (input_text, expected) in enumerate(test_cases):
        result = extract_code_snippet(input_text)
        if result.strip() == expected.strip():
            passed += 1
            print(f"  Test {i+1}: PASS")
        else:
            print(f"  Test {i+1}: FAIL")
            print(f"    Expected: {expected[:80]}...")
            print(f"    Got:      {result[:80]}...")

    print(f"\n{passed}/{len(test_cases)} tests passed")
