// Box components (level 2): the layout of one method's steps as a unit, composed from kernels (kernels.js). Keyed by
// "question/method", as in the server's registry (tutor/skills.py): every skill method (the green call nodes) and the
// method-level layouts (ratio tables). A component gets the frame from the spec ({component, id, labels, inputs,
// steps, done, kernels}) and the built kernels, and returns {node, placesDone}. What the student already wrote in a
// frame, and the build-up tries toward its next step, come in the frame's own `done`, so a component keeps no memory.
// It finds a step's place from the frame's `steps` (role, op, from, with), never from the say text. A registered
// frame without a JS component is drawn by `sequence`; a frame with no component by `plain`. Registers
// window.BoxComponents.
(function () {
  const {el, sym, line} = window.BoxKit;
  const OPWORD = {multiply: "×", divide: "÷", add: "+", subtract: "−", gcf: "GCF", lcm: "LCM", compare: "compare",
                  ratio_compare: "compare", plot: "plot"};

  const byRole = (ks, role) => ks.find(k => k.spec.role === role);
  const doneOf = (frame, role) => frame.done.filter(d => d.role === role).map(d => d.text);
  const doneLine = text => el("div", "bx-doneline", "✓ " + text);
  const pending = st => el("div", "bx-pending", "then " + (OPWORD[st.op] || st.op));
  const label = (frame, input) => (input && frame.labels[input]) || "";

  // A step's cell in a layout: its kernel if it's next, what the student wrote if it's done, else a placeholder.
  function cell(frame, ks, st, draw = k => k.inline()) {
    const k = byRole(ks, st.role);
    if (k) return draw(k);
    const done = doneOf(frame, st.role);
    if (done.length) return el("span", "bx-donecell", done.join("  →  "));
    return pending(st);
  }

  function withLabel(text, node) {
    const row = el("div", "bx-row");
    row.append(el("span", "bx-rowlabel", text), node);
    return row;
  }

  // ------------------------------------------------------------ generic layouts

  // No component: each kernel inline; several are alternatives.
  function plain(frame, ks) {
    const node = el("div", "bx-seq");
    ks.forEach((k, i) => {
      if (i) node.append(el("p", "bx-label", "or"));
      node.append(k.inline());
    });
    return {node, placesDone: false};
  }

  // The method's steps in order: done ones as written, the next as its kernel, later ones as placeholders.
  function sequence(frame, ks) {
    const node = el("div", "bx-seq");
    for (const st of frame.steps || []) {
      doneOf(frame, st.role).forEach(t => node.append(doneLine(t)));
      const k = byRole(ks, st.role);
      if (k) node.append(k.inline());
      else if (!doneOf(frame, st.role).length) node.append(pending(st));
    }
    ks.filter(k => !(frame.steps || []).some(st => st.role === k.spec.role)).forEach(k => node.append(k.inline()));
    return {node, placesDone: true};
  }

  // ------------------------------------------------------------ skills

  // simplify-fraction (gcf or repeated): the GCF, if the method finds one, then the top and bottom divisions as the
  // two rows of a fraction.
  function simplify(frame, ks) {
    const node = el("div", "bx-seq");
    const steps = frame.steps || [];
    const g = steps.find(st => st.op === "gcf");
    if (g) node.append(withLabel("GCF", cell(frame, ks, g)));
    const rows = el("div", "bx-rows");
    frame.inputs.slice(0, 2).forEach((input, i) => {
      const st = steps.find(s => s.op === "divide" && s.from === input);
      if (!st) return;
      if (i) rows.append(el("div", "bx-bar"));
      rows.append(withLabel(label(frame, input), cell(frame, ks, st)));
    });
    node.append(rows);
    return {node, placesDone: true};
  }

  // to-decimal/divide: the fraction itself, top over bottom, = [ ].
  function toDecimalDivide(frame, ks) {
    const [x, y] = frame.inputs;
    const node = el("div", "bx-seq");
    for (const k of ks) node.append(k.stacked ? k.stacked(label(frame, x), label(frame, y)) : k.inline());
    return {node, placesDone: false};
  }

  // to-decimal/power_of_ten: scale the top and the bottom (two rows), then read the decimal off the new fraction.
  function toDecimalPowerOfTen(frame, ks) {
    const node = el("div", "bx-seq");
    const steps = frame.steps || [];
    const rows = el("div", "bx-rows");
    frame.inputs.slice(0, 2).forEach((input, i) => {
      const st = steps.find(s => s.op === "multiply" && s.from === input);
      if (!st) return;
      if (i) rows.append(el("div", "bx-bar"));
      rows.append(withLabel(label(frame, input), cell(frame, ks, st)));
    });
    node.append(rows);
    const read = steps.find(s => s.op === "divide");
    if (read) node.append(withLabel("decimal", cell(frame, ks, read, k => (k.stacked ? k.stacked() : k.inline()))));
    return {node, placesDone: true};
  }

  // cross-products/diagonals: one row per diagonal, named by the two numbers it multiplies.
  function diagonals(frame, ks) {
    const node = el("div", "bx-seq");
    for (const st of frame.steps || []) {
      node.append(withLabel(`${label(frame, st.from)} × ${label(frame, st.with)}`, cell(frame, ks, st)));
    }
    return {node, placesDone: true};
  }

  // ------------------------------------------------------------ method layouts

  // A step the student wrote, read back from its text ("6 × 3 = 18"): {left, right, result}.
  function parts(text) {
    const m = /^(.+?) [×÷+−] (.+?) (?:=|≈) (.+)$/.exec(text || "");
    return m ? {left: m[1], right: m[2], result: m[3]} : null;
  }

  // A ratio table (missing-value/ratio_table, compare-fractions/ratio_table), composed from multiply kernels: the
  // active step's left slot is the start cell of its quantity, its right slot the ×k row header, its result the cell
  // of the new row. Everything already written comes from the frame's own `done` (the steps of this table, and the
  // build-up tries toward its next step, marked `try`), so each table (each call of the method) shows only its own
  // numbers, whichever way they were entered.
  function ratioTable(frame, ks) {
    const steps = frame.steps || [];
    const build = steps.find(s => s.op === "multiply" && s.search);
    const scale = steps.find(s => s.op === "multiply" && !s.search && build && s.from !== build.from);
    const rows = frame.inputs.filter(i => (build && i === build.from) || (scale && i === scale.from));
    const rowOf = role => { const st = steps.find(s => s.role === role); return st && st.from; };
    const start = {}, cols = [];
    let final = null;
    for (const d of frame.done) {
      const p = parts(d.text), row = rowOf(d.role);
      if (!p || !rows.includes(row)) continue;
      start[row] = p.left;
      if (d.try) cols.push({k: p.right, values: {[row]: p.result}});
      else if (!final) final = {k: p.right, values: {[row]: p.result}};
      else final.values[row] = p.result;
    }
    const k = ks.find(k => k.op === "multiply" && [build, scale].some(s => s && s.role === k.spec.role));
    const st = k && steps.find(s => s.role === k.spec.role);
    const activeRow = st && st.from;
    if (k) {
      if (start[activeRow]) k.slots.left.set(start[activeRow]);
      if (!st.search && final) k.slots.right.set(final.k);
    }
    // One column per quantity, one row per multiple: start, the ×k tries so far, then the row being filled. (Rows
    // grow downward, which fits a phone, and the tab order is start → k → result.)
    const wrap = el("div", "bx-tablewrap");
    const t = el("table", "bx-table");
    wrap.append(t);
    const head = el("tr");
    head.append(el("th", "", ""));
    for (const row of rows) head.append(el("th", "", label(frame, row)));
    t.append(head);
    const startRow = el("tr");
    startRow.append(el("th", "bx-rowlabel", "start"));
    for (const row of rows) {
      const td = el("td");
      if (k && row === activeRow) td.append(k.slots.left.node);
      else td.append(el("span", "bx-donecell", start[row] || ""));
      startRow.append(td);
    }
    t.append(startRow);
    for (const c of cols) {
      const tr = el("tr");
      tr.append(el("th", "bx-rowlabel", "× " + c.k));
      for (const row of rows) tr.append(el("td", "bx-donecell", c.values[row] || ""));
      t.append(tr);
    }
    const showFinal = final && !(st && st.search);
    if (k || showFinal) {
      const tr = el("tr", k ? "bx-cur" : "");
      const th = el("th", "bx-rowlabel");
      if (k) { const kk = el("span", "bx-k"); kk.append("×", k.slots.right.node); th.append(kk); }
      else th.textContent = "× " + final.k;
      tr.append(th);
      for (const row of rows) {
        const td = el("td");
        if (k && row === activeRow) td.append(k.slots.result.node);
        else if (showFinal) td.append(el("span", "bx-donecell", final.values[row] || ""));
        tr.append(td);
      }
      t.append(tr);
    }
    const node = el("div", "bx-seq");
    node.append(wrap);
    ks.filter(x => x !== k).forEach(x => node.append(x.inline()));  // e.g. compare the bottoms, after the table
    return {node, placesDone: true};
  }

  // common-multiple/list_multiples: the multiples of the first number listed so far (the build-up tries), then the
  // next one to write, until the second number divides one.
  function listMultiples(frame, ks) {
    const node = el("div", "bx-seq");
    const st = (frame.steps || []).find(s => s.search);
    const list = el("div", "bx-row");
    list.append(el("span", "bx-rowlabel", "multiples of " + (label(frame, st && st.from) || "")));
    for (const d of frame.done) {
      const p = parts(d.text);
      list.append(el("span", d.try ? "bx-donecell" : "bx-doneline", p ? p.result + (d.try ? "," : " ✓") : d.text));
    }
    node.append(list);
    ks.forEach(k => node.append(k.inline()));
    return {node, placesDone: true};
  }

  window.BoxComponents = {
    plain, sequence, parts,
    "simplify-fraction/gcf": simplify,
    "simplify-fraction/repeated": simplify,
    "to-decimal/divide": toDecimalDivide,
    "to-decimal/power_of_ten": toDecimalPowerOfTen,
    "common-multiple/recall": sequence,
    "common-multiple/list_multiples": listMultiples,
    "common-multiple/product": sequence,
    "common-multiple/gcf_formula": sequence,
    "cross-products/diagonals": diagonals,
    "missing-value/ratio_table": ratioTable,
    "compare-fractions/ratio_table": ratioTable,
  };
})();
