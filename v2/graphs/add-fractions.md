# Add two fractions

`add-fractions` · core · prompt: *Find {a}/{b} + {c}/{d}.*

Its methods call: [common-multiple](common-multiple.md), [cross-products](cross-products.md), [missing-value](missing-value.md), [simplify-fraction](simplify-fraction.md), [to-decimal](to-decimal.md)

| Method | Idea | Best when | Calls |
|---|---|---|---|
| **Common denominator** `common_denominator` | Rewrite both fractions over a common denominator, add the numerators, simplify. | Always; use the least common multiple to keep numbers small. | [common-multiple](common-multiple.md), [missing-value](missing-value.md), [simplify-fraction](simplify-fraction.md) |
| **Bow-tie (cross-multiply)** `bow_tie` | ({a}×{d} + {c}×{b}) / ({b}×{d}), then simplify. | Quick, with small denominators. | [cross-products](cross-products.md), [simplify-fraction](simplify-fraction.md) |
| **Convert to decimals** `decimal` | Write each fraction as a decimal and add. | An approximate answer is enough. | [to-decimal](to-decimal.md) |

Each graph starts at the question and branches at **× Which first step?** into every first step a student might write. Methods that share a first step meet there and split at **× Which next step?**. Each route then follows its method to the answer. The legend at the bottom of each graph explains the shapes.

## Find 5/6 + 3/4.

[![Find 5/6 + 3/4.](../svg/add-fractions-1.svg)](../svg/add-fractions-1.svg)

<sub>Click the graph to open it full size · [mermaid source](../svg/add-fractions-1.mmd)</sub>

## Find 2/3 + 1/5.

[![Find 2/3 + 1/5.](../svg/add-fractions-2.svg)](../svg/add-fractions-2.svg)

<sub>Click the graph to open it full size · [mermaid source](../svg/add-fractions-2.mmd)</sub>
