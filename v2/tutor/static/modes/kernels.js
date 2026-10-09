// Box kernels (level 1): the primitives (NumberSlot, FractionSlot, RelationPicker) and one kernel per op of the step
// language: multiply, divide, add, subtract, gcf, lcm, compare, ratio_compare, plot, answer. A kernel knows only its
// op. It exposes its slots, so a component (components.js) can place them anywhere, and an inline layout for when it
// is drawn on its own. collect() builds the typed StudentInput (with a readable `shown`) or returns null when a box
// doesn't hold a number. Registers window.BoxKit.
(function () {
  const SYM = {multiply: "×", divide: "÷", add: "+", subtract: "−"};
  const NUM = /^-?(\d+\.?\d*|\.\d+)(\/(\d+\.?\d*|\.\d+))?$/;
  const clean = v => v.trim().replace(/[\s$,]/g, "");
  const N = text => ({text});

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }
  const sym = s => el("span", "bx-sym", s);
  const line = (...parts) => { const d = el("div", "bx-eq"); d.append(...parts); return d; };

  // ------------------------------------------------------------ primitives

  // One number: 3, 0.75 or 2/3. read() marks the box and returns its text, or null when it isn't a number.
  function NumberSlot(label, opt = {}) {
    const i = el("input", "bx-box");
    i.type = "text"; i.autocomplete = "off"; i.spellcheck = false;
    i.setAttribute("autocapitalize", "off"); i.setAttribute("enterkeyhint", "go"); i.setAttribute("aria-label", label);
    i.optional = !!opt.optional;
    if (opt.value) i.value = opt.value;
    i.addEventListener("input", () => i.classList.remove("bx-bad"));
    return {
      node: i, inputs: [i],
      filled: () => !!clean(i.value),
      set: v => { i.value = v || ""; },
      read(required) {
        const v = clean(i.value);
        const bad = v ? !NUM.test(v) : (required || !i.optional);
        i.classList.toggle("bx-bad", bad);
        return bad ? null : v;
      },
    };
  }

  // A stacked fraction [ ]/[ ]. An empty bottom means the top is the whole value (0.667, 3).
  function FractionSlot(label) {
    const top = NumberSlot(label + ", top"), bot = NumberSlot(label + ", bottom", {optional: true});
    const node = el("span", "bx-frac");
    node.append(top.node, el("span", "bx-bar"), bot.node);
    return {
      node, inputs: [top.node, bot.node],
      filled: () => top.filled() || bot.filled(),
      set: v => { const [t, b] = String(v || "").split("/"); top.set(t); bot.set(b); },
      read(required) {
        const t = top.read(required), b = bot.read(false);
        if (t === null || b === null) return null;
        return b ? `${t}/${b}` : t;
      },
    };
  }

  // A choice of relation: <, =, > (or =, ≠).
  function RelationPicker(options, label = "relation") {
    const node = el("span", "bx-seg");
    node.setAttribute("role", "group"); node.setAttribute("aria-label", label);
    let picked = null;
    for (const r of options) {
      const b = el("button", "", r);
      b.type = "button"; b.setAttribute("aria-pressed", "false");
      b.onclick = () => {
        picked = r; node.classList.remove("bx-bad");
        node.querySelectorAll("button").forEach(x => x.setAttribute("aria-pressed", String(x === b)));
      };
      node.append(b);
    }
    return {
      node, inputs: [],
      filled: () => picked !== null,
      read() { if (!picked) node.classList.add("bx-bad"); return picked; },
    };
  }

  const operand = (kind, label) => (kind === "fraction" ? FractionSlot(label) : NumberSlot(label));

  // ------------------------------------------------------------ kernels

  // Read every slot of a kernel; null if any is bad (all are marked, not just the first).
  function readAll(slots, required) {
    const vals = slots.map(s => s.read(required));
    return vals.some(v => v === null) ? null : vals;
  }

  function arithmetic(op) {
    return spec => {
      const kinds = spec.slots || ["number", "number"];
      const left = operand(kinds[0], "first number"), right = operand(kinds[1], "second number");
      const result = NumberSlot("result");
      const slots = {left, right, result};
      return {
        spec, op, slots,
        inline: () => line(left.node, sym(SYM[op]), right.node, sym("="), result.node),
        // the stacked form, for a division drawn as a fraction: top over bottom, = result
        stacked(topLabel, bottomLabel) {
          const f = el("span", "bx-frac");
          f.append(left.node, el("span", "bx-bar"), right.node);
          const out = line(f, sym("="), result.node);
          if (topLabel || bottomLabel) {
            const lab = el("span", "bx-fraclabels");
            lab.append(el("span", "", topLabel || ""), el("span", "", bottomLabel || ""));
            out.prepend(lab);
          }
          return out;
        },
        filled: () => Object.values(slots).some(s => s.filled()),
        collect(required) {
          const v = readAll([left, right, result], required);
          if (!v) return null;
          return [{kind: "arithmetic", op, left: N(v[0]), right: N(v[1]), result: N(v[2])}, `${v[0]} ${SYM[op]} ${v[1]} = ${v[2]}`];
        },
      };
    };
  }

  function func(name) {
    return spec => {
      const left = NumberSlot("first number"), right = NumberSlot("second number"), result = NumberSlot("result");
      const slots = {left, right, result};
      const NAME = name.toUpperCase();
      return {
        spec, op: name, slots,
        inline: () => line(sym(NAME + "("), left.node, sym(","), right.node, sym(")"), sym("="), result.node),
        filled: () => Object.values(slots).some(s => s.filled()),
        collect(required) {
          const v = readAll([left, right, result], required);
          if (!v) return null;
          return [{kind: "function", name, left: N(v[0]), right: N(v[1]), result: N(v[2])}, `${NAME}(${v[0]}, ${v[1]}) = ${v[2]}`];
        },
      };
    };
  }

  function compare(spec) {
    const kinds = spec.slots || ["number", "number"];
    const left = operand(kinds[0], "left number"), right = operand(kinds[1], "right number");
    const relation = RelationPicker(["<", "=", ">"]);
    const slots = {left, relation, right};
    return {
      spec, op: "compare", slots,
      inline: () => line(left.node, relation.node, right.node),
      filled: () => left.filled() || right.filled(),
      collect(required) {
        const v = readAll([left, relation, right], required);
        if (!v) return null;
        return [{kind: "compare", left: N(v[0]), relation: v[1], right: N(v[2])}, `${v[0]} ${v[1]} ${v[2]}`];
      },
    };
  }

  function ratioCompare(spec) {
    const a = NumberSlot("first ratio, first term"), b = NumberSlot("first ratio, second term");
    const c = NumberSlot("second ratio, first term"), d = NumberSlot("second ratio, second term");
    const relation = RelationPicker(["=", "≠"]);
    const slots = {a, b, relation, c, d};
    return {
      spec, op: "ratio_compare", slots,
      inline: () => line(a.node, sym(":"), b.node, relation.node, c.node, sym(":"), d.node),
      filled: () => [a, b, c, d].some(s => s.filled()),
      collect(required) {
        const v = readAll([a, b, relation, c, d], required);
        if (!v) return null;
        return [{kind: "ratio_compare", left: [N(v[0]), N(v[1])], relation: v[2], right: [N(v[3]), N(v[4])]},
                `${v[0]}:${v[1]} ${v[2]} ${v[3]}:${v[4]}`];
      },
    };
  }

  function plot(spec) {
    const points = (spec.slots || ["point"]).map((_, i) => [NumberSlot(`point ${i + 1}, x`), NumberSlot(`point ${i + 1}, y`)]);
    return {
      spec, op: "plot", slots: {points},
      inline() {
        const wrap = el("div", "bx-points");
        for (const [x, y] of points) wrap.append(line(sym("("), x.node, sym(","), y.node, sym(")")));
        return wrap;
      },
      filled: () => points.flat().some(s => s.filled()),
      collect(required) {
        const v = readAll(points.flat(), required);
        if (!v) return null;
        const pts = [];
        for (let i = 0; i < v.length; i += 2) pts.push([N(v[i]), N(v[i + 1])]);
        return [{kind: "plot", points: pts}, "plot " + pts.map(([x, y]) => `(${x.text}, ${y.text})`).join(" ")];
      },
    };
  }

  // The final answer: option cards (a ChoiceAnswer, sent as soon as one is picked), or a number (a ValueAnswer).
  function answer(spec, env) {
    if (spec.options) {
      return {
        spec, op: "answer", slots: {}, cards: true,
        inline() {
          const box = el("div", "bx-cards");
          spec.options.forEach((o, i) => {
            const b = el("button", "", o);
            b.type = "button";
            b.onclick = () => env.submit([[{kind: "choice", index: i + 1}, o]]);
            box.append(b);
          });
          return box;
        },
        filled: () => false,
        collect: () => null,
      };
    }
    const value = NumberSlot("answer");
    return {
      spec, op: "answer", slots: {value},
      inline: () => line(value.node),
      filled: () => value.filled(),
      collect(required) {
        const v = value.read(required);
        return v === null ? null : [{kind: "value", value: N(v)}, v];
      },
    };
  }

  const Kernels = {
    multiply: arithmetic("multiply"), divide: arithmetic("divide"), add: arithmetic("add"), subtract: arithmetic("subtract"),
    gcf: func("gcf"), lcm: func("lcm"), compare, ratio_compare: ratioCompare, plot, answer,
  };

  // Build the kernel for a spec ({kernel, slots, say, role}); env.submit(items) sends inputs right away (answer cards).
  function makeKernel(spec, env) {
    const make = Kernels[spec.kernel];
    return make ? make(spec, env) : null;
  }

  window.BoxKit = {el, sym, line, clean, NumberSlot, FractionSlot, RelationPicker, Kernels, makeKernel, SYM};
})();
