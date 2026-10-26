# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Solution methods for ratio, fraction and percent questions, classified by the first step a student takes (and the
second step where methods share a first step). The data is meant for an app that recognizes a student's method from
their first step and gives method-specific help. `v2/tutor/` is a prototype of that app. `v1/` is the older
hand-written version, kept only for comparison. Work in `v2/`.

## Commands

```sh
cd v2 && python3 build.py            # validate all data, regenerate every output (trees, markdown, svg, website)
cd v2 && python3 build.py --no-site  # skip the Quarto website
cd v2 && python3 build.py --demo     # also run the first-step classifier demo
uv run pytest                        # from the repo root (pytest config puts v2/ on the path)
uv run pytest v2/tests/test_tutor.py -k <name>   # a single test
cd v2 && uv run python -m tutor [<word-problem-id> | <question-id>:<example#> | --list]   # terminal tutor
cd v2 && uv run uvicorn tutor.web:app --reload   # web tutor at http://127.0.0.1:8000
cd v2 && uv run python -m tutor.evals.run [--category X] [--limit N] [--dry]   # eval the Claude reader (real API calls, ~$0.6 a full run)
```

The Claude way reads `ANTHROPIC_API_KEY` (or `ANTHROPIC_KEY`) from the environment or a git-ignored `.env` at the repo
root. pytest never calls the API; the eval runner does, so ask before running it.

`build.py` uses only the standard library and exits non-zero when any check fails ("SOME CHECKS FAILED"). Graph
images need the mermaid CLI (`mmdc`) and the website needs Quarto. Without them the build still validates and writes
the JSON and markdown. Deployment: `git push dokku main` (the `Dockerfile` serves `tutor.web:app`, and `app.json`
health-checks `/healthz`).

## Source vs generated

Hand-edited sources live in `v2/`: `questions/*.json`, `word-problems/*.json`, `vocabulary.json` (the step language
`say`/`use`/`all`/`choose`, reductions, classification levels and graph grammar) and `extraction.json` (extraction
concepts and how a decision's options pick the question and its numbers).

Everything else is written by `build.py`: `v2/trees/`, `v2/graphs/`, `v2/svg/`, `REPORT.md`, `docs/` (rendered
site, served by GitHub Pages) and `site/` (git-ignored Quarto sources). Don't hand-edit these. Change the source or
`build.py`, then rebuild and commit the regenerated outputs along with the change.

## Architecture

- **`v2/build.py` is the engine for both the build and the tutor.** It loads all the JSON when it's imported (module
  globals `VOCAB`, `EXTRACTION`, `Q`, `WP`). It expands skills, `all` blocks and reductions into concrete routes,
  executes every method on every example with exact `Fraction` arithmetic, checks the answers, and derives the
  first-step trees. It also checks word problems, including the wrong answer each trap leads to and the first steps
  that give a trap away, and draws every diagram in one Mermaid graph grammar.
- **The tutor imports the engine** (`import build as engine` in `tutor/session.py`, `tutor/web.py` and the tests). It
  expands routes the same way the diagrams do, so the two always agree. At runtime it also reads the generated
  `trees/<question>.json` and `trees/word-problems.json`, so rebuild after changing the question data.
- **Tutor pipeline:** input → typed pydantic `StudentInput` (`tutor/models.py`) → `session.submit_input` →
  `tutor/classifier.py` (`RuleClassifier.classify(step, candidates)`; any object with this interface can replace it).
  A step counts for every first-step tree entry it fits, exact or wildcard, and the routes then filter on the actual
  numbers. The exact match only decides the arithmetic feedback. `named_methods()` leaves out routes that are only
  building up toward their step. The session classifies the first one or
  two steps against the tree, then against the next step of each route still alive. Each route keeps its own
  position, so build-up steps and steps done in the head don't lose the other routes. Word-problem sessions start
  with the extraction decisions. A student who skips them is classified against the correct reading and against
  each trap's giveaway steps.
- **Any step, any number** (`tutor/PATHS.md`, the plan). `tutor/paths.py` indexes every quantity on every route
  (and every reading of a word problem, traps included) from the same expansion as the diagrams. A step that is no
  live route's next step is matched further along a route. Only the skipped steps the statement needs are done in
  the head; the others are still to write (owed). A bare number is the answer or a quantity on some route.
  `ambiguity()` and `open_readings()` say what is still open.
- **Three ways in, one session** (`tutor/MODES.md` is the design). The page has two selectors: Setup (reading the
  story, then finding the method) is Choices, Type or Claude; Steps is Boxes, Type or Claude. Every way produces
  `StudentInput`s for the same session, so the graph logic lives only in `session.py`:
  - Type: `tutor/parse.py` turns text into inputs (`/input`).
  - Choices and Boxes: `tutor/skills.py` turns session state into specs (`/boxes`, `/method`), and the page posts
    typed inputs (`/step`). Specs never carry expected values. Boxes has two levels of component: kernels, one per
    step op (`static/modes/kernels.js`), and components registered by (question, method) for the skills, the green
    call nodes, and for method layouts like ratio_table (`components.js`, mirrored in `skills.py`). The same
    component is used wherever its skill is called.
  - Claude: `tutor/ai.py` only *reads* free text into inputs (structured output, `claude-opus-5-5` at low effort).
    It never judges; the session does (`/say`, rate-limited). `tutor/evals/` holds its eval set and runner.
- **`tutor/web.py`** is the FastAPI app: `/api/problems`, `/api/sessions`, `/api/sessions/{id}/input|step|hint|where|done`,
  plus routes registered by `skills_web.py` and `ai_web.py`, and one page, `tutor/static/index.html`. Sessions are
  kept in memory. `tutor/log.py` writes one JSON line per statement to `$TUTOR_LOG` (default `v2/logs/`,
  git-ignored). On the server a dokku storage mount keeps `/app/v2/logs` (PATHS.md, Logging, has the copy command).
- **Tests:** `v2/tests/test_tutor.py` includes an "automatic student" that types every route of every example and
  word problem and expects the tutor to reach the right answer, and `test_boxes.py` checks that Type and Boxes hold
  the same routes after every step of all ~11.5k routes (about a minute). A data change that breaks a route shows up
  in both.

## Pull requests

Every change in a PR needs adversarial validation by an Opus sub-agent before the PR is opened, and again before
each later push to it. Use the Agent tool with `model: "opus"`, give it the PR's diff against `main`, and tell it to
try to break the change, not to confirm it. It should:

- run `cd v2 && python3 build.py --no-site` and `uv run pytest`, and check that the build leaves no uncommitted
  changes to the generated outputs (`git status`);
- look for inputs, examples, routes or word problems the change gets wrong, including cases the tests don't cover;
- check that the tutor and the diagrams still agree, and that the tutor still accepts every route.

Fix what it finds, or explain in the PR description why a finding doesn't apply, and repeat until it finds nothing.
Summarize what the validation checked and found in the PR description.
