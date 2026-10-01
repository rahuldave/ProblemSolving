# Find the missing value in a proportion

`missing-value` · core · prompt: *Solve {a}/{b} = x/{d}.*

Its methods call: [simplify-fraction](simplify-fraction.md), [to-decimal](to-decimal.md)

| Method | Idea | Best when | Calls |
|---|---|---|---|
| **Cross-multiply and divide** `cross_multiply` | {a} × {d} = {b} × x, so x = {a} × {d} ÷ {b}. | Always works; most useful when there's no whole-number scale factor. | — |
| **Scale factor** `scale_factor` | Find what turns {b} into {d}, then do the same to {a}. | {d} is a whole-number multiple of {b}. | — |
| **Unit rate** `unit_rate` | Find the value per 1, then scale up to {d}. | {a}/{b} is a friendly decimal. | [to-decimal](to-decimal.md) |
| **Inverse rate** `inverse_rate` | Find how many of the second quantity per 1 of the first, then divide. | {b}/{a} is a friendly number. | [to-decimal](to-decimal.md) |
| **Ratio table** `ratio_table` | Build {a}:{b} up by ×2, ×3, … until the second term reaches {d}. | {d} is a small whole-number multiple of {b}. | — |
| **Simplify, then scale** `simplify_then_scale` | Reduce {a}/{b} first so a whole-number scale factor appears. | {a}/{b} isn't in lowest terms. | [simplify-fraction](simplify-fraction.md) |

Each graph starts at the question and branches at **× Which first step?** into every first step a student might write. Methods that share a first step meet there and split at **× Which next step?**. Each route then follows its method to the answer. The legend at the bottom of each graph explains the shapes.

## Solve 3/5 = x/40.

[![Solve 3/5 = x/40.](../svg/missing-value-1.svg)](../svg/missing-value-1.svg)

<sub>Click the graph to open it full size · [mermaid source](../svg/missing-value-1.mmd)</sub>

## Solve 4/6 = x/15.

[![Solve 4/6 = x/15.](../svg/missing-value-2.svg)](../svg/missing-value-2.svg)

<sub>Click the graph to open it full size · [mermaid source](../svg/missing-value-2.mmd)</sub>

Not applicable here: Ratio table (`ratio_table`)
