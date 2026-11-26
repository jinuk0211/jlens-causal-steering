(() => {
  const GL = { am_prompt: "AM 프롬프트 18종 (시나리오×긴급도×목표)", am_resp: "AM 응답 (leaking, 수신자 결정까지)",
    fail: "ToolAlign 실패 (misaligned/boundary)", aligned: "ToolAlign 정상 target (legit tool)", ref: "ToolAlign reference (writeInternalLog)" };
  let cur = null;
  const css = document.createElement("style");
  css.textContent = `#case-box{display:flex;flex-direction:column;gap:4px;margin:0 0 8px}
#case-box select{width:100%;background:#111;color:#ddd;border:1px solid #333;border-radius:6px;padding:5px;font:12px ui-monospace,monospace}
#case-info{font:11px ui-monospace,monospace;color:#aaa;line-height:1.5}
#case-info b{color:#eee}
#inf-toks button.cs-doc{opacity:.55}
#inf-toks button.cs-resp{box-shadow:inset 0 -2px 0 #4fa3ff}
#inf-toks button.cs-call{box-shadow:inset 0 -2px 0 #ffb547}
#inf-toks button.cs-onset{outline:1px solid #4fa3ff}`;
  document.head.appendChild(css);
  const box = document.createElement("div");
  box.id = "case-box";
  box.innerHTML = `<select id="case-sel"><option value="">agentbench2 ToolAlign 케이스 불러오는 중…</option></select><div id="case-info"></div>`;
  const pane = document.getElementById("lt-run");
  pane.insertBefore(box, pane.firstChild);
  const sel = box.querySelector("select"), info = box.querySelector("#case-info");
  fetch("/api/cases").then(r => r.json()).then(cs => {
    const by = { am_prompt: [], am_resp: [], fail: [], aligned: [], ref: [] };
    cs.forEach(c => (by[c.group] = by[c.group] || []).push(c));
    let h = `<option value="">케이스 선택 (${cs.length}개)</option>`;
    for (const g of Object.keys(by)) {
      if (!by[g].length) continue;
      h += `<optgroup label="${GL[g]}">` + by[g].sort((a, b) => (a.domain > b.domain) - (a.domain < b.domain) || a.i - b.i)
        .map(c => `<option value="${c.i}">#${c.i} ${c.domain} · ${c.tool} · ${c.risk} · ${c.tokens} tok</option>`).join("") + "</optgroup>";
    }
    sel.innerHTML = h;
    window.__cases = Object.fromEntries(cs.map(c => [c.i, c]));
  });
  sel.addEventListener("change", () => {
    if (sel.value === "") return;
    cur = window.__cases[sel.value];
    const f = cur.fires || {}, yn = v => v === undefined ? "-" : v ? "켜짐" : "꺼짐";
    info.innerHTML = `<b>#${cur.i}</b> ${GL[cur.group]} · ${cur.domain}<br>원래 호출 <b>${cur.tool}</b> · 응답 시작 token ${cur.onset} · tool call ${cur.scaf} · 총 ${cur.tokens} tok<br>` +
      (cur.group === "am_prompt" ? `프롬프트만 (응답 없음). 마지막 토큰 = 응답을 시작하는 위치` :
        cur.group === "am_resp" ? `결정 토큰(수신자 주소 첫 토큰) = ${cur.dec}` :
        `감지기(LODO) last64 ${yn(f.last64)} · scaffold ${yn(f.scaffold)} · doc ${yn(f.doc)}`) +
      (cur.attn_commit !== undefined ? `<br>attn L16-20 편집(commit) 후 호출: ${cur.attn_commit ?? "없음"}` : "") +
      `<br><span style="color:#4fa3ff">파란 밑줄</span> = 모델 응답, <span style="color:#ffb547">주황</span> = tool call, 흐린 것 = 입력 문서. 실행에 수십 초 걸립니다.`;
    const q = document.querySelector('#q-mode button[data-q="fires"]');
    if (q && !q.classList.contains("on")) q.click();
    const lq = document.getElementById("lens-q"), it = document.getElementById("inf-text");
    const text = `#case ${cur.i}`;
    it.value = text; lq.value = text;
    lq.dispatchEvent(new Event("input"));
  });
  new MutationObserver(() => {
    if (!cur || document.getElementById("lens-q").value.trim() !== `#case ${cur.i}`) return;
    const btns = [...document.querySelectorAll("#inf-toks button")];
    if (!btns.length || btns[0].dataset.cs) return;
    let first = null, dec = null;
    btns.forEach(b => {
      const i = +b.dataset.i;
      b.dataset.cs = "1";
      b.classList.add(i >= cur.scaf ? "cs-call" : i >= cur.onset ? "cs-resp" : "cs-doc");
      if (!first && i >= cur.onset) { first = b; b.classList.add("cs-onset"); }
      if (cur.dec != null && !dec && i >= cur.dec) { dec = b; b.style.outline = "2px solid #ff4f9a"; }
    });
    (dec || first)?.scrollIntoView({ block: "center" });
  }).observe(document.getElementById("inf-toks"), { childList: true });
})();
