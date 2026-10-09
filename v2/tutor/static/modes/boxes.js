// Choice setup and box steps. Registers TutorSetup.choices and TutorSteps.boxes, each {render(s, asker, ctx)} with
// the ctx of index.html.
//
// GET /api/sessions/{sid}/boxes says which stage we're in (tutor/skills.py documents the spec):
// - "extract": the decision's option cards, sent as a ChoiceAnswer to /step;
// - "find_method": "How do you want to start?", the live methods as cards, sent to POST /method;
// - "steps": frames, each drawn by its component (components.js) from kernels (kernels.js), AoPS-style: an equation,
//   a stacked fraction or a small table with number boxes in it. The spec never holds the step's numbers; the
//   kernels build typed StudentInputs for /step, and the server checks them.
//
// kernels.js and components.js are loaded here if the page hasn't loaded them already.
(function () {
  const CSS = `
  .bx { display: flex; flex-direction: column; gap: .75rem; }
  .bx-card { border: 1px solid var(--line); border-radius: 12px; padding: .8rem .9rem; background: var(--panel); min-width: 0; }
  .bx-say { font-size: .95rem; margin: 0 0 .55rem; }
  .bx-label { font-size: .78rem; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); margin: 0 0 .4rem; }
  .bx-chip { display: inline-block; font-size: .82rem; padding: .1rem .55rem; border-radius: 999px; background: var(--method-bg);
             color: var(--method); }
  .bx form.bx-form { display: block; }
  .bx-eq { display: flex; flex-wrap: wrap; align-items: center; gap: .4rem .45rem; font-size: 1.25rem; font-family: var(--mono); }
  .bx-sym { min-width: .8em; text-align: center; color: var(--ink); }
  .bx input.bx-box { flex: 0 0 auto; width: 4.6em; min-width: 0; padding: .35rem .3rem; text-align: center; font: 1.1rem var(--mono);
                     border: 1.5px solid var(--line); border-radius: 8px; background: var(--bg); color: var(--ink); }
  .bx input.bx-box:focus { outline: 2px solid var(--accent); outline-offset: 1px; border-color: var(--accent); }
  .bx input.bx-box.bx-bad { border-color: var(--trap); background: var(--trap-bg); }
  .bx-frac { display: inline-flex; flex-direction: column; align-items: center; gap: 3px; }
  .bx-frac .bx-bar { align-self: stretch; height: 2px; background: var(--ink); border-radius: 1px; }
  .bx-rows { display: inline-grid; gap: .35rem; max-width: 100%; }
  .bx-rows .bx-bar { height: 2px; background: var(--ink); border-radius: 1px; }
  .bx-rowlabel { font: .8rem system-ui, sans-serif; color: var(--muted); min-width: 3.2em; }
  .bx-seg { display: inline-flex; gap: 3px; padding: 2px; border: 1px solid var(--line); border-radius: 9px; background: var(--chip); }
  .bx-seg button { border: 0; background: none; color: var(--ink); font: 1.05rem var(--mono); padding: .25rem .6rem; border-radius: 7px;
                   cursor: pointer; min-width: 2.2em; }
  .bx-seg button[aria-pressed=true] { background: var(--accent); color: var(--accent-ink); }
  .bx-seg.bx-bad { outline: 2px solid var(--trap); }
  .bx-go { display: flex; gap: .5rem; flex-wrap: wrap; align-items: center; margin-top: .7rem; }
  .bx-err { color: var(--trap); font-size: .88rem; }
  .bx-cards { display: grid; gap: .5rem; grid-template-columns: repeat(auto-fill, minmax(min(100%, 15rem), 1fr)); }
  .bx-decision { display: flex; flex-direction: column; gap: .4rem; }
  .bx-typed { display: flex; flex-direction: column; gap: .3rem; margin-top: .25rem; }
  .bx-typed .bx-row { flex-wrap: nowrap; }
  .bx-typed input { flex: 1 1 auto; min-width: 0; padding: .5rem .7rem; border: 1px solid var(--line); border-radius: 9px;
                    background: var(--panel); color: var(--ink); font: 1rem var(--mono); }
  .bx-cards button { text-align: left; padding: .65rem .8rem; border: 1px solid var(--line); background: var(--panel); color: var(--ink);
                     border-radius: 10px; font: inherit; cursor: pointer; }
  .bx-cards button:hover, .bx-cards button:focus-visible { border-color: var(--accent); outline: none; }
  .bx-cards b { display: block; margin-bottom: .15rem; }
  .bx-cards small { display: block; color: var(--muted); font-size: .85rem; margin-top: .25rem; }
  .bx-tablewrap { overflow-x: auto; max-width: 100%; }
  .bx-table { border-collapse: collapse; font-family: var(--mono); }
  .bx-table th, .bx-table td { border: 1px solid var(--line); padding: .3rem .4rem; text-align: center; min-width: 4.2em; }
  .bx-table th { font-weight: 500; color: var(--muted); font-size: .9rem; white-space: nowrap; }
  .bx-table th.bx-rowlabel, .bx-table td.bx-rowlabel { text-align: left; font-family: system-ui, sans-serif; }
  .bx-table .bx-cur td, .bx-table .bx-cur th { background: var(--hint-bg); }
  .bx-table .bx-done { color: var(--ink); font-size: 1.05rem; }
  .bx-table .bx-k { display: inline-flex; align-items: center; gap: .2rem; }
  .bx-table input.bx-box { width: 3.8em; }
  .bx-seq { display: flex; flex-direction: column; gap: .5rem; align-items: flex-start; min-width: 0; max-width: 100%; }
  .bx-row { display: flex; flex-wrap: wrap; align-items: center; gap: .3rem .6rem; }
  .bx-doneline, .bx-donecell { font-family: var(--mono); color: var(--ok); }
  .bx-pending { font-size: .88rem; color: var(--muted); font-style: italic; }
  .bx-fraclabels { display: inline-flex; flex-direction: column; justify-content: space-between; align-self: stretch;
                   font: .78rem system-ui, sans-serif; color: var(--muted); text-align: right; padding: .3rem 0; }
  .bx-points { display: flex; flex-wrap: wrap; gap: .5rem .9rem; align-items: center; }
  @media (max-width: 480px) {
    .bx-eq { font-size: 1.1rem; gap: .35rem; }
    .bx input.bx-box { width: 3.9em; font-size: 1rem; }
  }`;

  function injectCss() {
    if (document.getElementById("bx-css")) return;
    const st = document.createElement("style");
    st.id = "bx-css"; st.textContent = CSS;
    document.head.append(st);
  }

  // ------------------------------------------------------------ loading kernels.js and components.js

  const here = (document.currentScript && document.currentScript.src) || "/static/modes/boxes.js";
  function load(name) {
    return new Promise((ok, fail) => {
      const sc = document.createElement("script");
      sc.src = new URL(name, here).href;
      sc.onload = ok; sc.onerror = () => fail(new Error("couldn't load " + name));
      document.head.append(sc);
    });
  }
  let ready = null;
  const loaded = () => (ready = ready || (async () => {
    if (!window.BoxKit) await load("kernels.js");
    if (!window.BoxComponents) await load("components.js");
  })());

  const el = (tag, cls, text) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  };

  // ------------------------------------------------------------ frames

  // Send inputs one after another (top then bottom of a fraction), stopping at the first that isn't accepted.
  async function submit(items, ctx) {
    for (const [input, shown] of items) {
      const r = await ctx.sendTyped(input, shown);
      if (!r || !(r.feedback || []).some(f => f.kind === "correct" || f.kind === "on_track")) break;
    }
  }

  // "Simplify: divide the top by the GCF" + "Simplify: divide the bottom by the GCF" →
  // "Simplify: divide the top by the GCF, or divide the bottom by the GCF"
  function joinSays(says) {
    says = [...new Set(says.filter(Boolean))];
    if (says.length < 2) return says[0] || "";
    const lead = says[0].includes(": ") ? says[0].slice(0, says[0].indexOf(": ") + 2) : "";
    const low = x => x.slice(0, 1).toLowerCase() + x.slice(1);
    if (lead && says.every(x => x.startsWith(lead))) return lead + says.map(x => x.slice(lead.length)).join(", or ");
    return says[0] + says.slice(1).map(x => ", or " + low(x)).join("");
  }

  function drawFrame(frame, ctx) {
    const env = {sid: ctx.sid, submit: items => submit(items, ctx)};
    const card = el("div", "bx-card");
    const ks = frame.kernels.map(k => BoxKit.makeKernel(k, env)).filter(Boolean);
    if (frame.kernels.length) card.append(el("p", "bx-say", joinSays(frame.kernels.map(k => k.say))));
    const comp = (frame.component && (BoxComponents[frame.component] || BoxComponents.sequence)) || BoxComponents.plain;
    const drawn = comp(frame, ks, env);
    if (!drawn.placesDone) frame.done.forEach(d => card.append(el("div", "bx-doneline", "✓ " + d.text)));
    if (ks.length && ks.every(k => k.cards)) { card.append(drawn.node); return card; }  // answer cards send on click
    const f = el("form", "bx-form");
    f.noValidate = true;
    const go = el("button", "btn primary", "Check");
    go.type = "submit";
    const err = el("span", "bx-err");
    const row = el("div", "bx-go");
    row.append(go, err);
    f.append(drawn.node, row);
    f.onsubmit = async e => {
      e.preventDefault();
      err.textContent = "";
      // the kernels the student filled (either-order steps can be filled together), else the first one
      const filled = ks.filter(k => !k.cards && k.filled());
      const chosen = filled.length ? filled : ks.filter(k => !k.cards).slice(0, 1);
      const items = chosen.map(k => k.collect(true));
      if (!items.length || items.some(i => !i)) {
        err.textContent = "Fill each box with a number, like 3, 0.75 or 2/3.";
        const bad = f.querySelector("input.bx-bad");
        if (bad) bad.focus();
        return;
      }
      go.disabled = true;
      try { await submit(items, ctx); } finally { go.disabled = false; }
    };
    card.append(f);
    return card;
  }

  // ------------------------------------------------------------ stages

  function cards(options, onPick) {
    const box = el("div", "bx-cards");
    options.forEach((o, i) => {
      const b = el("button", "");
      b.type = "button";
      if (typeof o === "string") b.textContent = o;
      else {
        b.append(el("b", "", o.name), o.idea || "");
        if (o.best_when) b.append(el("small", "", "Best when: " + o.best_when));
      }
      b.onclick = () => onPick(o, i);
      box.append(b);
    });
    return box;
  }

  // Through ctx.post, like every other request: the reply is drawn only if the student is still on that problem.
  async function chooseMethod(m, ctx) {
    return ctx.post(`/api/sessions/${ctx.sid}/method`, {method: m.id}, "I'll start with: " + m.name);
  }

  function header(spec) {
    const top = el("div");
    if (spec.prompt) top.append(el("div", "msg ask", spec.prompt));
    if (spec.method) top.append(el("span", "bx-chip", spec.method.name));
    return top;
  }

  function focusFirst(root) {
    const inputs = [...root.querySelectorAll("input.bx-box")];
    const first = inputs.find(i => !i.optional && !i.value) || inputs[0] || root.querySelector(".bx-cards button");
    if (first) first.focus({preventScroll: true});
  }

  // "Or write your first step": a typed step, parsed on the server, wherever the setup has cards. It skips the
  // decisions (or gives a trap away), or finds the method from the step, as the graph's first-step tree does.
  function typeBox(ctx, label, placeholder) {
    const f = el("form", "bx-typed");
    const lab = el("label", "bx-label", label);
    const input = el("input");
    input.type = "text"; input.autocomplete = "off"; input.spellcheck = false;
    input.placeholder = placeholder;
    input.setAttribute("aria-label", label);
    const go = el("button", "btn", "Check");
    go.type = "submit";
    const row = el("div", "bx-row");
    row.append(input, go);
    f.append(lab, row);
    f.onsubmit = e => { e.preventDefault(); if (input.value.trim()) ctx.send(input.value.trim()); };
    return f;
  }

  // Setup by choices: every open extraction decision with its option cards (the graph lets them be taken in any
  // order), then "How do you want to start?" with the method cards. Both also take a typed first step. Once one
  // method is named, the steps input takes over.
  function drawSetup(spec, s, asker, ctx) {
    if (spec.stage !== "extract" && spec.stage !== "find_method") return drawSteps(spec, s, asker, ctx);
    const root = el("div", "bx");
    if (spec.stage === "extract") {
      const decisions = spec.decisions || [{id: null, say: spec.prompt, options: s.ask.options}];
      decisions.forEach((d, n) => {
        const group = el("div", "bx-decision");
        group.append(el("div", n ? "bx-label" : "msg ask", d.say));
        group.append(cards(d.options, (o, i) => {
          const input = {kind: "choice", index: i + 1};
          if (d.id !== null && d.id !== undefined) input.decision = Number(d.id);
          ctx.sendTyped(input, o);
        }));
        root.append(group);
        if (!n && decisions.length > 1) root.append(el("p", "bx-label", "The other decisions, in any order:"));
      });
      root.append(typeBox(ctx, "Or just start solving: write your first step", "e.g. 4 x 18 = 72"));
    } else {
      root.append(header(spec));
      root.append(cards(spec.methods, m => chooseMethod(m, ctx)));
      root.append(typeBox(ctx, spec.prompt.includes("next step") ? "Or write your next step" : "Or write your first step",
                          "e.g. 4 x 18 = 72"));
    }
    asker.append(root, ctx.tools());
    focusFirst(root);
  }

  // Steps by boxes: one frame per place the next step can be (usually one), then the follow-up step and the answer.
  function drawSteps(spec, s, asker, ctx) {
    if (spec.stage === "extract" || spec.stage === "find_method") return drawSetup(spec, s, asker, ctx);
    const root = el("div", "bx");
    root.append(header(spec));
    const frames = spec.frames || [];
    if (frames.length > 1) root.append(el("p", "bx-label", "Next, any one of these"));
    for (const fr of frames) root.append(drawFrame(fr, ctx));
    asker.append(root, ctx.tools());
    focusFirst(root);
  }

  // Fetch the spec, then draw it, unless a newer render, another way or another problem took over in the meantime
  // (the page clears asker.bxToken whenever it redraws the asker).
  async function withSpec(s, asker, ctx, drawFn) {
    injectCss();
    const sid = ctx.sid;
    const token = {};
    asker.bxToken = token;
    let spec;
    try {
      await loaded();
      spec = await ctx.api(`/api/sessions/${sid}/boxes`);
    } catch (e) {
      if (asker.bxToken === token) asker.append(el("p", "bx-err", "Couldn't load this step (" + e.message + ")."), ctx.tools());
      return;
    }
    if (asker.bxToken !== token || !asker.isConnected || ctx.sid !== sid) return;
    asker.replaceChildren();
    drawFn(spec, s, asker, ctx);
  }

  window.TutorSetup = window.TutorSetup || {};
  window.TutorSteps = window.TutorSteps || {};
  TutorSetup.choices = {label: "choices", render: (s, asker, ctx) => withSpec(s, asker, ctx, drawSetup)};
  TutorSteps.boxes = {label: "boxes", render: (s, asker, ctx) => withSpec(s, asker, ctx, drawSteps)};
})();
