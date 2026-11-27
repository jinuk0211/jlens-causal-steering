"""Forward speed with and without the capture hooks, one AM sequence, chunk sizes 2048 and 4096."""
import json
import os
import sys
import time
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from capture import Capture  # noqa: E402

jobs = [json.loads(l) for _, l in zip(range(5), open(sys.argv[1], encoding="utf-8"))]
ids = max(jobs, key=lambda j: len(j["ids"]))["ids"][:6144]
dtype = {"bf16": torch.bfloat16, "fp16": torch.float16}[os.environ.get("CAP_DTYPE", "bf16")]
cap = Capture("cuda", dtype)


def run(ch):
    torch.cuda.synchronize()
    t = time.time()
    cache = None
    for p in range(0, len(ids), ch):
        cache, _ = cap.run(ids, cache, p, min(p + ch, len(ids)))
    torch.cuda.synchronize()
    return len(ids) / (time.time() - t)


for ch in (2048, 2048, 4096, 4096, 1500, 1500, 1777):
    print(f"hooks on, chunk {ch}: {run(ch):.0f} tok/s", flush=True)
hooks = []
for m in cap.lm.modules():
    hooks += [k for k in list(m._forward_hooks) + list(m._forward_pre_hooks)]
    m._forward_hooks.clear()
    m._forward_pre_hooks.clear()
for ch in (2048, 4096, 1333):
    print(f"hooks off, chunk {ch}: {run(ch):.0f} tok/s", flush=True)
