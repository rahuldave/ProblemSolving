"""What the choice and box inputs draw: the session's stage, and in the "steps" stage the frames to fill in.

Stages: "extract" (the story's decisions are still open; `decisions` lists every open one, the current one first,
each answerable in any order with a ChoiceAnswer that names its `decision`), "find_method" (solving, but more than
one method is named; `methods` lists them as cards for POST /method), "steps" (one method is named, or a step on a
decision's ✓ edge, the follow-up step or the final answer is next), "done". `allow_step` says a typed step (POST
/input) is taken too: at the decisions it skips them or gives a trap away, at the cards the tree finds the method.

    {"stage": "extract" | "find_method" | "steps" | "done", "phase": <the session's phase>, "prompt": "…",
     "allow_step": true,                                           # extract, find_method
     "decisions": [{"id": "1", "say", "options": […]}, …],          # extract (id: the decision's index)
     "methods": [{"id", "name", "idea", "best_when"?}, …],         # find_method
     "method": {"id": "unit_rate", "name": "Unit rate"},           # steps, while solving
     "frames": [frame, …]}                                         # steps

The steps are drawn at two levels.

**Kernels** (level 1): one per op of the step language and per StudentStep model: multiply, divide, add, subtract, gcf,
lcm, compare, ratio_compare, plot, and the final answer. A kernel knows only its op. Its operand slots are "number"
or "fraction" (an operand like 2/3 that isn't a whole number or a terminating decimal), "pair" for ratio_compare and
"point" for plot; the result box is implied by the op.

    {"kernel": "multiply", "slots": ["fraction", "number"], "say": "Scale up to 18", "role": "answer"}
    {"kernel": "answer", "options": ["first", "second", "equal"] | null}

**Components** (level 2): the layout of one method's steps as a unit, keyed by (question id, method id). Every skill
question's methods are registered (each `use` of to-decimal, simplify-fraction, common-multiple, cross-products, the
green call nodes in the graphs), and so are method-level layouts such as the ratio table. A step belongs to the
innermost frame on its `loc` that has a registered component; its `role` is the `out` name of the step in that
method's own step list (found by the step's index path, and inside a `repeat` by its place in the round). The same
component is drawn wherever the skill is called and when the skill question is itself the problem. A step with no
registered frame is drawn as a plain kernel (component null).

    {"component": "simplify-fraction/gcf" | null,
     "id": "…",                                       # one id per frame instance (per call), "mental", or "plain"
     "labels": {"x": "spoons", "y": "glasses"},      # the frame question's inputs, named from the problem
     "inputs": ["x", "y"],                            # in the question's quantity order (x is the top)
     "steps": [{"role": "g", "op": "gcf", "from": "x", "with": "y", "search": false}, …],  # the method's steps
     "done": [{"role": "g", "text": "GCF(4, 6) = 2"},                          # what the student already did here,
              {"role": "bk", "text": "6 × 2 = 12", "try": true}],              # and build-up tries toward the next
     "kernels": [kernel, …]}                                                   # the next step(s)

`from` and `with` are the inputs a step's first and second arguments come from, through the method's own data flow
(x1 starts as x, xk is x × k), which is how a component knows which row a step goes in. Labels come from the word
problem's quantity units ("spoons", "glasses") through the call bindings, falling back to the input descriptions of
the question.

Nothing in a spec holds the step's numbers: no operands, no results. `done` repeats steps the student already wrote.
Several frames (or several kernels in one frame) are alternatives or either-order steps: the student does any. Only
the routes of the named methods are drawn. Where the graph has a step done in the head (percent-of's 15 ÷ 100), a
"mental" frame offers the step after it.
"""

import build as engine

from .session import QuestionSession, step_candidate, WordProblemSession, answer_options, method_text

# ---------------------------------------------------------------- level 1: kernels


def is_fraction(x):
    """An operand that is best written as a fraction: not whole and not a terminating decimal (2/3, 5/3)."""
    return hasattr(x, "denominator") and x.denominator != 1 and not engine.terminates(x)


def slot(x):
    return "fraction" if is_fraction(x) else "number"


def kernel_for(op, operands, say, role=None):
    """The kernel for one step: its op and the shape of its operand slots. No values."""
    if op == "plot":
        k = {"kernel": "plot", "slots": ["point"] * len(operands)}
    elif op == "compare" and operands and isinstance(operands[0], tuple):
        k = {"kernel": "ratio_compare", "slots": ["pair", "pair"]}
    else:
        k = {"kernel": op, "slots": [slot(x) for x in operands]}
    k["say"] = say
    if role is not None:
        k["role"] = role
    return k


def answer_kernel(options):
    return {"kernel": "answer", "options": options or None}


# ---------------------------------------------------------------- level 2: components

def def_steps(qid, mid):
    return engine.methods_of(qid)[mid]["steps"]


def ordered_inputs(qid):
    q = engine.Q[qid]
    order = [n for part in q.get("quantities", {}).values() for n in part if n in q["inputs"]]
    return list(dict.fromkeys(order + list(q["inputs"])))


def method_layout(qid, mid):
    """A method's own steps in order: role (the step's `out`), op, and the input its first argument comes from."""
    origin = {n: n for n in engine.Q[qid]["inputs"]}
    out = []

    def walk(items):
        for it in items:
            if it["op"] == "all":
                for br in it["branches"]:
                    walk(br)
            elif it["op"] == "repeat":
                origin.update({k: origin.get(v, v) for k, v in it["init"].items()})
                walk(it["steps"])
            elif it["op"] in ("use", "map", "choose"):
                continue
            else:
                src = [origin.get(a[0] if isinstance(a, list) else a) if isinstance(a, (str, list)) else None
                       for a in it["args"]]
                origin.setdefault(it["out"], src[0])
                op = "ratio_compare" if it["op"] == "compare" and isinstance(it["args"][0], list) else it["op"]
                if all(s["role"] != it["out"] for s in out):
                    out.append({"role": it["out"], "op": op, "from": src[0], "with": src[1] if len(src) > 1 else None,
                                "search": "search" in it})

    walk(def_steps(qid, mid))
    return out


class Component:
    """A registered layout for one (question, method). The page draws it from `steps`, `inputs` and `labels`."""

    def __init__(self, qid, mid):
        self.qid, self.mid, self.id = qid, mid, f"{qid}/{mid}"

    def layout(self):
        return {"inputs": ordered_inputs(self.qid), "steps": method_layout(self.qid, self.mid)}


COMPONENTS: dict = {}


def register(qid, mid, cls=Component):
    COMPONENTS[(qid, mid)] = cls(qid, mid)


# every method of every skill question: the green call nodes
for _qid, _q in engine.Q.items():
    if _q["kind"] == "skill":
        for _mid in _q.get("methods", {}):
            register(_qid, _mid)
# method-level layouts
register("missing-value", "ratio_table")
register("compare-fractions", "ratio_table")


# ---------------------------------------------------------------- which frame a step is in, and its role

def def_item(qid, mid, ip, st, variant):
    """The step of `qid`'s method `mid` that a route step comes from: by index path, then by place in a repeat."""
    items, path, item = def_steps(qid, mid), list(ip), None
    while path:
        item = items[path.pop(0)]
        if item["op"] == "all" and path:
            items = item["branches"][path.pop(0)]
            continue
        break
    if item is not None and item["op"] == "repeat":
        rep = next((s for s in variant["steps"] if s["op"] == "repeat" and tuple(s["loc"]) == tuple(st["loc"])), None)
        j = next((j for j, s in enumerate(rep["steps"]) if s is st or s == st), None) if rep else None
        item = item["steps"][j] if j is not None else None
    return item


def frame_of(st, variant):
    """(frame key, component or None, call level) for a route step."""
    loc = tuple(st.get("loc", ()))
    for i in range(len(loc) - 1, -1, -1):
        comp = COMPONENTS.get(loc[i][:2])
        if comp:
            return (loc[:i], loc[i][:2]), comp, i
    i = len(loc) - 1
    return (loc[:i], loc[i][:2] if loc else None), None, i


def role_of(st, variant, comp, i):
    if comp is None:
        return None
    item = def_item(comp.qid, comp.mid, st["loc"][i][2], st, variant)
    return item.get("out") if item else None


def frame_labels(st, variant, i, top_label):
    """Labels for the frame question's inputs: resolve each through the call's `with` binding to the problem's own
    input (named from the story's quantities), else use the frame question's input description. Two inputs with
    the same short label (shots and shots) are named by what they count instead (made shots, attempts)."""
    loc = tuple(st.get("loc", ()))
    if not loc:
        return {}
    qid = loc[i][0]
    call = next((c for c in variant["calls"] if tuple(c["loc"]) == loc[:i]), None) if i else None
    out, names = {}, {}
    for k, desc in engine.Q[qid]["inputs"].items():
        name = k if call is None else call["with"].get(k)
        names[k] = name
        out[k] = (top_label(name) if isinstance(name, str) else None) or desc
    shown = [v for v in out.values()]
    for k, v in out.items():
        if shown.count(v) > 1 and isinstance(names[k], str):
            out[k] = top_label(names[k], long=True) or v
    return out


def frame_id(key):
    """A stable id for one frame instance (one call of a component): the page keys its memory by it."""
    locs, comp = key
    path = lambda ip: ".".join(_letters(i) for i in ip)  # no digits in a spec outside its text fields
    return " › ".join(f"{q}/{m}@{path(ip)}" for q, m, ip in locs) + " | " + "/".join(comp or ())


def _letters(n):
    out = ""
    while True:
        n, d = divmod(n, 26)
        out = chr(97 + d) + out
        if not n:
            return out
        n -= 1


def mental_kernels(q: QuestionSession):
    """Where the graph has a step done in the head (percent-of: 15 ÷ 100 first), the step after it, as an
    alternative to the skipped step: one kernel per live route that can start that way."""
    if q.tree_entries is None or q.history:
        return []
    mental = {m for e in q.tree_entries if e.get("mental") for m in e["methods"]}
    named = set(q.named_methods())
    out = []
    for r, at in q.live.items():
        v, env, trace, vis = q.routes[r]
        if at or v["method"] not in mental or v["method"] not in named or len(vis) < 2:
            continue
        c = step_candidate("x", q.routes[r], 1)
        skip, then = (engine.say(trace[vis[p]][0].get("say"), env) for p in (0, 1))
        k = kernel_for(c.op, c.operands, f"Or, with “{skip[:1].lower()}{skip[1:]}” done in your head: "
                                         f"{then[:1].lower()}{then[1:]}")
        if not any(m["kernel"] == k["kernel"] and m["slots"] == k["slots"] for m in out):  # one per shape
            out.append(k)
    return out


def frames_for(q: QuestionSession, top_label):
    """One frame per frame instance that holds a live route's next step, with the kernels for those steps. Only the
    methods the student's steps are named for are drawn (a route only building up toward a step isn't)."""
    frames = {}
    named = set(q.named_methods())
    for r, st, c in q.next_steps():
        v, env, trace, vis = q.routes[r]
        if v["method"] not in named:
            continue
        key, comp, i = frame_of(st, v)
        role = role_of(st, v, comp, i)
        k = kernel_for(c.op, c.operands, c.say, role)
        if key not in frames:
            done = []  # the steps done in this frame, each after the build-up tries toward it (6 × 2 = 12 before 6 × 3)
            for p in range(q.live[r] + 1):
                pst, args, result = trace[vis[p]]
                pkey, pcomp, pi = frame_of(pst, v)
                if pkey == key:
                    prole = role_of(pst, v, pcomp, pi)
                    done += [{"role": prole, "text": t, "try": True} for t in q.tries.get((r, p), [])]
                    if p < q.live[r]:
                        done.append({"role": prole, "text": engine.expression(pst, args, result)})
            f = {"component": comp.id if comp else None, "id": frame_id(key), "labels": frame_labels(st, v, i, top_label)}
            if comp:
                f.update(comp.layout())
            frames[key] = {**f, "done": done, "kernels": []}
        add_kernel(frames[key]["kernels"], k)
    out = list(frames.values())
    mk = mental_kernels(q)
    if mk:
        out.append({**plain_frame(mk), "id": "mental"})
    return out


def add_kernel(kernels, k):
    """Steps of the same shape and role share a kernel; their say texts are joined."""
    for m in kernels:
        if all(m.get(f) == k.get(f) for f in ("kernel", "slots", "role")):
            if k["say"] and k["say"].lower() not in m["say"].lower():
                m["say"] += f", or {k['say'][:1].lower()}{k['say'][1:]}"
            return
    kernels.append(k)


def plain_frame(kernels):
    return {"component": None, "id": "plain", "labels": {}, "done": [], "kernels": kernels}


# ---------------------------------------------------------------- sessions → specs

def method_card(q: QuestionSession, mid):
    """A method card: its name and idea for these numbers, and when it's best only where that holds whatever the
    numbers (a best_when about the values, like "{d} is a multiple of {b}", may be false for these)."""
    m = q.methods[mid]
    card = {"id": mid, "name": m["name"], "idea": method_text(q.qid, mid, "idea", q.values)}
    best = method_text(q.qid, mid, "best_when", q.values)
    if best:
        card["best_when"] = best
    return card


def question_labels(qid):
    inputs = engine.Q[qid]["inputs"]
    return lambda name, long=False: inputs.get(name)


def word_problem_labels(s: WordProblemSession):
    """A bound input is named by the story's quantity unit (spoons, glasses), else by the question's description;
    `long` names it by what it counts (Maya's made shots)."""
    qs = {x["id"]: x for x in s.wp["quantities"]}
    inputs = engine.Q[s.plan["question"]]["inputs"]

    def label(name, long=False):
        src = s.plan["binds"].get(name)
        if isinstance(src, str) and src in qs:
            return (qs[src].get("counts") or qs[src].get("unit")) if long else (qs[src].get("unit") or qs[src].get("counts"))
        return inputs.get(name)
    return label


def question_spec(q: QuestionSession, phase=None, top_label=None):
    ask = q.ask()
    out = {"stage": "steps", "phase": phase or q.phase, "prompt": ask["text"]}
    if q.phase == "answer":
        return {**out, "frames": [plain_frame([answer_kernel(answer_options(q.qid))])]}
    if q.phase != "steps":
        return {**out, "stage": "done", "prompt": "", "frames": []}
    live = q.named_methods()
    if len(live) != 1:  # the method cards, or the first step (the tree finds the method): both are taken
        prompt = ("How do you want to start? Pick a method, or write your first step." if not q.history else
                  f"That step starts {q.names(live)}. Pick one, or write your next step.")
        return {"stage": "find_method", "phase": out["phase"], "prompt": prompt, "allow_step": True,
                "methods": [method_card(q, m) for m in live]}
    frames = frames_for(q, top_label or question_labels(q.qid))
    return {**out, "method": {"id": live[0], "name": q.methods[live[0]]["name"]}, "frames": frames}


def word_problem_spec(s: WordProblemSession):
    ask = s.ask()
    if s.phase == "extract":
        pre = s.pre_step()
        if pre:  # a step on a decision's ✓ edge (convert minutes to hours)
            st, args, result = pre
            k = kernel_for(st["op"], list(args), engine.say(st.get("say"), s.run["env"]))
            return {"stage": "steps", "phase": "extract", "prompt": ask["text"], "frames": [plain_frame([k])]}
        # every open decision, in any order (the graph's `all` block); a first step or a giveaway can be typed too
        return {"stage": "extract", "phase": "extract", "prompt": ask["text"], "allow_step": True,
                "decisions": [{"id": str(d["decision"]), "say": d["text"], "options": d["options"]}
                              for d in ask["decisions"]]}
    if s.phase == "solve":
        return question_spec(s.question, "solve", word_problem_labels(s))
    if s.phase == "then":
        st, args, result = s.then_step()
        k = kernel_for(st["op"], list(args), engine.say(st.get("say"), s.run["env"]))
        return {"stage": "steps", "phase": "then", "prompt": ask["text"], "frames": [plain_frame([k])]}
    if s.phase == "answer":
        return {"stage": "steps", "phase": "answer", "prompt": ask["text"],
                "frames": [plain_frame([answer_kernel(ask["options"])])]}
    return {"stage": "done", "phase": s.phase, "prompt": "", "frames": []}


def spec(session):
    if isinstance(session, WordProblemSession):
        return word_problem_spec(session)
    return question_spec(session)
