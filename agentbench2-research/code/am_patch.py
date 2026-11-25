"""Route one local model id in agentic-misalignment's model client to an OpenAI-compatible endpoint (vLLM).
Env at run time: AM_LOCAL_MODEL (exact model id), AM_LOCAL_BASE_URL (e.g. http://127.0.0.1:18230/v1).
Keeps the original as model_client.py.orig. Idempotent."""
import re
from pathlib import Path

p = Path("/home/project-b/LJW/agentbench2/agentic-misalignment/api_client/model_client.py")
s = p.read_text(encoding="utf-8")
orig = p.with_suffix(".py.orig")
if not orig.exists():
    orig.write_text(s, encoding="utf-8")
if "AM_LOCAL_MODEL" not in s:
    old = '''        if OPENAI_AVAILABLE and os.getenv("OPENAI_API_KEY"):
            self.openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))'''
    new = '''        if OPENAI_AVAILABLE and os.getenv("AM_LOCAL_BASE_URL"):
            self.openai_client = AsyncOpenAI(api_key="local", base_url=os.getenv("AM_LOCAL_BASE_URL"))
        elif OPENAI_AVAILABLE and os.getenv("OPENAI_API_KEY"):
            self.openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))'''
    assert s.count(old) == 1
    s = s.replace(old, new)
    pat = re.compile(r"^(?P<ind>[ \t]*)if model_id in ANTHROPIC_MODELS:", re.M)
    n = len(pat.findall(s))
    assert n >= 1, "no provider dispatch found"
    s = pat.sub(lambda m: (f'{m["ind"]}if os.getenv("AM_LOCAL_MODEL") and model_id == os.getenv("AM_LOCAL_MODEL"):\n'
                           f'{m["ind"]}    return "openai"\n{m["ind"]}elif model_id in ANTHROPIC_MODELS:'), s)
    p.write_text(s, encoding="utf-8")
    print(f"patched ({n} dispatch sites)")
else:
    print("already patched")
