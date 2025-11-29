import re

def extract_json_object(raw: str) -> str:
    """
    Try to robustly extract a JSON object from an LLM response that may contain
    prose or Markdown fences.

    Strategy:
      1. If the whole string already looks like JSON (starts with '{' and ends with '}'), use it.
      2. If there is a ```json ... ``` code block, extract the inside.
      3. Otherwise, take the substring between the first '{' and the last '}'.
    """
    s = raw.strip()

    # 1) Pure JSON object
    if s.startswith("{") and s.endswith("}"):
        return s

    # 2) ```json ... ``` or ``` ... ``` block
    fence_match = re.search(r"```(?:json)?(.*?)```", s, re.DOTALL | re.IGNORECASE)
    if fence_match:
        inner = fence_match.group(1).strip()
        # sometimes there's a leading language label on the first line; strip it if needed
        # e.g. "json\n{...}"
        if inner.startswith("{") and inner.endswith("}"):
            return inner

    # 3) Fallback: first '{' to last '}'
    first = s.find("{")
    last = s.rfind("}")
    if first != -1 and last != -1 and first < last:
        return s[first:last + 1].strip()

    # If we can't find anything, just return as-is and let json.loads fail
    return s
