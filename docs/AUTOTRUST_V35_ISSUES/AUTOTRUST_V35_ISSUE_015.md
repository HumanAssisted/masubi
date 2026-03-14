# Issue 015: train.py JSON extraction regex is greedy and may match incorrectly

## Severity
Low

## Category
Quality

## Description
In `train.py`, the `_parse_response` method (line 139) uses `re.search(r"\{.*\}", raw, re.DOTALL)` as a fallback to extract JSON from LLM responses. The `.*` with `re.DOTALL` is greedy, matching from the first `{` to the LAST `}` in the entire response. If the LLM includes markdown, multiple JSON examples, or explanatory text with braces, the regex could capture too much content, leading to a JSON parse error or incorrect data.

## Evidence
- File: `/Users/jonathan.hendler/personal/autoresearch-helpful/train.py:139` -- `re.search(r"\{.*\}", raw, re.DOTALL)`

## Suggested Fix
Use a more targeted approach:
1. Try parsing the raw response as JSON first (already done).
2. As fallback, look for JSON starting with `{"trust_vector"`:
   ```python
   match = re.search(r'\{"trust_vector".*?\}(\s*\})?', raw, re.DOTALL)
   ```
3. Or try iteratively trimming the response from both ends until `json.loads()` succeeds.
4. At minimum, use a non-greedy match: `re.search(r"\{.*?\}", raw, re.DOTALL)` -- though this would stop at the first `}` which is also wrong for nested JSON. A better approach is:
   ```python
   # Find balanced braces
   start = raw.index('{')
   depth = 0
   for i, ch in enumerate(raw[start:], start):
       if ch == '{': depth += 1
       elif ch == '}': depth -= 1
       if depth == 0:
           data = json.loads(raw[start:i+1])
           break
   ```

## Affected Files
- `train.py`
