"""Cost of each hook operation, 32 layers, T tokens (warm)."""
import time

import torch

T, dev = 4096, "cuda"
a16 = torch.randn(T, 9216, device=dev, dtype=torch.bfloat16)
z16 = torch.randn(T, 4096, device=dev, dtype=torch.bfloat16)
G = torch.randn(32, 128, 128, device=dev)
G16 = torch.randn(16, 256, 256, device=dev)


def tm(name, fn, n=32):
    fn()
    torch.cuda.synchronize()
    t = time.time()
    for _ in range(n):
        fn()
    torch.cuda.synchronize()
    print(f"{name}: {(time.time() - t) * 1000:.0f} ms for 32 layers", flush=True)


tm("a.float()", lambda: a16.float())
a = a16.float()
tm("abs().topk(32) fp32", lambda: a.abs().topk(32, dim=-1))
tm("abs().topk(32) bf16", lambda: a16.abs().topk(32, dim=-1))
tm("einsum 3-op heads (32x128)", lambda: torch.einsum("thd,hde,the->th", z16.float().view(T, 32, 128), G, z16.float().view(T, 32, 128)))


def bmm_heads():
    zh = z16.float().view(T, 32, 128).transpose(0, 1)
    return (torch.bmm(zh, G) * zh).sum(-1)


tm("bmm heads (32x128)", bmm_heads)
tm("einsum 3-op heads (16x256)", lambda: torch.einsum("thd,hde,the->th", z16.float().view(T, 16, 256), G16, z16.float().view(T, 16, 256)))
tm("mean over 128-token pieces", lambda: [a[u:u + 128].mean(0) for u in range(0, T, 128)])
