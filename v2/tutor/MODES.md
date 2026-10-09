# Three ways in, one walk through the graph

The tutor accepts a student's work in three ways: typed steps, input boxes, or free text read by Claude. All three
produce the same typed inputs (`tutor/models.py`). The session walks the same graph with them, so the extraction,
method, trap and route logic lives in one place (`tutor/session.py`) and no mode re-implements it.

## How it works today, on "Lemonade: more sugar"

> Joe has 6 cups of water and 4 spoons of sugar, which make 6 glasses of lemonade. He needs 18 more glasses. How many
> more spoons of sugar does he need?

The data is `word-problems/lemonade-more-sugar.json`, its generated trap analysis is in
`trees/word-problems.json`, and the graph is `svg/wp-lemonade-more-sugar.svg`. The graph has two frames, and the
session walks them in order.

**1. Extract (the left frame).** There are five decisions, which the graph lets a student take in any order. The
session asks the first open one and lists every other open one beside it (`ask()["decisions"]`), so any of them can be
answered next: a `ChoiceAnswer` may name its `decision`, the terminal takes `b2` for option 2 of decision b, and
Claude's choice for "Decision 3" is submitted as it comes. Each decision's options are shuffled with a fixed seed.

| Decision | Correct | Traps (wrong answer it leads to) |
|---|---|---|
| question_type | missing value | (none, so it is only announced, not asked) |
| rate_pair | sugar with glasses | sugar with water → 12, *the same answer*, so the answer can't catch it |
| correspondence | sugar/glasses both sides | glasses/sugar on one side → 27, given away by `6 × 18 = 108`, `18 ÷ 4 = 4.5` |
| delta_vs_total | 18 is the extra | use 24 → 16 (`4 × 24 = 96`, …); 18 is the total, then subtract 4 → 8 |
| multiplicative | scales | adds 18 → 18 |

The student picks an option by number. A correct pick settles that decision. When the correct option has steps of
its own on its ✓ edge (train-minutes' `90 ÷ 60 = 1.5`, pancakes' `2 × 12 = 24`), the session asks for them next. A trap
pick explains the trap and its wrong answer, then asks that decision again. A trap that gives the same answer as the
correct reading (sugar with water → 12) says so: "That reading happens to give the same answer, 12, but for the wrong
reason", as the graph's "same answer as the correct reading!" does.

The student can also skip the decisions and start computing (`_jump`). That step is classified, in order, against:
the steps on an open decision's ✓ edge (`90 ÷ 60` settles the conversion; it isn't read as a solving step); the
correct reading's first steps (a match fills in every remaining decision, "that step means you read the story right",
and continues); and each trap's giveaways, which are the trap's own steps on its branch (`18 + 6 = 24`,
`80 − 15 = 65`), plus its question's first steps that no correct reading starts with, plots and comparisons included
(`6 x 18 = 108` matches the flipped-ratio trap, so the session moves to that decision). The trap's own steps are in
the graph's "gives itself away" label too.

**2. Bind.** The decisions fix the question (`missing-value`) and its inputs: a = 4 spoons, b = 6 glasses,
d = 18 more glasses. The session says so ("So the story gives: …") and starts a `QuestionSession` on
`Solve 4/6 = x/18`.

**3. Solve (the right frame, the same graph as the missing-value page).** `build.routes_for` expands six methods
into nine concrete routes:

| Method | Route |
|---|---|
| cross_multiply | 4 × 18 = 72 → 72 ÷ 6 = 12 |
| scale_factor | 18 ÷ 6 = 3 → 4 × 3 = 12 |
| unit_rate (uses to-decimal) | 4 ÷ 6 ≈ 0.667 → 2/3 × 18 = 12 |
| inverse_rate (uses to-decimal) | 6 ÷ 4 = 1.5 → 18 ÷ 1.5 = 12, *or* 4 × 25 = 100 → 6 × 25 = 150 → 150 ÷ 100 = 1.5 → 18 ÷ 1.5 = 12 |
| ratio_table | 6 × 3 = 18 → 4 × 3 = 12 (build-up steps like 6 × 2 = 12 are "on track") |
| simplify_then_scale (uses simplify-fraction) | GCF(4, 6) = 2 → 4 ÷ 2 → 6 ÷ 2 (either order) → 18 ÷ 3 = 6 → 2 × 6 = 12, or start at 4 ÷ 2 |

The first step is classified against `trees/missing-value.json`. Every tree entry the step fits counts, exact and
wildcard alike (the exact one only decides the arithmetic feedback), and the routes then filter by the actual numbers.
So a step the graph draws for two methods keeps both (train-minutes' `150 ÷ 3 = 50`: simplify then scale, or unit
rate), and the tree's `next` level ("Which next step?") decides. After that, each step is matched against the next
step of every route still live. Each route keeps its own position, which is what makes build-up and in-the-head steps
work. A route that is only building up toward its step (`8 × 12 = 96` on the way to `8 × 125 = 1000`) stays live, but
the session names only the methods the step is a step of (`named_methods()`). Where the method lets the student
choose (any common factor when dividing out factors, as the tree's `common_factor` says; any power of ten when
scaling to 10, 100 or 1000), the route is re-run with the student's own choice (`72 ÷ 8 = 9`, `4 × 250 = 1000`). Right
step with wrong arithmetic is a slip: the student gets one retry, then the tutor gives the value and carries on.

**4. Answer.** For a word problem the session reports the answer of the route the student walked (12), runs any
follow-up steps from the chosen reading (none for the correct one), and asks for the answer in the story's terms. An
equality-only route (simplify → `3:4 ≠ 5:7`) can't say which is better, so the question starts again for another
method.

**Limits seen in a scripted run:**

- Once the first step has fixed a method, the student can't switch. `4 x 18 = 72` then `6 x 3 = 18` is "not
  recognized".
- A bare `12` mid-route is refused as "looks like an answer".
- Every entry has to be in the parser's notation.

## Mode 1: type steps (existing)

Text → `parse.parse_all` → typed readings → `session.submit_readings`.

## Mode 2: guided (skill UIs once the method is known)

Every mode runs the same three stages: extract → find the method → solve. The method is found either way: the
student may pick a method card (the guided setup's default, kept as the MVP), or the tutor finds the method from the
first step they write, through the tree and its "Which next step?" level. The guided setup takes a typed step at
every stage: at the decisions (to skip them, or a giveaway that names a trap) and at the method cards.

| | Extraction | Finding the method | Solving steps |
|---|---|---|---|
| Type steps | options, hand-rolled parser | first step(s) parsed, classified by the tree | parsed |
| Talk it through | Claude reads free text | Claude reads the first step(s), the tree classifies | Claude reads each step |
| Guided | parser (Claude later, behind a switch) | parser (Claude later, behind a switch) | the skill's widget |

The guided mode is modelled on the AoPS and Beast Academy problem screens:

- The scaffold is a sentence or an equation with blanks in it, and a Check button checks it.
- Help comes in layers.
- The student never has to learn a notation.

How it runs:

- **Extraction and finding the method:** every open decision is drawn as its own set of option cards, answerable
  in any order, with "or just start solving: write your first step" below. A step on a decision's ✓ edge is a plain
  kernel. Then come the method cards, with "or write your first step". Once exactly one method is named, each
  remaining step becomes that skill's widget, built from the route's next candidate. Where the graph has a step done
  in the head (percent-of: `15 ÷ 100` first), the step after it is offered as an extra kernel ("Or, with … done in
  your head").
- **Layout:** each step is drawn by a kernel for its op, placed by the component of the method it sits in (see
  below).
- **Boxes:** each box takes one number (`3`, `0.75`, `2/3`).
- **Output:** the kernels build a typed `StudentInput` and POST it to `/api/sessions/{id}/step`, so nothing is
  parsed. The spec never carries the expected values.
- **Fallback:** the page's Steps selector switches to typing at any point.

### Kernels and components

`GET /api/sessions/{id}/boxes` returns `{"stage": "steps", "frames": [...]}` once one method is live
(`tutor/skills.py` documents the whole spec). The method cards come as `{"stage": "find_method"}` while more than
one method is named. The page draws it at two levels:

- **Kernels** (`static/modes/kernels.js`): one per op of the step language and per `StudentStep` model: multiply,
  divide, add, subtract, gcf, lcm, compare, ratio_compare, plot, and the answer. Each is built from three primitives,
  `NumberSlot`, `FractionSlot` and `RelationPicker`. An operand slot is a fraction when the operand is one, like 2/3
  in `2/3 × 18`. A kernel knows only its op. It draws itself inline, or hands its slots to a component.
  Spec: `{"kernel": "divide", "slots": ["number", "number"], "say": "…", "role": "answer"}`.
- **Components** (`static/modes/components.js`, and the registry in `skills.py`): the layout of one method's steps
  as a unit, keyed by `question/method`. Every method of a skill question is registered: these are the green call
  nodes in the graphs, to-decimal, simplify-fraction, common-multiple and cross-products. Method-level layouts are
  registered the same way: the ratio table for `missing-value/ratio_table` and `compare-fractions/ratio_table` is a
  component made of multiply kernels. Examples:
  - simplify-fraction: the GCF, then the top and bottom divisions under a fraction bar;
  - to-decimal/divide: the stacked fraction `= [ ]`;
  - to-decimal/power_of_ten: scale the top and the bottom, then read the decimal off;
  - cross-products/diagonals: one row per diagonal.
- **Frames:** each step belongs to the innermost frame on its `loc` that has a registered component. Its `role` is
  the step's `out` in that method's own step list, found by the step's index path, or by its place in a `repeat`
  round. The frame also carries the method's steps with the input each one comes from (`from`, `with`), traced
  through the method's data flow. That data, not the say text, puts a step in the top or the bottom row. Labels name
  the frame question's inputs from the problem: the call's `with` bindings lead to the story's quantity units
  ("spoons", "glasses"), and otherwise to the input descriptions; two inputs with the same unit are named by what
  they count ("Maya's made shots", "Maya's attempts"). A frame also lists the steps already done in it, and the
  build-up tries toward its next step (`"try": true`), and carries an `id` for its call. So a ratio table draws only
  its own numbers, whichever way they were entered, and a second call of the method gets a table of its own.
- **Same component everywhere:** the skill's component is the same whether the skill is called inside another
  question (missing-value's unit_rate, compare-fractions' decimal, add-fractions' simplify…) or is itself the
  problem. `tests/test_boxes.py` checks this for every registered component.
- **Without a component:** a step with no registered frame, such as missing-value's own `2/3 × 18 = 12`, the
  follow-up step or the answer, is drawn as a plain kernel.

## Mode 3: talk it through (Claude)

The student types whatever they like: "I think the 18 is just the extra ones", "6 goes into 18 three times so
it's 4 times 3, 12". Claude turns that into the typed inputs the session already understands. It interprets the
text; it never judges it. The deterministic session still decides what is right.

- **Extraction:** given the story and every open decision with its options, Claude returns a `ChoiceAnswer` per
  decision answered, in any order. If the student is computing instead, it returns a step. A choice for a decision
  that isn't listed is reported, not dropped.
- **Method and steps:** given the bound question, the steps so far and the live methods, Claude returns zero or
  more `StudentStep`s in the order the student did them. A sentence can hold several steps, and an in-the-head step
  is just left out. Claude returns `none` when nothing can be read.
- **Answer:** a `ValueAnswer` or a `ChoiceAnswer`.
- **What Claude returns matches what the graph accepts:** only the steps the student states. "Two thirds of 18 is
  12" is just `2/3 × 18 = 12` (missing-value has no in-the-head step in the graph, so the tutor doesn't recognize it);
  "15% of 80 is 12" is `0.15 × 80 = 12`, which percent-of's graph allows with `15 ÷ 100` done in the head. A quantity
  named with its value ("it's 3 times as many glasses") is the calculation it states, `18 ÷ 6 = 3`.
- **Fidelity is measured, not assumed:** an eval set (`tutor/evals/`) pairs a context and a student utterance with
  the expected typed input(s). The automatic student generates the contexts. The utterances are hand-written plus
  model-written paraphrases, including the traps, rounding, words for operations, several steps at once and
  off-topic text. A runner scores exact typed-input match per case, and the prompt is tuned against that score.

## The page

At the top, *Type steps · Guided · Talk it through* switches the input mode at any point. The session and the thread
are shared, so switching modes keeps your place in the problem.

## Later: choosing the way automatically

The two selectors are a default for now. Later, a router in front of the three ways can choose one per entry:

- notation (`18 / 6 = 3`) goes to the parser;
- prose goes to Claude;
- a student who is stuck or keeps slipping is offered the boxes or the choices.

The router can be Claude, or a small trained classifier where cost or latency matters. Either way it only picks the
way. The session still decides what is right.
