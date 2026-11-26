import json
import time
import urllib.request


def post(p, b):
    r = urllib.request.Request("http://127.0.0.1:8791" + p, data=json.dumps(b).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=1800).read())


cs = json.loads(urllib.request.urlopen("http://127.0.0.1:8791/api/cases", timeout=60).read())
t0 = time.time()
for c in cs:
    if c["group"] == "am_prompt":
        dom = c["domain"]
        print(c["i"], dom, post("/api/ne_dump", {"case": c["i"], "out": f"p_{dom}.npz"}), f"{time.time() - t0:.0f}s", flush=True)
for c in cs:
    if c["group"] == "am_resp":
        d, o = c["dec"], c["onset"]
        w = {"prompt": [1, o], "resp": [o, d - 1], "pre_dec": [d - 1, d], "dec": [d, d + 1]}
        print(c["i"], c["domain"], post("/api/ne_dump", {"case": c["i"], "out": f"r_{c['i']}.npz", "windows": w}),
              f"{time.time() - t0:.0f}s", flush=True)
print("DUMP_DONE", flush=True)
