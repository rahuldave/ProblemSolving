# Find a percent of a number

`percent-of` · applied · prompt: *What is {p}% of {n}?*

Reduces to [missing-value](missing-value.md) with `{"a": "p", "b": 100, "d": "n"}`. p% of n means p/100 = x/n.

| Method | Idea | Steps use |
|---|---|---|
| **Convert to a decimal and multiply** `decimal` (= missing-value · unit_rate) | {p}% = {p} ÷ 100; multiply that by {n}. | — |
| **Find 1% first** `one_percent` (= missing-value · scale_factor) | 1% of {n} is {n} ÷ 100; multiply by {p}. | — |
| **Multiply, then divide by 100** `multiply_first` (= missing-value · cross_multiply) | {p} × {n} ÷ 100. | — |
| **Use a simplified fraction** `fraction` (= missing-value · simplify_then_scale) | {p}/100 simplifies (15/100 = 3/20); take that fraction of {n}. | — |
| **Ratio table** `ratio_table` (= missing-value · ratio_table) | Scale {p}:100 until the 100 becomes {n}. | — |
| **Build from 10% and 5%** `benchmark_10_5` | 10% is easy (÷ 10) and 5% is half of that; add up the pieces. | — |

Reading the graphs: **hexagons** group first steps by operation · scope; **blue** = first step, **purple** = second step (only where methods share a first step); **yellow** = method; **green dashed** = a call to another question (see its own page); edge labels show which skill method produced the step.

## What is 15% of 80?

[![What is 15% of 80?](../svg/percent-of-1.svg)](../svg/percent-of-1.svg)

<sub>Click the graph to open it full size · [mermaid source](../svg/percent-of-1.mmd)</sub>

Not applicable here: Ratio table (`ratio_table`)

## What is 35% of 60?

[![What is 35% of 60?](../svg/percent-of-2.svg)](../svg/percent-of-2.svg)

<sub>Click the graph to open it full size · [mermaid source](../svg/percent-of-2.mmd)</sub>

Not applicable here: Ratio table (`ratio_table`)
