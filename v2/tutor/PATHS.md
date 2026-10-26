# Plan for finding a student on any path of the graph

The tutor matches a step only against the next step of each live route. A student who skips steps, writes
the answer first, or writes two steps in one expression gets a refusal. The plan replaces matching by
position with matching against every quantity on every path. When a step fits more than one path, the
tutor asks the student to break the step down until one path is left.

## Terms

| Term | Meaning |
|---|---|
| path | One route through a method's graph, from the givens to the answer, as `build.py` expands it today. |
| quantity | A value that a path computes or reads, with its name, its value and the step that makes it. |
| role | The kind of quantity: given, goal, setup, working or answer. |
| given | A number from the story or the question, for example 4 spoons with 6 glasses. |
| goal | The unknown that the question asks for, for example "x is the extra spoons for 18 glasses". |
| setup | The equation that links the givens and the goal, for example `4/6 = x/18`. |
| working | A quantity between the setup and the answer, for example the scale factor 3. |
| answer | The quantity the question asks for, for example 12. |
| trap path | A path from a wrong reading of the story, with its own quantities and its own wrong answer. |
| statement | One thing the student writes: a number, an expression, an equation, a given or a goal. |
| consistent set | The paths that fit every statement the student has made so far. |
| decomposition | The student says how a quantity was made, one step back along a path. |
| done in the head | A quantity that a path needs before the student's statement, but that the student did not write. |

## What the student met

On 18 October the student used `lemonade-more-sugar` with Claude as the setup mode. The server log has
the endpoints but not the text, so the cases below are a local replay of short cuts.

| Statement | What the tutor said |
|---|---|
| `12` at the start | "Pick a number from 1 to 2." The tutor read 12 as an option number. |
| `4/6*18 = 12` | "I can't tell which reading it comes from." |
| `4*3 = 12` | The same refusal. The scale factor 3 was done in the head. |
| `x/18 = 4/6` | "I couldn't read" the setup. |
| `18/6 = 3`, then `12` | "That looks like an answer. Write the step." |
| `3*8 = 24` for `3/5 = x/40` | "How Inverse rate starts." The step is the last step of Scale factor. |

The Claude reader cannot help. Its output schema holds one operation on two numbers, a choice or a final
value. It has no form for an expression, a setup, a given or a goal.

## How the matching works

### Index every quantity

1. For each example, take every path that `build.py` expands, trap paths included.
2. Give each quantity a role. Inputs are givens. The question's prompt gives the goal and the setup. The
   last step is the answer. Every other step is working.
3. Merge quantities that two paths compute in the same way, so that the order of an `all` block adds no
   new quantities. Routes 6 and 7 of `missing-value` differ only in order and share all quantities.
4. Keep an index from each value to the quantities that have it. About 47% of values belong to more than
   one quantity, so the value alone is not enough.

The index is built from the same expansion as the diagrams, so the tutor and the diagrams stay in
agreement.

### Match a statement

A statement fits a quantity when both of these are true:

- **The value is equal.** The value check uses exact fractions and the rounding rules of `Number.close_to`.
- **The expression maps onto the path.** Each number in the expression is a given or a quantity that the
  student already has. It can also be a quantity done in the head on the same path. A bare number has no
  expression and fits every quantity with its value.

Then the tutor keeps the paths in the consistent set that contain the quantity. Each path also keeps its
own position. The quantities between the old position and the new one become done in the head.

### Outcomes

| The statement fits | The tutor says | Built |
|---|---|---|
| a quantity on a correct path | It is right, and names the quantity, for example "3 is the scale factor". | Partly. It shows the step that makes the quantity, not its name. |
| a quantity on a trap path only | It names the misreading, for example "16 uses all 24 glasses". | Yes |
| a quantity on a correct path and a trap path | It is right so far. The reading is still open. | Yes, with a note on the trap |
| the operation of a quantity, with a wrong result | It is an arithmetic slip, with the expected result. | Yes |
| no quantity, with correct arithmetic | The arithmetic is right, but the step does not lead to the answer. | No. It says the step isn't recognized. |
| nothing | It asks the student to write the step again, or to take a hint. | Yes |

### Break a step down

The tutor starts a decomposition when one of these is true:

- More than one method is in the consistent set.
- The statement leaves quantities done in the head, and the decomposition depth is "to the givens".
- A correct path and a trap path both fit.

A decomposition goes back one step at a time:

1. The tutor asks how the student made the quantity, for example "What two numbers make 12, and how?".
2. The answer must fit a parent of that quantity on a path in the consistent set. The paths that do not
   fit leave the set.
3. If a number in the answer is a working quantity, the tutor asks about that number next.
4. The decomposition stops at the givens, or when one path is left, as the depth setting says.

If the student cannot answer, the hint shows the parent step on the most likely path as a blank, for
example `? × ? = 12`. In Boxes mode the question is a kernel with empty operands.

**Depth setting.** "To the givens" makes the student say every step. "Until unique" asks only enough to
find the path. The default is "to the givens", because saying the decomposition is a skill to practise.

### Word problems

- **Givens and goal as statements.** A student can write "4 spoons go with 6 glasses" or "x is the extra
  spoons". The parser and the Claude reader turn these into given and goal inputs. A given settles the
  rate pair decision, and a goal settles the delta or total decision.
- **Decisions that the work settles.** Any statement that fits only the correct reading settles every
  decision that it depends on. Today only a first step does this.
- **Fewer questions.** The tutor does not ask a decision with one option. It asks a decision only when the
  student's work leaves the decision open.
- **Same answer, wrong reading.** If a trap path gives the correct answer, the answer cannot show the
  reading. The tutor then asks for a decomposition, because the step back shows the pair that the student
  used.

## Input changes

| Input | Example | Change |
|---|---|---|
| expression | `4/6 × 18 = 12`, `4 × 18 ÷ 6 = 12` | New kind with a tree of operations, in the parser and the Claude schema. |
| setup | `x/18 = 4/6`, `4:6 = x:18` | New kind with two ratios and one unknown. |
| given | "4 spoons with 6 glasses" | New kind that names two numbers that go together. |
| goal | "x is the extra spoons" | New kind that names the unknown. |
| bare number | `12` | Read as a value in every phase, and never as an option number when the number is larger than the list. |

The Claude reader still only reads. The session judges every input, as `MODES.md` says.

## A classifier on the path

The question is whether a trained or statistical classifier helps the tutor find the path. The tutor can
use one in the places below, and path finding is not one of them.

| Job | Needs a classifier | Plan |
|---|---|---|
| Find the paths that fit the statements | No | Exact matching and decomposition give a definite answer, with a reason the student can see. |
| Read free text into statements | Yes, and it exists | The Claude reader, with the new kinds in its schema. |
| Order the open paths for a hint | Helpful | Start with a fixed order from the data, for example the default method. Later, use counts from the logs. |
| Decide how much decomposition to ask for | Helpful, later | Knowledge tracing, a model of which skills a student has shown, can lower the depth for skills she has. |
| Find steps that no path has | Helpful, offline | Claude reads the logged statements that matched nothing and proposes new paths. An author checks each one before it goes into the data. |

A classifier inside path finding would guess where an exact check is possible. A guess gives wrong
feedback with confidence, and decomposition removes the need for the guess. A classifier is useful only
to choose which question or hint comes first.

### Jev, not used for now

Jev is a model from TypeSafe AI that returns a choice among named options, with probabilities. Jev could
pick a path when more than one path is open, from the words of the student and her earlier problems. The
plan does not use Jev for now, because decomposition finds the path exactly and makes the student say her
steps. If decomposition asks too many questions, try Jev on cases from the logs.

## Logging

The tutor writes one line of JSON for each statement to `v2/logs/statements.jsonl`, or to the path in
`TUTOR_LOG`. The line has the session id, the problem, the phase, the text, the reading used, the
consistent set before and after, and the feedback. The line has no name, address or other detail about the
student. The student's own text is kept, cut to 2000 characters.

On the server, the dokku storage mount `/var/lib/dokku/data/storage/problemsolving-logs` is mounted at
`/app/v2/logs`, so the log survives a restart or a deploy. Copy it with this command:

```sh
ssh dokku enter problemsolving web cat /app/v2/logs/statements.jsonl > statements.jsonl
```

Someone with access to the host can copy the file from the host path with `scp` instead.

## Steps of the work

Each step ends with `cd v2 && python3 build.py --no-site` and `uv run pytest`. Each step also gets the
adversarial review that `CLAUDE.md` asks for, before it is merged.

1. **Log every statement.** Add the log line and a test that reads it back.
2. **Index the quantities.** Build the index of quantities and roles from the existing expansion. Test that
   every quantity on every path is in the index, and that the index agrees with the diagrams.
3. **Match any quantity.** Replace matching by position with matching against the index and the consistent
   set. Accept a bare answer in every phase. Fix the "Inverse rate starts" label.
4. **Read expressions and setups.** Extend the parser, `models.py` and the Claude schema. Add eval cases for
   the new kinds. Run the eval only after the user agrees, because each full run costs about $0.6.
5. **Break steps down.** Add the decomposition questions, the depth setting, and the Boxes kernel with
   empty operands.
6. **Word problems.** Add givens and goals, and settle decisions from any step. Drop decisions with one
   option. Use decomposition for a trap with the same answer.
7. **Collapse orders.** Show one node for each quantity in the diagrams, so that an `all` block no longer
   multiplies the routes.
8. **Order hints from data.** Use the logs to order open paths for hints. Consider knowledge tracing after
   there are enough logs.

## Tests

- **Automatic students.** Today one automatic student types every step of every route. Add these students:
  - a student who skips one step
  - a student who writes the answer first
  - a student who joins two steps in one expression
  - a student who writes the setup first

  Each student must reach the answer, and decomposition must recover the path.
- **The replay cases.** Every case in the table at the top becomes a test with the expected feedback.
- **Traps.** For each trap, a student who writes the trap's answer first must get the misreading named,
  either at once or after decomposition.
- **Agreement.** `test_boxes.py` keeps checking that Type and Boxes hold the same paths after every step.

## Risks

- **Rounded values.** A student who writes 0.67 for 2/3 must still fit. The match uses `close_to`, but an
  expression with a rounded number can drift. The check must allow the drift that the rounding causes.
- **Search steps.** The ratio table builds up by 2, 3 and so on. A quantity in a search has many values,
  so the index needs a rule for them, as the classifier has today with `on_track`.
- **Compare and plot questions.** These questions end in a relation or a graph, not a number. The answer
  check and the decomposition need a form for them.
- **Size.** Some questions have more than 1,000 routes. The index must merge quantities, or matching gets
  slow.
- **Too many questions.** Decomposition to the givens on every step can tire a student. The depth setting
  and, later, knowledge tracing control the load.
