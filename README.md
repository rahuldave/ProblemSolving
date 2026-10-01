# ProblemSolving

Solution methods for ratio, fraction, and percent questions, classified by the first step a student takes
(and the second step when methods share a first step). Meant as data for an app that recognizes a student's
method from their first step and gives method-specific help.

**Website: https://rahuldave.com/ProblemSolving/** (built from this repo into `docs/`).

**Or read [REPORT.md](REPORT.md):** the idea, the reuse structure, and a graph for every example question and word problem.

| Path | What it is |
|---|---|
| `v2/questions/*.json` | The data: skills, core questions, and applied questions (one file each) |
| `v2/vocabulary.json` | Schema: the step language (`say`, `use`, `all`, `choose`), reductions, classification levels, and the graph grammar |
| `v2/extraction.json` | Extraction concepts for word problems, and how a decision's options pick the question and its numbers |
| `v2/word-problems/*.json` | Word problems: quantities plus extraction decisions, each with one correct option and its traps |
| `v2/trees/word-problems.json` | Generated: each word problem's answer, each trap's wrong answer, and first steps that give a trap away |
| `v2/build.py` | Expands skills and reductions, checks every method on every example, generates the outputs below |
| `v2/trees/*.json` | Generated first-step trees for an app to match student steps against |
| `v2/graphs/*.md` | Generated pages, one per question, plus the word problems |
| `v2/svg/` | Generated graph images (`.svg`, each with its legend at the bottom) and their mermaid sources (`.mmd`) |
| `docs/` | Generated website (Quarto), served by GitHub Pages |
| `REPORT.md` | Generated single report combining everything |
| `v1/` | The first, hand-written version (one JSON file), kept for comparison |
| `v2/tutor/` | A prototype tutor that walks a student through a question or word problem step by step |
| `v2/tests/` | Tests for the tutor, including an automatic student that walks every method to the answer |

```sh
cd v2 && python3 build.py --demo   # validate, regenerate everything, run the classifier demo
cd v2 && python3 build.py --no-site   # skip the website
```

Requires Python 3.9+ (no packages). Graph images need the mermaid CLI (`mmdc`); the website needs
[Quarto](https://quarto.org). Without them the build still validates and writes the JSON and markdown.

## Tutor prototype

A terminal tutor that walks a student through a question or a word problem one step at a time, using the trees.

```sh
cd v2
uv run python -m tutor                       # pick from a list
uv run python -m tutor lemonade-more-sugar   # a word problem
uv run python -m tutor compare-fractions:1   # a question's first example
uv run python -m tutor --list
uv run pytest                                # from the repo root
```

The same sessions run as a web app (deployed at https://problemsolving.rahuldave.us):

```sh
cd v2 && uv run uvicorn tutor.web:app --reload   # then open http://127.0.0.1:8000
```

`tutor/web.py` is a small FastAPI JSON API (`/api/problems`, `/api/sessions`, `/api/sessions/{id}/input`,
`/api/sessions/{id}/hint|where|done`) plus one page (`tutor/static/index.html`). Sessions are kept in memory.
The `Dockerfile` builds it for Dokku (`git push dokku main`).

The student types one step at a time (`4 x 18 = 72`, `72 / 6 = 12`, `gcf(6, 8) = 2`, `21 > 20`, `3:4 ≠ 5:7`,
`plot (3, 4) (5, 7)`), or picks an option by number. `hint` (twice for more), `where`, `done`, `quit`.

How it works:

- **Typed input** (`tutor/models.py`): every entry becomes a pydantic model (an arithmetic, function, comparison,
  ratio-comparison or plot step, or a choice) before the tutor sees it. `tutor/parse.py` makes these from text, and
  returns every reading of ambiguous notation (`4/3 = 4/3`), so the session can use the one that fits.
- **Classifier** (`tutor/classifier.py`): input is concrete, a typed step plus the candidate next steps with their
  values; output is which candidates match, or that the step is on the way to a build-up step, and whether the
  student's arithmetic is right. `RuleClassifier` matches exactly (exact matches beat wildcards); anything with the
  same `classify(step, candidates)` interface, such as a trained model, can replace it.
- **Session** (`tutor/session.py`): the first step, and the second where methods share a first step, are classified
  against `trees/<question>.json`; after that, against the next step of each route still alive. Each route keeps its
  own position, so a build-up step (5 × 2 = 10 on the way to 5 × 8 = 40) or a step done in the head (15% → 0.15)
  doesn't lose other routes. Word problems start with the extraction decisions; a student who skips them and starts
  computing is classified against the correct reading and against each trap's giveaway first steps.
- The session reuses `build.py` to expand questions into routes, so the tutor and the diagrams always agree.
