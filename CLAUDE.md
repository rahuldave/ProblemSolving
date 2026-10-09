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
```

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
- **Tutor pipeline:** text → `tutor/parse.py` → typed pydantic steps (`tutor/models.py`; ambiguous notation returns
  every reading) → `tutor/classifier.py` (`RuleClassifier.classify(step, candidates)`; exact matches beat wildcards,
  and any object with this interface can replace it) → `tutor/session.py`. The session classifies the first one or
  two steps against the tree, then against the next step of each route still alive. Each route keeps its own
  position, so build-up steps and steps done in the head don't lose the other routes. Word-problem sessions start
  with the extraction decisions. A student who skips them is classified against the correct reading and against
  each trap's giveaway steps.
- **`tutor/web.py`** is a FastAPI JSON API (`/api/problems`, `/api/sessions`, `/api/sessions/{id}/input|hint|where|done`)
  plus one page, `tutor/static/index.html`. Sessions are kept in memory.
- **Tests:** `v2/tests/test_tutor.py` includes an "automatic student" that types every route of every example and
  word problem and expects the tutor to reach the right answer. A data change that breaks a route shows up there.
