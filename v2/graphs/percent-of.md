# Find a percent of a number

`percent-of` · applied · prompt: *What is {p}% of {n}?*

This is [missing-value](missing-value.md) in context, with `{"a": "p", "b": 100, "d": "n"}`. p% of n means p/100 = x/n.

| Method | Idea | Best when | Calls |
|---|---|---|---|
| **Convert to a decimal and multiply** `decimal` (= missing-value · unit_rate) | {p}% = {p} ÷ 100; multiply that by {n}. | {a}/{b} is a friendly decimal. | [to-decimal](to-decimal.md) |
| **Find 1% first** `one_percent` (= missing-value · scale_factor) | 1% of {n} is {n} ÷ 100; multiply by {p}. | {d} is a whole-number multiple of {b}. | — |
| **Multiply, then divide by 100** `multiply_first` (= missing-value · cross_multiply) | {p} × {n} ÷ 100. | Always works; most useful when there's no whole-number scale factor. | — |
| **Use a simplified fraction** `fraction` (= missing-value · simplify_then_scale) | {p}/100 simplifies (15/100 = 3/20); take that fraction of {n}. | {a}/{b} isn't in lowest terms. | [simplify-fraction](simplify-fraction.md) |
| **Ratio table** `ratio_table` (= missing-value · ratio_table) | Scale {p}:100 until the 100 becomes {n}. | {d} is a small whole-number multiple of {b}. | — |
| **Build from 10% and 5%** `benchmark_10_5` | 10% is easy (÷ 10) and 5% is half of that; add up the pieces. | The percent is a multiple of 5. | — |

Each graph starts at the question and branches at **× Which first step?** into every first step a student might write. Methods that share a first step meet there and split at **× Which next step?**. Each route then follows its method to the answer. The legend at the bottom of each graph explains the shapes.

## What is 15% of 80?

[![What is 15% of 80?](../svg/percent-of-1.svg)](../svg/percent-of-1.svg)

<sub>Click the graph to open it full size · [mermaid source](../svg/percent-of-1.mmd)</sub>

Not applicable here: Ratio table (`ratio_table`)

## What is 35% of 60?

[![What is 35% of 60?](../svg/percent-of-2.svg)](../svg/percent-of-2.svg)

<sub>Click the graph to open it full size · [mermaid source](../svg/percent-of-2.mmd)</sub>

Not applicable here: Ratio table (`ratio_table`)
