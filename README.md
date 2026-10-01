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

```sh
cd v2 && python3 build.py --demo   # validate, regenerate everything, run the classifier demo
cd v2 && python3 build.py --no-site   # skip the website
```

Requires Python 3.9+ (no packages). Graph images need the mermaid CLI (`mmdc`); the website needs
[Quarto](https://quarto.org). Without them the build still validates and writes the JSON and markdown.
