# ProblemSolving

Solution methods for ratio, fraction, and percent questions, classified by the first step a student takes
(and the second step when methods share a first step). Meant as data for an app that recognizes a student's
method from their first step and gives method-specific help.

**Start with [REPORT.md](REPORT.md):** the idea, the reuse structure, and a graph for every example question.

| Path | What it is |
|---|---|
| `v2/questions/*.json` | The data: skills, core questions, and applied questions (one file each) |
| `v2/vocabulary.json` | Schema: step types, skill calls (`use`), reductions, classification levels |
| `v2/build.py` | Expands skills and reductions, checks every method on every example, generates the outputs below |
| `v2/trees/*.json` | Generated first-step trees for an app to match student steps against |
| `v2/graphs/*.md` | Generated mermaid graphs, one page per question |
| `REPORT.md` | Generated single report combining everything |
| `v1/` | The first, hand-written version (one JSON file), kept for comparison |

```sh
cd v2 && python3 build.py --demo   # validate, regenerate, run the classifier demo
```

Requires Python 3.9+; no dependencies.
