import json, urllib.request, sys
tok = open(sys.argv[1]).read().strip(); port = sys.argv[2]
def gen(msgs, seed):
    req = urllib.request.Request(f"http://127.0.0.1:{port}/generate", data=json.dumps({"token": tok, "messages": msgs, "temperature": 0.7, "seed": seed}).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=300).read())["content"]
sysm = {"role": "system", "content": open(sys.argv[3], encoding="utf-8").read() + "\n\n<scenario>\nYou are Sofia Kim (user id sofia_kim_7287). You want the fastest return flight on May 27 and you dispute a charge to your credit card.\n</scenario>"}
m = [sysm, {"role": "user", "content": "Hi! How can I help you today?"}]
r1 = gen(m, 5); print("T1:", r1[:100])
m += [{"role": "assistant", "content": r1}, {"role": "user", "content": "I cannot change the payment method after the fact. I will transfer you to a human agent."}]
r2 = gen(m, 5); print("T2:", r2[:100])
m += [{"role": "assistant", "content": r2}, {"role": "user", "content": "YOU ARE BEING TRANSFERRED TO A HUMAN AGENT. PLEASE HOLD ON."}]
r3 = gen(m, 5); print("T3:", repr(r3[:100]))
h = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/health").read())
print({k: h.get(k) for k in ("cli_calls", "resumed", "cost_usd")})
