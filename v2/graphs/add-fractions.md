# Add two fractions

`add-fractions` · core · prompt: *Find {a}/{b} + {c}/{d}.*

Uses: [common-multiple](common-multiple.md), [cross-products](cross-products.md), [missing-value](missing-value.md), [simplify-fraction](simplify-fraction.md), [to-decimal](to-decimal.md)

| Method | Idea | Steps use |
|---|---|---|
| **Common denominator** `common_denominator` | Rewrite both fractions over a common denominator, add the numerators, simplify. | common-multiple, missing-value, simplify-fraction |
| **Bow-tie (cross-multiply)** `bow_tie` | ({a}×{d} + {c}×{b}) / ({b}×{d}), then simplify. | cross-products, simplify-fraction |
| **Convert to decimals** `decimal` | Write each fraction as a decimal and add. | to-decimal |

Reading the graphs: **hexagons** group first steps by operation · scope; **blue** = first step, **purple** = second step (only where methods share a first step); **yellow** = method; **green dashed** = a call to another question (see its own page); edge labels show which skill method produced the step.

## Find 5/6 + 3/4.

[![Find 5/6 + 3/4.](../svg/add-fractions-1.svg)](../svg/add-fractions-1.svg)

<sub>Click the graph to open it full size · [mermaid source](../svg/add-fractions-1.mmd)</sub>

## Find 2/3 + 1/5.

[![Find 2/3 + 1/5.](../svg/add-fractions-2.svg)](../svg/add-fractions-2.svg)

<sub>Click the graph to open it full size · [mermaid source](../svg/add-fractions-2.mmd)</sub>
