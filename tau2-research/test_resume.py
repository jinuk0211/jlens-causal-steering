import json, urllib.request, sys
tok = open(sys.argv[1]).read().strip()
def gen(msgs, seed):
    req = urllib.request.Request("http://127.0.0.1:18092/generate", data=json.dumps({"token": tok, "messages": msgs, "temperature": 0.7, "seed": seed}).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=300).read())["content"]
sysm = {"role": "system", "content": "You are Liam Khan (user id liam_khan_2521) calling an airline. You want to move your May 23 IAH->SEA flight to May 24. Only accept if the total extra cost is under 1000 dollars. When done, reply ###STOP###."}
m = [sysm, {"role": "user", "content": "Hi! How can I help you today?"}]
r1 = gen(m, 7); print("T1:", r1[:120])
m += [{"role": "assistant", "content": r1}, {"role": "user", "content": "I found reservation 4NQLHD. The change to May 24 in economy costs an extra $1,250 in total. Shall I proceed?"}]
r2 = gen(m, 7); print("T2:", r2[:160])
m += [{"role": "assistant", "content": r2}, {"role": "user", "content": "Understood. Is there anything else I can help with?"}]
r3 = gen(m, 7); print("T3:", r3[:160])
h = json.loads(urllib.request.urlopen("http://127.0.0.1:18092/health").read())
print({k: h.get(k) for k in ("cli_calls", "resumed", "cost_usd", "cache_read_input_tokens", "cache_creation_input_tokens")})
