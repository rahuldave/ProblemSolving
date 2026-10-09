// ai mode: registers TutorSetup.ai and TutorSteps.ai, each {render(s, asker, ctx)} (see index.html for the contract).
// "Talk it through": the student writes whatever they like; Claude reads it into the tutor's typed inputs on the
// server (POST /api/sessions/{id}/say) and the same session checks them. Claude never judges the work: the line
// "Claude read this as …" shows what it read, so a misreading is visible, and the tutor's own feedback follows.
(() => {
  const css = `
  .ai-box { display: flex; flex-direction: column; gap: .5rem; }
  .ai-box textarea { width: 100%; min-height: 4.2rem; resize: vertical; padding: .6rem .75rem; border: 1px solid var(--line);
    border-radius: 9px; background: var(--panel); color: var(--ink); font: 1rem/1.4 system-ui, -apple-system, "Segoe UI", sans-serif; }
  .ai-box textarea:focus { outline: 2px solid var(--accent); outline-offset: 1px; }
  .ai-box textarea:disabled { opacity: .6; }
  .ai-row { display: flex; gap: .5rem; align-items: center; flex-wrap: wrap; }
  .ai-row .btn.primary { margin-left: auto; }
  .ai-keys { font-size: .8rem; color: var(--muted); }
  .msg.ai-read { align-self: flex-end; background: none; border: 0; padding: 0 .25rem; margin-top: -.25rem; font-size: .83rem;
    color: var(--muted); white-space: normal; max-width: 100%; }
  .msg.ai-read code { font-family: var(--mono); background: var(--chip); color: var(--ink); padding: 0 .3rem; border-radius: 4px; }
  .msg.ai-note { background: var(--hint-bg); border-color: var(--hint); }
  .msg.ai-note::before { content: "Claude: "; font-weight: 600; }
  .msg.ai-thinking { color: var(--muted); font-size: .9rem; border: 0; }
  .ai-dots span { display: inline-block; width: .38rem; height: .38rem; margin: 0 .1rem; border-radius: 50%; background: var(--muted);
    animation: ai-blink 1.2s infinite ease-in-out both; }
  .ai-dots span:nth-child(2) { animation-delay: .15s; } .ai-dots span:nth-child(3) { animation-delay: .3s; }
  @keyframes ai-blink { 0%, 80%, 100% { opacity: .2; } 40% { opacity: 1; } }
  .ai-off { padding: .6rem .8rem; border-radius: 9px; border: 1px dashed var(--line); background: var(--chip); font-size: .92rem; }
  @media (max-width: 760px) { .ai-keys { display: none; } .ai-row .btn.primary { flex: 1 1 100%; margin-left: 0; } }
  @media (prefers-reduced-motion: reduce) { .ai-dots span { animation: none; opacity: .6; } }`;
  const style = document.createElement("style");
  style.textContent = css;
  document.head.append(style);

  let status = null;                 // {configured, model} from /api/ai/status, fetched once
  const busy = new Set();            // the sessions with a reading in flight (one at a time per session)
  const thread = () => document.querySelector(".thread");

  async function loadStatus(ctx) {
    if (status) return status;
    try { status = await ctx.api("/api/ai/status"); } catch { status = {configured: false}; }
    return status;
  }

  function placeholder(s) {
    if (!s.ask.allow_step) return s.ask.options.length ? "Say which one, in your own words…" : "Say your answer…";
    if (s.phase === "extract") return "Say which you think and why, or just start working it out…";
    return "e.g. 6 goes into 18 three times, so 4 times 3 is 12";
  }

  function showRead(ctx, list, checked) {
    if (!list || !list.length) return;
    const line = ctx.el("div", "msg ai-read");
    line.append("Claude read this as: ");
    list.forEach((t, i) => {
      if (i) line.append(i === list.length - 1 ? " then " : ", ");
      const c = ctx.el("code", "", t);
      if (checked && !checked[i]) { c.style.opacity = ".55"; c.title = "Not checked on its own"; }
      line.append(c);
    });
    thread().append(line);
  }

  // A reply is drawn only if the student is still on the session it was sent for.
  async function sayIt(ctx, text, box) {
    const sid = ctx.sid;
    if (busy.has(sid) || !text) return;
    busy.add(sid);
    ctx.say(text);
    const wait = ctx.el("div", "msg ai-thinking");
    const dots = ctx.el("span", "ai-dots");
    dots.append(ctx.el("span"), ctx.el("span"), ctx.el("span"));
    wait.append("Reading what you wrote ", dots);
    wait.setAttribute("role", "status");
    thread().append(wait);
    // while Claude reads, nothing else may change the session: the box, the option cards and Hint, Where, Done
    const controls = [...(box.closest(".asker") || box).querySelectorAll("textarea, button")];
    controls.forEach(e => { e.disabled = true; });
    try {
      const r = await ctx.api(`/api/sessions/${sid}/say`, {text});
      busy.delete(sid);
      if (ctx.sid !== sid) return;
      wait.remove();
      showRead(ctx, r.interpreted, r.checked);
      if (r.note) ctx.say(r.note, "ai-note");
      ctx.render(r);
    } catch (e) {
      busy.delete(sid);
      if (ctx.sid !== sid) return;
      wait.remove();
      ctx.say(e.message, "error");
      controls.forEach(e => { e.disabled = false; });
    }
  }

  // The same chat box serves both stages of the page: Setup (reading the story, then finding the method) and
  // Steps (once the method is known). /say works in every phase, so only the registration differs.
  function render(s, asker, ctx) {
    if (s.ask.text) asker.append(ctx.el("div", "msg ask", s.ask.text));
    if (s.ask.options.length) {         // the cards stay clickable: a click is a ChoiceAnswer, no model call
      const opts = ctx.el("div", "options");
      s.ask.options.forEach((o, i) => {
        const b = ctx.el("button", "", o);
        b.onclick = () => { if (!busy.has(ctx.sid)) ctx.sendTyped({kind: "choice", index: i + 1}, o); };
        opts.append(b);
      });
      asker.append(opts);
    }
    if (s.ask.note) asker.append(ctx.el("p", "note", s.phase === "extract"
      ? "Click one, or say what you think. You can also just start working it out." : s.ask.note));

    const box = ctx.el("div", "ai-box");
    const area = ctx.el("textarea");
    area.rows = 2;
    area.placeholder = placeholder(s);
    area.setAttribute("aria-label", "Say your step or answer in your own words");
    const row = ctx.el("div", "ai-row");
    const keys = ctx.el("span", "ai-keys", "Enter to send · Shift+Enter for a new line");
    const go = ctx.el("button", "btn primary", "Send");
    go.type = "button";
    row.append(keys, go);
    box.append(area, row);
    const send = () => sayIt(ctx, area.value.trim(), box);
    go.onclick = send;
    area.addEventListener("keydown", e => {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(); }
    });
    asker.append(box, ctx.tools());
    area.focus();

    loadStatus(ctx).then(st => {
      if (st.configured || !box.isConnected) return;
      const off = ctx.el("div", "ai-off");
      off.append("Talk it through needs a Claude API key on the server (ANTHROPIC_API_KEY, or a .env file at the " +
                 "repository root), and none is set. ");
      if (s.ask.options.length) off.append("You can still click an option above. ");
      off.append("Switch to “Type steps” to keep going.");
      box.replaceWith(off);
    });
  }

  const mode = {label: "Talk it through", order: 2, render};
  window.TutorSetup = window.TutorSetup || {};
  window.TutorSetup.ai = mode;
  window.TutorSteps = window.TutorSteps || {};
  window.TutorSteps.ai = mode;
})();
