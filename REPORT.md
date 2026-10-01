# Solving arithmetic problems: methods classified by first step

Most arithmetic questions can be solved in several ways. This report catalogs the methods for a family of
ratio, fraction, and percent questions and classifies each method by **the first step a student takes**,
using the second step only when methods share a first step. The goal is an app that recognizes a student's
method from what they write first and responds with help for *that* method.

## How the data is organized

- **Skills** are small questions that other methods call as steps: simplify a fraction, write it as a decimal,
  find a common multiple, cross products. Each has its own methods (a common multiple can be recalled, found by
  listing multiples, by multiplying, or from the GCF).
- **Core questions** (compare fractions, missing value, add fractions) have methods built from primitive steps
  and skill calls.
- **Applied questions** are core questions in context: a proportion check *is* comparing fractions for equality,
  a better buy *is* comparing price ÷ quantity, and a percent of a number *is* a missing value with denominator 100.

The first-step trees are not written by hand: `v2/build.py` expands every skill call into every combination of
skill methods, runs each variant on the examples to check the answer, and groups variants by their first step,
then by their second where needed. The hand-written version this replaced is in `v1/` for comparison.

## What expanding the skills revealed

Shared first steps that the hand-written v1 tree missed, because they only appear once skills are expanded:

- In *compare fractions*, `3 × 7` starts both **cross-multiply** and **rewrite one fraction over the other's
  denominator** (through missing value's cross-multiply). The next step decides: `5 × 4` vs `21 ÷ 4`.
- In *proportion check*, `6 ÷ 8` starts both **decimal** and **rewrite over the other's denominator**,
  and `GCF(6, 8)` starts both **simplify** and the same rewrite.
- `3 × 5 = 15` can come from **listing multiples** or from **multiplying**; the graphs show it as one node
  linked from both classes.

Known limit: the generated trees store a student-chosen multiplier as a wildcard, so a typed classifier sees
`4 × 25` as matching three methods. The per-example graphs tell those apart by value.

## Reading the graphs

Each example graph reads left to right: question → **hexagons** grouping first steps by operation · scope →
**blue** first step → **purple** second step (only where methods share a first step) → **yellow** method →
the method's steps, where a **green dashed** box is a call to another question (it has its own section) →
answer. Edge labels name the skill method that produced the step.

## How the questions reuse each other

```mermaid
flowchart LR
  add_fractions["Add two fractions"]
  better_buy["Which is the better buy?"]
  common_multiple["Find a common multiple"]
  compare_fractions["Compare two fractions"]
  cross_products["Cross products"]
  missing_value["Find the missing value in a proportion"]
  percent_of["Find a percent of a number"]
  proportion_check["Are two ratios proportional?"]
  simplify_fraction["Simplify a fraction"]
  to_decimal["Write a fraction as a decimal"]
  add_fractions --> common_multiple
  add_fractions --> cross_products
  add_fractions --> missing_value
  add_fractions --> simplify_fraction
  add_fractions --> to_decimal
  better_buy -.->|is a| compare_fractions
  compare_fractions --> common_multiple
  compare_fractions --> cross_products
  compare_fractions --> missing_value
  compare_fractions --> simplify_fraction
  compare_fractions --> to_decimal
  missing_value --> simplify_fraction
  missing_value --> to_decimal
  percent_of -.->|is a| missing_value
  proportion_check -.->|is a| compare_fractions
  classDef skill fill:#e3f4e6,stroke:#3f9a55,color:#222
  classDef core fill:#fff1cc,stroke:#c99a1a,color:#222
  classDef applied fill:#e3edfd,stroke:#5b7fd1,color:#222
  class common_multiple,cross_products,simplify_fraction,to_decimal skill
  class add_fractions,compare_fractions,missing_value core
  class better_buy,percent_of,proportion_check applied
```

| Question | Kind | Methods | Uses |
|---|---|---|---|
| [Add two fractions](#add-fractions) | core | 3 | [common-multiple](#common-multiple), [cross-products](#cross-products), [missing-value](#missing-value), [simplify-fraction](#simplify-fraction), [to-decimal](#to-decimal) |
| [Compare two fractions](#compare-fractions) | core | 11 | [common-multiple](#common-multiple), [compare-fractions](#compare-fractions), [cross-products](#cross-products), [missing-value](#missing-value), [simplify-fraction](#simplify-fraction), [to-decimal](#to-decimal) |
| [Find the missing value in a proportion](#missing-value) | core | 6 | [simplify-fraction](#simplify-fraction), [to-decimal](#to-decimal) |
| [Which is the better buy?](#better-buy) | applied | 6 | [compare-fractions](#compare-fractions) |
| [Find a percent of a number](#percent-of) | applied | 6 | [missing-value](#missing-value) |
| [Are two ratios proportional?](#proportion-check) | applied | 11 | [compare-fractions](#compare-fractions) |
| [Find a common multiple](#common-multiple) | skill | 4 | — |
| [Cross products](#cross-products) | skill | 1 | — |
| [Simplify a fraction](#simplify-fraction) | skill | 2 | — |
| [Write a fraction as a decimal](#to-decimal) | skill | 2 | — |

## Contents

- [Add two fractions](#add-fractions) (core)
- [Compare two fractions](#compare-fractions) (core)
- [Find the missing value in a proportion](#missing-value) (core)
- [Which is the better buy?](#better-buy) (applied)
- [Find a percent of a number](#percent-of) (applied)
- [Are two ratios proportional?](#proportion-check) (applied)
- [Find a common multiple](#common-multiple) (skill)
- [Cross products](#cross-products) (skill)
- [Simplify a fraction](#simplify-fraction) (skill)
- [Write a fraction as a decimal](#to-decimal) (skill)
- [Word problems](#word-problems): extraction concepts and 12 stories

<a name="add-fractions"></a>

## Add two fractions

`add-fractions` · core · prompt: *Find {a}/{b} + {c}/{d}.*

Uses: [common-multiple](#common-multiple), [cross-products](#cross-products), [missing-value](#missing-value), [simplify-fraction](#simplify-fraction), [to-decimal](#to-decimal)

| Method | Idea | Steps use |
|---|---|---|
| **Common denominator** `common_denominator` | Rewrite both fractions over a common denominator, add the numerators, simplify. | common-multiple, missing-value, simplify-fraction |
| **Bow-tie (cross-multiply)** `bow_tie` | ({a}×{d} + {c}×{b}) / ({b}×{d}), then simplify. | cross-products, simplify-fraction |
| **Convert to decimals** `decimal` | Write each fraction as a decimal and add. | to-decimal |

Reading the graphs: **hexagons** group first steps by operation · scope; **blue** = first step, **purple** = second step (only where methods share a first step); **yellow** = method; **green dashed** = a call to another question (see its own page); edge labels show which skill method produced the step.

### Find 5/6 + 3/4.

```mermaid
flowchart LR
  n0(["Find 5/6 + 3/4."])
  n1(["Answer: 19/12"])
  n2["Common denominator"]
  n3["Find a common multiple of 6 and 4 → 12"]
  n2 --> n3
  n4["Solve 5/6 = x/12 → 10"]
  n3 --> n4
  n5["Solve 3/4 = x/12 → 9"]
  n4 --> n5
  n6["10 + 9 = 19"]
  n5 --> n6
  n7["Simplify 19/12 → 19/12"]
  n6 --> n7
  n7 --> n1
  n8["Bow-tie (cross-multiply)"]
  n9["Find the cross products of 5/6 and 3/4 → 20/18"]
  n8 --> n9
  n10["6 × 4 = 24"]
  n9 --> n10
  n11["20 + 18 = 38"]
  n10 --> n11
  n12["Simplify 38/24 → 19/12"]
  n11 --> n12
  n12 --> n1
  n13["Convert to decimals"]
  n14["Write 5/6 as a decimal → ≈ 0.833"]
  n13 --> n14
  n15["Write 3/4 as a decimal → 0.75"]
  n14 --> n15
  n16["5/6 + 0.75 = 19/12"]
  n15 --> n16
  n16 --> n1
  n17["5 ÷ 6 ≈ 0.833"]
  n18{{"divide · within"}}
  n0 --> n18
  n18 --> n17
  n17 -->|"to-decimal/divide"| n13
  n19["GCF(6, 4) = 2"]
  n20{{"factor · across"}}
  n0 --> n20
  n20 --> n19
  n19 -->|"common-multiple/gcf_formula"| n2
  n21["5 × 4 = 20"]
  n22{{"multiply · across"}}
  n0 --> n22
  n22 --> n21
  n21 -->|"cross-products/diagonals"| n8
  n23["6 × 4 = 24"]
  n22 --> n23
  n23 -->|"common-multiple/product"| n2
  n24["LCM(6, 4) = 12"]
  n22 --> n24
  n24 -->|"common-multiple/recall"| n2
  n25["6 × 2 = 12"]
  n26{{"multiply · within"}}
  n0 --> n26
  n26 --> n25
  n25 -->|"common-multiple/list_multiples"| n2
  classDef cls fill:#eef0f6,stroke:#8a90a6,color:#222
  classDef first fill:#e3edfd,stroke:#5b7fd1,color:#222
  classDef second fill:#efe6fb,stroke:#8b63c9,color:#222
  classDef method fill:#fff1cc,stroke:#c99a1a,color:#222,font-weight:bold
  classDef skill fill:#e3f4e6,stroke:#3f9a55,stroke-dasharray:5 3,color:#222
  classDef step fill:#ffffff,stroke:#999,color:#222
  classDef ans fill:#fde4e1,stroke:#c4554a,color:#222
  class n18,n20,n22,n26 cls
  class n17,n19,n21,n23,n24,n25 first
  class n2,n8,n13 method
  class n3,n4,n5,n7,n9,n12,n14,n15 skill
  class n6,n10,n11,n16 step
  class n0,n1 ans
```

### Find 2/3 + 1/5.

```mermaid
flowchart LR
  n0(["Find 2/3 + 1/5."])
  n1(["Answer: 13/15"])
  n2["Common denominator"]
  n3["Find a common multiple of 3 and 5 → 15"]
  n2 --> n3
  n4["Solve 2/3 = x/15 → 10"]
  n3 --> n4
  n5["Solve 1/5 = x/15 → 3"]
  n4 --> n5
  n6["10 + 3 = 13"]
  n5 --> n6
  n7["Simplify 13/15 → 13/15"]
  n6 --> n7
  n7 --> n1
  n8["Bow-tie (cross-multiply)"]
  n9["Find the cross products of 2/3 and 1/5 → 10/3"]
  n8 --> n9
  n10["3 × 5 = 15"]
  n9 --> n10
  n11["10 + 3 = 13"]
  n10 --> n11
  n12["Simplify 13/15 → 13/15"]
  n11 --> n12
  n12 --> n1
  n13["Convert to decimals"]
  n14["Write 2/3 as a decimal → ≈ 0.667"]
  n13 --> n14
  n15["Write 1/5 as a decimal → 0.2"]
  n14 --> n15
  n16["2/3 + 0.2 = 13/15"]
  n15 --> n16
  n16 --> n1
  n17["2 ÷ 3 ≈ 0.667"]
  n18{{"divide · within"}}
  n0 --> n18
  n18 --> n17
  n17 -->|"to-decimal/divide"| n13
  n19["GCF(3, 5) = 1"]
  n20{{"factor · across"}}
  n0 --> n20
  n20 --> n19
  n19 -->|"common-multiple/gcf_formula"| n2
  n21["2 × 5 = 10"]
  n22{{"multiply · across"}}
  n0 --> n22
  n22 --> n21
  n21 -->|"cross-products/diagonals"| n8
  n23["LCM(3, 5) = 15"]
  n22 --> n23
  n23 -->|"common-multiple/recall"| n2
  n24["3 × 5 = 15"]
  n22 --> n24
  n25{{"multiply · within"}}
  n0 --> n25
  n25 --> n24
  n24 -->|"common-multiple/list_multiples / common-multiple/product"| n2
  classDef cls fill:#eef0f6,stroke:#8a90a6,color:#222
  classDef first fill:#e3edfd,stroke:#5b7fd1,color:#222
  classDef second fill:#efe6fb,stroke:#8b63c9,color:#222
  classDef method fill:#fff1cc,stroke:#c99a1a,color:#222,font-weight:bold
  classDef skill fill:#e3f4e6,stroke:#3f9a55,stroke-dasharray:5 3,color:#222
  classDef step fill:#ffffff,stroke:#999,color:#222
  classDef ans fill:#fde4e1,stroke:#c4554a,color:#222
  class n18,n20,n22,n25 cls
  class n17,n19,n21,n23,n24 first
  class n2,n8,n13 method
  class n3,n4,n5,n7,n9,n12,n14,n15 skill
  class n6,n10,n11,n16 step
  class n0,n1 ans
```


<a name="compare-fractions"></a>

## Compare two fractions

`compare-fractions` · core · prompt: *Which is larger: {a}/{b} or {c}/{d}? (Or are they equal?)*

Uses: [common-multiple](#common-multiple), [compare-fractions](#compare-fractions), [cross-products](#cross-products), [missing-value](#missing-value), [simplify-fraction](#simplify-fraction), [to-decimal](#to-decimal)

| Method | Idea | Steps use |
|---|---|---|
| **Cross-multiply** `cross_multiply` | {a}/{b} > {c}/{d} exactly when {a}×{d} > {c}×{b}. | cross-products |
| **Common denominator** `common_denominator` | Rewrite both fractions over the same denominator, then compare numerators. | common-multiple, missing-value |
| **Rewrite one fraction over the other's denominator** `match_denominator` | Turn {a}/{b} into something over {d}, then compare numerators with {c}. | missing-value |
| **Common numerator** `common_numerator` | With equal numerators, the smaller denominator gives the bigger fraction. | common-multiple, missing-value |
| **Convert to decimals** `decimal` | Write each fraction as a decimal and compare. | to-decimal |
| **Compare unit rates (flipped fractions)** `unit_rate` | How much bottom per 1 of top? The bigger rate belongs to the smaller fraction. | to-decimal |
| **Compare scale factors** `scale_factor` | How much do the tops grow ({c} ÷ {a}) compared with the bottoms ({d} ÷ {b})? | — |
| **Ratio table** `ratio_table` | Scale {a}:{b} by 2, 3, 4, … until the top reaches {c}, then compare bottoms. | — |
| **Graph the points** `graph` | Plot ({a}, {b}) and ({c}, {d}); the steeper line from the origin belongs to the smaller fraction. | — |
| **Simplify both** `simplify` | Reduce both fractions to lowest terms; equal fractions reduce to the same thing. | simplify-fraction |
| **Distance from 1** `distance_from_one` | Find how far each fraction is from 1; the one closer to 1 is bigger. | compare-fractions |

Reading the graphs: **hexagons** group first steps by operation · scope; **blue** = first step, **purple** = second step (only where methods share a first step); **yellow** = method; **green dashed** = a call to another question (see its own page); edge labels show which skill method produced the step.

### Which is larger: 3/4 or 5/7? (Or are they equal?)

```mermaid
flowchart LR
  n0(["Which is larger: 3/4 or 5/7? (Or are they equal?)"])
  n1(["Answer: first"])
  n2["Cross-multiply"]
  n3["Find the cross products of 3/4 and 5/7 → 21/20"]
  n2 --> n3
  n4["21 #gt; 20"]
  n3 --> n4
  n4 --> n1
  n5["Common denominator"]
  n6["Find a common multiple of 4 and 7 → 28"]
  n5 --> n6
  n7["Solve 3/4 = x/28 → 21"]
  n6 --> n7
  n8["Solve 5/7 = x/28 → 20"]
  n7 --> n8
  n9["21 #gt; 20"]
  n8 --> n9
  n9 --> n1
  n10["Rewrite one fraction over the other's denominator"]
  n11["Solve 3/4 = x/7 → 5.25"]
  n10 --> n11
  n12["5.25 #gt; 5"]
  n11 --> n12
  n12 --> n1
  n13["Common numerator"]
  n14["Find a common multiple of 3 and 5 → 15"]
  n13 --> n14
  n15["Solve 4/3 = x/15 → 20"]
  n14 --> n15
  n16["Solve 7/5 = x/15 → 21"]
  n15 --> n16
  n17["20 #lt; 21"]
  n16 --> n17
  n17 --> n1
  n18["Convert to decimals"]
  n19["Write 3/4 as a decimal → 0.75"]
  n18 --> n19
  n20["Write 5/7 as a decimal → ≈ 0.714"]
  n19 --> n20
  n21["0.75 #gt; 5/7"]
  n20 --> n21
  n21 --> n1
  n22["Compare unit rates (flipped fractions)"]
  n23["Write 4/3 as a decimal → ≈ 1.333"]
  n22 --> n23
  n24["Write 7/5 as a decimal → 1.4"]
  n23 --> n24
  n25["4/3 #lt; 1.4"]
  n24 --> n25
  n25 --> n1
  n26["Compare scale factors"]
  n27["5 ÷ 3 ≈ 1.667"]
  n26 --> n27
  n28["7 ÷ 4 = 1.75"]
  n27 --> n28
  n29["5/3 #lt; 1.75"]
  n28 --> n29
  n29 --> n1
  n30["Graph the points"]
  n31["plot (3, 4), (5, 7)"]
  n30 --> n31
  n32["4 ÷ 3 ≈ 1.333"]
  n31 --> n32
  n33["7 ÷ 5 = 1.4"]
  n32 --> n33
  n34["4/3 #lt; 1.4"]
  n33 --> n34
  n34 --> n1
  n35["Simplify both"]
  n36["Simplify 3/4 → 3/4"]
  n35 --> n36
  n37["Simplify 5/7 → 5/7"]
  n36 --> n37
  n38["3:4 ≠ 5:7"]
  n37 --> n38
  n38 --> n1
  n39["Distance from 1"]
  n40["4 − 3 = 1"]
  n39 --> n40
  n41["7 − 5 = 2"]
  n40 --> n41
  n42["Which is larger: 1/4 or 2/7? (Or are they equal?) → second"]
  n41 --> n42
  n42 --> n1
  n43["5 ÷ 3 ≈ 1.667"]
  n44{{"divide · across"}}
  n0 --> n44
  n44 --> n43
  n43 --> n26
  n45["7 ÷ 4 = 1.75"]
  n44 --> n45
  n45 -->|"missing-value/scale_factor"| n10
  n46["3 ÷ 4 = 0.75"]
  n47{{"divide · within"}}
  n0 --> n47
  n47 --> n46
  n48["then 0.75 × 7 = 5.25"]
  n46 --> n48
  n48 -->|"missing-value/unit_rate"| n10
  n49["then 5 ÷ 7 ≈ 0.714"]
  n46 --> n49
  n49 -->|"to-decimal/divide"| n18
  n50["4 ÷ 3 ≈ 1.333"]
  n47 --> n50
  n51["then 7 ÷ 4/3 = 5.25"]
  n50 --> n51
  n51 -->|"missing-value/inverse_rate"| n10
  n52["then 7 ÷ 5 = 1.4"]
  n50 --> n52
  n52 -->|"to-decimal/divide"| n22
  n53["then 5 × 2 = 10"]
  n50 --> n53
  n53 -->|"to-decimal/power_of_ten"| n22
  n54["GCF(3, 5) = 1"]
  n55{{"factor · across"}}
  n0 --> n55
  n55 --> n54
  n54 -->|"common-multiple/gcf_formula"| n13
  n56["GCF(4, 7) = 1"]
  n55 --> n56
  n56 -->|"common-multiple/gcf_formula"| n5
  n57["GCF(3, 4) = 1"]
  n58{{"factor · within"}}
  n0 --> n58
  n58 --> n57
  n59["then 3 ÷ 1 = 3"]
  n57 --> n59
  n59 -->|"simplify-fraction/gcf"| n10
  n59 -->|"simplify-fraction/gcf"| n35
  n60["3 × 7 = 21"]
  n61{{"multiply · across"}}
  n0 --> n61
  n61 --> n60
  n62["then 5 × 4 = 20"]
  n60 --> n62
  n62 -->|"cross-products/diagonals"| n2
  n63["then 21 ÷ 4 = 5.25"]
  n60 --> n63
  n63 -->|"missing-value/cross_multiply"| n10
  n64["LCM(3, 5) = 15"]
  n61 --> n64
  n64 -->|"common-multiple/recall"| n13
  n65["LCM(4, 7) = 28"]
  n61 --> n65
  n65 -->|"common-multiple/recall"| n5
  n66["3 × 5 = 15"]
  n61 --> n66
  n67{{"multiply · within"}}
  n0 --> n67
  n67 --> n66
  n66 -->|"common-multiple/list_multiples / common-multiple/product"| n13
  n68["4 × 7 = 28"]
  n61 --> n68
  n67 --> n68
  n68 -->|"common-multiple/list_multiples / common-multiple/product"| n5
  n69["4 × 25 = 100"]
  n67 --> n69
  n70["then 3 × 25 = 75"]
  n69 --> n70
  n70 -->|"to-decimal/power_of_ten"| n18
  n70 -->|"to-decimal/power_of_ten"| n10
  n71["plot (3, 4), (5, 7)"]
  n72{{"represent · across"}}
  n0 --> n72
  n72 --> n71
  n71 --> n30
  n73["4 − 3 = 1"]
  n74{{"subtract · within"}}
  n0 --> n74
  n74 --> n73
  n73 --> n39
  classDef cls fill:#eef0f6,stroke:#8a90a6,color:#222
  classDef first fill:#e3edfd,stroke:#5b7fd1,color:#222
  classDef second fill:#efe6fb,stroke:#8b63c9,color:#222
  classDef method fill:#fff1cc,stroke:#c99a1a,color:#222,font-weight:bold
  classDef skill fill:#e3f4e6,stroke:#3f9a55,stroke-dasharray:5 3,color:#222
  classDef step fill:#ffffff,stroke:#999,color:#222
  classDef ans fill:#fde4e1,stroke:#c4554a,color:#222
  class n44,n47,n55,n58,n61,n67,n72,n74 cls
  class n43,n45,n46,n50,n54,n56,n57,n60,n64,n65,n66,n68,n69,n71,n73 first
  class n48,n49,n51,n52,n53,n59,n62,n63,n70 second
  class n2,n5,n10,n13,n18,n22,n26,n30,n35,n39 method
  class n3,n6,n7,n8,n11,n14,n15,n16,n19,n20,n23,n24,n36,n37,n42 skill
  class n4,n9,n12,n17,n21,n25,n27,n28,n29,n31,n32,n33,n34,n38,n40,n41 step
  class n0,n1 ans
```

Not applicable here: Ratio table (`ratio_table`)

### Which is larger: 3/8 or 2/5? (Or are they equal?)

```mermaid
flowchart LR
  n0(["Which is larger: 3/8 or 2/5? (Or are they equal?)"])
  n1(["Answer: second"])
  n2["Cross-multiply"]
  n3["Find the cross products of 3/8 and 2/5 → 15/16"]
  n2 --> n3
  n4["15 #lt; 16"]
  n3 --> n4
  n4 --> n1
  n5["Common denominator"]
  n6["Find a common multiple of 8 and 5 → 40"]
  n5 --> n6
  n7["Solve 3/8 = x/40 → 15"]
  n6 --> n7
  n8["Solve 2/5 = x/40 → 16"]
  n7 --> n8
  n9["15 #lt; 16"]
  n8 --> n9
  n9 --> n1
  n10["Rewrite one fraction over the other's denominator"]
  n11["Solve 3/8 = x/5 → 1.875"]
  n10 --> n11
  n12["1.875 #lt; 2"]
  n11 --> n12
  n12 --> n1
  n13["Common numerator"]
  n14["Find a common multiple of 3 and 2 → 6"]
  n13 --> n14
  n15["Solve 8/3 = x/6 → 16"]
  n14 --> n15
  n16["Solve 5/2 = x/6 → 15"]
  n15 --> n16
  n17["16 #gt; 15"]
  n16 --> n17
  n17 --> n1
  n18["Convert to decimals"]
  n19["Write 3/8 as a decimal → 0.375"]
  n18 --> n19
  n20["Write 2/5 as a decimal → 0.4"]
  n19 --> n20
  n21["0.375 #lt; 0.4"]
  n20 --> n21
  n21 --> n1
  n22["Compare unit rates (flipped fractions)"]
  n23["Write 8/3 as a decimal → ≈ 2.667"]
  n22 --> n23
  n24["Write 5/2 as a decimal → 2.5"]
  n23 --> n24
  n25["8/3 #gt; 2.5"]
  n24 --> n25
  n25 --> n1
  n26["Compare scale factors"]
  n27["2 ÷ 3 ≈ 0.667"]
  n26 --> n27
  n28["5 ÷ 8 = 0.625"]
  n27 --> n28
  n29["2/3 #gt; 0.625"]
  n28 --> n29
  n29 --> n1
  n30["Graph the points"]
  n31["plot (3, 8), (2, 5)"]
  n30 --> n31
  n32["8 ÷ 3 ≈ 2.667"]
  n31 --> n32
  n33["5 ÷ 2 = 2.5"]
  n32 --> n33
  n34["8/3 #gt; 2.5"]
  n33 --> n34
  n34 --> n1
  n35["Simplify both"]
  n36["Simplify 3/8 → 3/8"]
  n35 --> n36
  n37["Simplify 2/5 → 2/5"]
  n36 --> n37
  n38["3:8 ≠ 2:5"]
  n37 --> n38
  n38 --> n1
  n39["Distance from 1"]
  n40["8 − 3 = 5"]
  n39 --> n40
  n41["5 − 2 = 3"]
  n40 --> n41
  n42["Which is larger: 5/8 or 3/5? (Or are they equal?) → first"]
  n41 --> n42
  n42 --> n1
  n43["2 ÷ 3 ≈ 0.667"]
  n44{{"divide · across"}}
  n0 --> n44
  n44 --> n43
  n43 --> n26
  n45["5 ÷ 8 = 0.625"]
  n44 --> n45
  n45 -->|"missing-value/scale_factor"| n10
  n46["3 ÷ 8 = 0.375"]
  n47{{"divide · within"}}
  n0 --> n47
  n47 --> n46
  n48["then 0.375 × 5 = 1.875"]
  n46 --> n48
  n48 -->|"missing-value/unit_rate"| n10
  n49["then 2 ÷ 5 = 0.4"]
  n46 --> n49
  n49 -->|"to-decimal/divide"| n18
  n50["then 5 × 2 = 10"]
  n46 --> n50
  n50 -->|"to-decimal/power_of_ten"| n18
  n51["8 ÷ 3 ≈ 2.667"]
  n47 --> n51
  n52["then 5 ÷ 8/3 = 1.875"]
  n51 --> n52
  n52 -->|"missing-value/inverse_rate"| n10
  n53["then 5 ÷ 2 = 2.5"]
  n51 --> n53
  n53 -->|"to-decimal/divide"| n22
  n54["then 2 × 5 = 10"]
  n51 --> n54
  n54 -->|"to-decimal/power_of_ten"| n22
  n55["GCF(3, 2) = 1"]
  n56{{"factor · across"}}
  n0 --> n56
  n56 --> n55
  n55 -->|"common-multiple/gcf_formula"| n13
  n57["GCF(8, 5) = 1"]
  n56 --> n57
  n57 -->|"common-multiple/gcf_formula"| n5
  n58["GCF(3, 8) = 1"]
  n59{{"factor · within"}}
  n0 --> n59
  n59 --> n58
  n60["then 3 ÷ 1 = 3"]
  n58 --> n60
  n60 -->|"simplify-fraction/gcf"| n10
  n60 -->|"simplify-fraction/gcf"| n35
  n61["3 × 5 = 15"]
  n62{{"multiply · across"}}
  n0 --> n62
  n62 --> n61
  n63["then 2 × 8 = 16"]
  n61 --> n63
  n63 -->|"cross-products/diagonals"| n2
  n64["then 15 ÷ 8 = 1.875"]
  n61 --> n64
  n64 -->|"missing-value/cross_multiply"| n10
  n65["LCM(3, 2) = 6"]
  n62 --> n65
  n65 -->|"common-multiple/recall"| n13
  n66["LCM(8, 5) = 40"]
  n62 --> n66
  n66 -->|"common-multiple/recall"| n5
  n67["3 × 2 = 6"]
  n62 --> n67
  n68{{"multiply · within"}}
  n0 --> n68
  n68 --> n67
  n67 -->|"common-multiple/list_multiples / common-multiple/product"| n13
  n69["8 × 5 = 40"]
  n62 --> n69
  n68 --> n69
  n69 -->|"common-multiple/list_multiples / common-multiple/product"| n5
  n70["8 × 125 = 1000"]
  n68 --> n70
  n71["then 3 × 125 = 375"]
  n70 --> n71
  n71 -->|"to-decimal/power_of_ten"| n18
  n71 -->|"to-decimal/power_of_ten"| n10
  n72["plot (3, 8), (2, 5)"]
  n73{{"represent · across"}}
  n0 --> n73
  n73 --> n72
  n72 --> n30
  n74["8 − 3 = 5"]
  n75{{"subtract · within"}}
  n0 --> n75
  n75 --> n74
  n74 --> n39
  classDef cls fill:#eef0f6,stroke:#8a90a6,color:#222
  classDef first fill:#e3edfd,stroke:#5b7fd1,color:#222
  classDef second fill:#efe6fb,stroke:#8b63c9,color:#222
  classDef method fill:#fff1cc,stroke:#c99a1a,color:#222,font-weight:bold
  classDef skill fill:#e3f4e6,stroke:#3f9a55,stroke-dasharray:5 3,color:#222
  classDef step fill:#ffffff,stroke:#999,color:#222
  classDef ans fill:#fde4e1,stroke:#c4554a,color:#222
  class n44,n47,n56,n59,n62,n68,n73,n75 cls
  class n43,n45,n46,n51,n55,n57,n58,n61,n65,n66,n67,n69,n70,n72,n74 first
  class n48,n49,n50,n52,n53,n54,n60,n63,n64,n71 second
  class n2,n5,n10,n13,n18,n22,n26,n30,n35,n39 method
  class n3,n6,n7,n8,n11,n14,n15,n16,n19,n20,n23,n24,n36,n37,n42 skill
  class n4,n9,n12,n17,n21,n25,n27,n28,n29,n31,n32,n33,n34,n38,n40,n41 step
  class n0,n1 ans
```

Not applicable here: Ratio table (`ratio_table`)


<a name="missing-value"></a>

## Find the missing value in a proportion

`missing-value` · core · prompt: *Solve {a}/{b} = x/{d}.*

Uses: [simplify-fraction](#simplify-fraction), [to-decimal](#to-decimal)

| Method | Idea | Steps use |
|---|---|---|
| **Cross-multiply and divide** `cross_multiply` | {a} × {d} = {b} × x, so x = {a} × {d} ÷ {b}. | — |
| **Scale factor** `scale_factor` | Find what turns {b} into {d}, then do the same to {a}. | — |
| **Unit rate** `unit_rate` | Find the value per 1, then scale up to {d}. | to-decimal |
| **Inverse rate** `inverse_rate` | Find how many of the second quantity per 1 of the first, then divide. | to-decimal |
| **Ratio table** `ratio_table` | Build {a}:{b} up by ×2, ×3, … until the second term reaches {d}. | — |
| **Simplify, then scale** `simplify_then_scale` | Reduce {a}/{b} first so a whole-number scale factor appears. | simplify-fraction |

Reading the graphs: **hexagons** group first steps by operation · scope; **blue** = first step, **purple** = second step (only where methods share a first step); **yellow** = method; **green dashed** = a call to another question (see its own page); edge labels show which skill method produced the step.

### Solve 3/5 = x/40.

```mermaid
flowchart LR
  n0(["Solve 3/5 = x/40."])
  n1(["Answer: 24"])
  n2["Cross-multiply and divide"]
  n3["3 × 40 = 120"]
  n2 --> n3
  n4["120 ÷ 5 = 24"]
  n3 --> n4
  n4 --> n1
  n5["Scale factor"]
  n6["40 ÷ 5 = 8"]
  n5 --> n6
  n7["3 × 8 = 24"]
  n6 --> n7
  n7 --> n1
  n8["Unit rate"]
  n9["Write 3/5 as a decimal → 0.6"]
  n8 --> n9
  n10["0.6 × 40 = 24"]
  n9 --> n10
  n10 --> n1
  n11["Inverse rate"]
  n12["Write 5/3 as a decimal → ≈ 1.667"]
  n11 --> n12
  n13["40 ÷ 5/3 = 24"]
  n12 --> n13
  n13 --> n1
  n14["Ratio table"]
  n15["5 × 8 = 40"]
  n14 --> n15
  n16["3 × 8 = 24"]
  n15 --> n16
  n16 --> n1
  n17["Simplify, then scale"]
  n18["Simplify 3/5 → 3/5"]
  n17 --> n18
  n19["40 ÷ 5 = 8"]
  n18 --> n19
  n20["3 × 8 = 24"]
  n19 --> n20
  n20 --> n1
  n21["40 ÷ 5 = 8"]
  n22{{"divide · across"}}
  n0 --> n22
  n22 --> n21
  n21 --> n5
  n23["3 ÷ 5 = 0.6"]
  n24{{"divide · within"}}
  n0 --> n24
  n24 --> n23
  n23 -->|"to-decimal/divide"| n8
  n25["5 ÷ 3 ≈ 1.667"]
  n24 --> n25
  n25 -->|"to-decimal/divide"| n11
  n26["GCF(3, 5) = 1"]
  n27{{"factor · within"}}
  n0 --> n27
  n27 --> n26
  n26 -->|"simplify-fraction/gcf"| n17
  n28["3 × 40 = 120"]
  n29{{"multiply · across"}}
  n0 --> n29
  n29 --> n28
  n28 --> n2
  n30["5 × 2 = 10"]
  n31{{"multiply · within"}}
  n0 --> n31
  n31 --> n30
  n30 -->|"to-decimal/power_of_ten"| n8
  n32["5 × 8 = 40"]
  n31 --> n32
  n32 --> n14
  classDef cls fill:#eef0f6,stroke:#8a90a6,color:#222
  classDef first fill:#e3edfd,stroke:#5b7fd1,color:#222
  classDef second fill:#efe6fb,stroke:#8b63c9,color:#222
  classDef method fill:#fff1cc,stroke:#c99a1a,color:#222,font-weight:bold
  classDef skill fill:#e3f4e6,stroke:#3f9a55,stroke-dasharray:5 3,color:#222
  classDef step fill:#ffffff,stroke:#999,color:#222
  classDef ans fill:#fde4e1,stroke:#c4554a,color:#222
  class n22,n24,n27,n29,n31 cls
  class n21,n23,n25,n26,n28,n30,n32 first
  class n2,n5,n8,n11,n14,n17 method
  class n9,n12,n18 skill
  class n3,n4,n6,n7,n10,n13,n15,n16,n19,n20 step
  class n0,n1 ans
```

### Solve 4/6 = x/15.

```mermaid
flowchart LR
  n0(["Solve 4/6 = x/15."])
  n1(["Answer: 10"])
  n2["Cross-multiply and divide"]
  n3["4 × 15 = 60"]
  n2 --> n3
  n4["60 ÷ 6 = 10"]
  n3 --> n4
  n4 --> n1
  n5["Scale factor"]
  n6["15 ÷ 6 = 2.5"]
  n5 --> n6
  n7["4 × 2.5 = 10"]
  n6 --> n7
  n7 --> n1
  n8["Unit rate"]
  n9["Write 4/6 as a decimal → ≈ 0.667"]
  n8 --> n9
  n10["2/3 × 15 = 10"]
  n9 --> n10
  n10 --> n1
  n11["Inverse rate"]
  n12["Write 6/4 as a decimal → 1.5"]
  n11 --> n12
  n13["15 ÷ 1.5 = 10"]
  n12 --> n13
  n13 --> n1
  n14["Simplify, then scale"]
  n15["Simplify 4/6 → 2/3"]
  n14 --> n15
  n16["15 ÷ 3 = 5"]
  n15 --> n16
  n17["2 × 5 = 10"]
  n16 --> n17
  n17 --> n1
  n18["15 ÷ 6 = 2.5"]
  n19{{"divide · across"}}
  n0 --> n19
  n19 --> n18
  n18 --> n5
  n20["4 ÷ 6 ≈ 0.667"]
  n21{{"divide · within"}}
  n0 --> n21
  n21 --> n20
  n20 -->|"to-decimal/divide"| n8
  n22["6 ÷ 4 = 1.5"]
  n21 --> n22
  n22 -->|"to-decimal/divide"| n11
  n23["4 ÷ 2 = 2"]
  n24{{"factor · within"}}
  n0 --> n24
  n24 --> n23
  n23 -->|"simplify-fraction/repeated"| n14
  n25["GCF(4, 6) = 2"]
  n24 --> n25
  n25 -->|"simplify-fraction/gcf"| n14
  n26["4 × 15 = 60"]
  n27{{"multiply · across"}}
  n0 --> n27
  n27 --> n26
  n26 --> n2
  n28["4 × 25 = 100"]
  n29{{"multiply · within"}}
  n0 --> n29
  n29 --> n28
  n28 -->|"to-decimal/power_of_ten"| n11
  classDef cls fill:#eef0f6,stroke:#8a90a6,color:#222
  classDef first fill:#e3edfd,stroke:#5b7fd1,color:#222
  classDef second fill:#efe6fb,stroke:#8b63c9,color:#222
  classDef method fill:#fff1cc,stroke:#c99a1a,color:#222,font-weight:bold
  classDef skill fill:#e3f4e6,stroke:#3f9a55,stroke-dasharray:5 3,color:#222
  classDef step fill:#ffffff,stroke:#999,color:#222
  classDef ans fill:#fde4e1,stroke:#c4554a,color:#222
  class n19,n21,n24,n27,n29 cls
  class n18,n20,n22,n23,n25,n26,n28 first
  class n2,n5,n8,n11,n14 method
  class n9,n12,n15 skill
  class n3,n4,n6,n7,n10,n13,n16,n17 step
  class n0,n1 ans
```

Not applicable here: Ratio table (`ratio_table`)


<a name="better-buy"></a>

## Which is the better buy?

`better-buy` · applied · prompt: *Offer 1: {q1} units for ${p1}. Offer 2: {q2} units for ${p2}. Which is the better buy?*

Reduces to [compare-fractions](#compare-fractions) with `{"a": "p1", "b": "q1", "c": "p2", "d": "q2"}`. Compare the prices per unit p1/q1 and p2/q2; the smaller one is the better buy, so 'first' (bigger) maps to 'second'.

| Method | Idea | Steps use |
|---|---|---|
| **Price per unit** `price_per_unit` (= compare-fractions · decimal) | Find the cost of 1 unit in each offer; lower is better. | — |
| **Units per dollar** `units_per_dollar` (= compare-fractions · unit_rate) | Find how much $1 buys; more is better. | — |
| **Common quantity** `common_quantity` (= compare-fractions · common_denominator) | Price both offers at the same quantity. | — |
| **Scale one offer to the other's size** `scale_up` (= compare-fractions · match_denominator) | What would offer 1 cost for {q2} units? | — |
| **Cross-multiply** `cross_multiply` (= compare-fractions · cross_multiply) | {a}/{b} > {c}/{d} exactly when {a}×{d} > {c}×{b}. | — |
| **Compare growth** `compare_growth` (= compare-fractions · scale_factor) | Price grows by {p2} ÷ {p1}, quantity by {q2} ÷ {q1}; quantity growing faster means offer 2 is better. | — |

Reading the graphs: **hexagons** group first steps by operation · scope; **blue** = first step, **purple** = second step (only where methods share a first step); **yellow** = method; **green dashed** = a call to another question (see its own page); edge labels show which skill method produced the step.

### Offer 1: 12 units for $3. Offer 2: 20 units for $4.5. Which is the better buy?

```mermaid
flowchart LR
  n0(["Offer 1: 12 units for $3. Offer 2: 20 units for $4.5. Which is the better buy?"])
  n1(["Answer: second"])
  n2["Price per unit"]
  n3["Write 3/12 as a decimal → 0.25"]
  n2 --> n3
  n4["Write 4.5/20 as a decimal → 0.225"]
  n3 --> n4
  n5["0.25 #gt; 0.225"]
  n4 --> n5
  n5 --> n1
  n6["Units per dollar"]
  n7["Write 12/3 as a decimal → 4"]
  n6 --> n7
  n8["Write 20/4.5 as a decimal → ≈ 4.444"]
  n7 --> n8
  n9["4 #lt; 40/9"]
  n8 --> n9
  n9 --> n1
  n10["Common quantity"]
  n11["Find a common multiple of 12 and 20 → 60"]
  n10 --> n11
  n12["Solve 3/12 = x/60 → 15"]
  n11 --> n12
  n13["Solve 4.5/20 = x/60 → 13.5"]
  n12 --> n13
  n14["15 #gt; 13.5"]
  n13 --> n14
  n14 --> n1
  n15["Scale one offer to the other's size"]
  n16["Solve 3/12 = x/20 → 5"]
  n15 --> n16
  n17["5 #gt; 4.5"]
  n16 --> n17
  n17 --> n1
  n18["Cross-multiply"]
  n19["Find the cross products of 3/12 and 4.5/20 → 60/54"]
  n18 --> n19
  n20["60 #gt; 54"]
  n19 --> n20
  n20 --> n1
  n21["Compare growth"]
  n22["4.5 ÷ 3 = 1.5"]
  n21 --> n22
  n23["20 ÷ 12 ≈ 1.667"]
  n22 --> n23
  n24["1.5 #lt; 5/3"]
  n23 --> n24
  n24 --> n1
  n25["20 ÷ 12 ≈ 1.667"]
  n26{{"divide · across"}}
  n0 --> n26
  n26 --> n25
  n25 -->|"missing-value/scale_factor"| n15
  n27["4.5 ÷ 3 = 1.5"]
  n26 --> n27
  n27 --> n21
  n28["12 ÷ 3 = 4"]
  n29{{"divide · within"}}
  n0 --> n29
  n29 --> n28
  n30["then 20 ÷ 4.5 ≈ 4.444"]
  n28 --> n30
  n30 -->|"to-decimal/divide"| n6
  n31["then 20 ÷ 4 = 5"]
  n28 --> n31
  n31 -->|"missing-value/inverse_rate"| n15
  n32["3 ÷ 12 = 0.25"]
  n29 --> n32
  n33["then 4.5 ÷ 20 = 0.225"]
  n32 --> n33
  n33 -->|"to-decimal/divide"| n2
  n34["then 20 × 5 = 100"]
  n32 --> n34
  n34 -->|"to-decimal/power_of_ten"| n2
  n35["then 0.25 × 20 = 5"]
  n32 --> n35
  n35 -->|"missing-value/unit_rate"| n15
  n36["GCF(12, 20) = 4"]
  n37{{"factor · across"}}
  n0 --> n37
  n37 --> n36
  n36 -->|"common-multiple/gcf_formula"| n10
  n38["3 ÷ 3 = 1"]
  n39{{"factor · within"}}
  n0 --> n39
  n39 --> n38
  n38 -->|"simplify-fraction/repeated"| n15
  n40["GCF(3, 12) = 3"]
  n39 --> n40
  n40 -->|"simplify-fraction/gcf"| n15
  n41["12 × 20 = 240"]
  n42{{"multiply · across"}}
  n0 --> n42
  n42 --> n41
  n41 -->|"common-multiple/product"| n10
  n43["3 × 20 = 60"]
  n42 --> n43
  n44["then 60 ÷ 12 = 5"]
  n43 --> n44
  n44 -->|"missing-value/cross_multiply"| n15
  n45["then 4.5 × 12 = 54"]
  n43 --> n45
  n45 -->|"cross-products/diagonals"| n18
  n46["LCM(12, 20) = 60"]
  n42 --> n46
  n46 -->|"common-multiple/recall"| n10
  n47["12 × 5 = 60"]
  n48{{"multiply · within"}}
  n0 --> n48
  n48 --> n47
  n47 -->|"common-multiple/list_multiples"| n10
  classDef cls fill:#eef0f6,stroke:#8a90a6,color:#222
  classDef first fill:#e3edfd,stroke:#5b7fd1,color:#222
  classDef second fill:#efe6fb,stroke:#8b63c9,color:#222
  classDef method fill:#fff1cc,stroke:#c99a1a,color:#222,font-weight:bold
  classDef skill fill:#e3f4e6,stroke:#3f9a55,stroke-dasharray:5 3,color:#222
  classDef step fill:#ffffff,stroke:#999,color:#222
  classDef ans fill:#fde4e1,stroke:#c4554a,color:#222
  class n26,n29,n37,n39,n42,n48 cls
  class n25,n27,n28,n32,n36,n38,n40,n41,n43,n46,n47 first
  class n30,n31,n33,n34,n35,n44,n45 second
  class n2,n6,n10,n15,n18,n21 method
  class n3,n4,n7,n8,n11,n12,n13,n16,n19 skill
  class n5,n9,n14,n17,n20,n22,n23,n24 step
  class n0,n1 ans
```

### Offer 1: 6 units for $4.2. Offer 2: 10 units for $7.5. Which is the better buy?

```mermaid
flowchart LR
  n0(["Offer 1: 6 units for $4.2. Offer 2: 10 units for $7.5. Which is the better buy?"])
  n1(["Answer: first"])
  n2["Price per unit"]
  n3["Write 4.2/6 as a decimal → 0.7"]
  n2 --> n3
  n4["Write 7.5/10 as a decimal → 0.75"]
  n3 --> n4
  n5["0.7 #lt; 0.75"]
  n4 --> n5
  n5 --> n1
  n6["Units per dollar"]
  n7["Write 6/4.2 as a decimal → ≈ 1.429"]
  n6 --> n7
  n8["Write 10/7.5 as a decimal → ≈ 1.333"]
  n7 --> n8
  n9["10/7 #gt; 4/3"]
  n8 --> n9
  n9 --> n1
  n10["Common quantity"]
  n11["Find a common multiple of 6 and 10 → 30"]
  n10 --> n11
  n12["Solve 4.2/6 = x/30 → 21"]
  n11 --> n12
  n13["Solve 7.5/10 = x/30 → 22.5"]
  n12 --> n13
  n14["21 #lt; 22.5"]
  n13 --> n14
  n14 --> n1
  n15["Scale one offer to the other's size"]
  n16["Solve 4.2/6 = x/10 → 7"]
  n15 --> n16
  n17["7 #lt; 7.5"]
  n16 --> n17
  n17 --> n1
  n18["Cross-multiply"]
  n19["Find the cross products of 4.2/6 and 7.5/10 → 42/45"]
  n18 --> n19
  n20["42 #lt; 45"]
  n19 --> n20
  n20 --> n1
  n21["Compare growth"]
  n22["7.5 ÷ 4.2 ≈ 1.786"]
  n21 --> n22
  n23["10 ÷ 6 ≈ 1.667"]
  n22 --> n23
  n24["25/14 #gt; 5/3"]
  n23 --> n24
  n24 --> n1
  n25["10 ÷ 6 ≈ 1.667"]
  n26{{"divide · across"}}
  n0 --> n26
  n26 --> n25
  n25 -->|"missing-value/scale_factor"| n15
  n27["7.5 ÷ 4.2 ≈ 1.786"]
  n26 --> n27
  n27 --> n21
  n28["4.2 ÷ 6 = 0.7"]
  n29{{"divide · within"}}
  n0 --> n29
  n29 --> n28
  n30["then 7.5 ÷ 10 = 0.75"]
  n28 --> n30
  n30 -->|"to-decimal/divide / to-decimal/power_of_ten"| n2
  n31["then 0.7 × 10 = 7"]
  n28 --> n31
  n31 -->|"missing-value/unit_rate"| n15
  n32["6 ÷ 4.2 ≈ 1.429"]
  n29 --> n32
  n33["then 10 ÷ 7.5 ≈ 1.333"]
  n32 --> n33
  n33 -->|"to-decimal/divide"| n6
  n34["then 10 ÷ 10/7 = 7"]
  n32 --> n34
  n34 -->|"missing-value/inverse_rate"| n15
  n35["GCF(6, 10) = 2"]
  n36{{"factor · across"}}
  n0 --> n36
  n36 --> n35
  n35 -->|"common-multiple/gcf_formula"| n10
  n37["4.2 × 10 = 42"]
  n38{{"multiply · across"}}
  n0 --> n38
  n38 --> n37
  n39["then 42 ÷ 6 = 7"]
  n37 --> n39
  n39 -->|"missing-value/cross_multiply"| n15
  n40["then 7.5 × 6 = 45"]
  n37 --> n40
  n40 -->|"cross-products/diagonals"| n18
  n41["6 × 10 = 60"]
  n38 --> n41
  n41 -->|"common-multiple/product"| n10
  n42["LCM(6, 10) = 30"]
  n38 --> n42
  n42 -->|"common-multiple/recall"| n10
  n43["6 × 5 = 30"]
  n44{{"multiply · within"}}
  n0 --> n44
  n44 --> n43
  n43 -->|"common-multiple/list_multiples"| n10
  classDef cls fill:#eef0f6,stroke:#8a90a6,color:#222
  classDef first fill:#e3edfd,stroke:#5b7fd1,color:#222
  classDef second fill:#efe6fb,stroke:#8b63c9,color:#222
  classDef method fill:#fff1cc,stroke:#c99a1a,color:#222,font-weight:bold
  classDef skill fill:#e3f4e6,stroke:#3f9a55,stroke-dasharray:5 3,color:#222
  classDef step fill:#ffffff,stroke:#999,color:#222
  classDef ans fill:#fde4e1,stroke:#c4554a,color:#222
  class n26,n29,n36,n38,n44 cls
  class n25,n27,n28,n32,n35,n37,n41,n42,n43 first
  class n30,n31,n33,n34,n39,n40 second
  class n2,n6,n10,n15,n18,n21 method
  class n3,n4,n7,n8,n11,n12,n13,n16,n19 skill
  class n5,n9,n14,n17,n20,n22,n23,n24 step
  class n0,n1 ans
```


<a name="percent-of"></a>

## Find a percent of a number

`percent-of` · applied · prompt: *What is {p}% of {n}?*

Reduces to [missing-value](#missing-value) with `{"a": "p", "b": 100, "d": "n"}`. p% of n means p/100 = x/n.

| Method | Idea | Steps use |
|---|---|---|
| **Convert to a decimal and multiply** `decimal` (= missing-value · unit_rate) | {p}% = {p} ÷ 100; multiply that by {n}. | — |
| **Find 1% first** `one_percent` (= missing-value · scale_factor) | 1% of {n} is {n} ÷ 100; multiply by {p}. | — |
| **Multiply, then divide by 100** `multiply_first` (= missing-value · cross_multiply) | {p} × {n} ÷ 100. | — |
| **Use a simplified fraction** `fraction` (= missing-value · simplify_then_scale) | {p}/100 simplifies (15/100 = 3/20); take that fraction of {n}. | — |
| **Ratio table** `ratio_table` (= missing-value · ratio_table) | Scale {p}:100 until the 100 becomes {n}. | — |
| **Build from 10% and 5%** `benchmark_10_5` | 10% is easy (÷ 10) and 5% is half of that; add up the pieces. | — |

Reading the graphs: **hexagons** group first steps by operation · scope; **blue** = first step, **purple** = second step (only where methods share a first step); **yellow** = method; **green dashed** = a call to another question (see its own page); edge labels show which skill method produced the step.

### What is 15% of 80?

```mermaid
flowchart LR
  n0(["What is 15% of 80?"])
  n1(["Answer: 12"])
  n2["Convert to a decimal and multiply"]
  n3["Write 15/100 as a decimal → 0.15"]
  n2 --> n3
  n4["0.15 × 80 = 12"]
  n3 --> n4
  n4 --> n1
  n5["Find 1% first"]
  n6["80 ÷ 100 = 0.8"]
  n5 --> n6
  n7["15 × 0.8 = 12"]
  n6 --> n7
  n7 --> n1
  n8["Multiply, then divide by 100"]
  n9["15 × 80 = 1200"]
  n8 --> n9
  n10["1200 ÷ 100 = 12"]
  n9 --> n10
  n10 --> n1
  n11["Use a simplified fraction"]
  n12["Simplify 15/100 → 3/20"]
  n11 --> n12
  n13["80 ÷ 20 = 4"]
  n12 --> n13
  n14["3 × 4 = 12"]
  n13 --> n14
  n14 --> n1
  n15["Build from 10% and 5%"]
  n16["80 ÷ 10 = 8"]
  n15 --> n16
  n17["8 ÷ 2 = 4"]
  n16 --> n17
  n18["8 × 1 = 8"]
  n17 --> n18
  n19["4 × 1 = 4"]
  n18 --> n19
  n20["8 + 4 = 12"]
  n19 --> n20
  n20 --> n1
  n21["0.15 × 80 = 12"]
  n22{{"after 15 ÷ 100 = 0.15 in their head"}}
  n0 --> n22
  n22 --> n21
  n21 --> n2
  n23["15 ÷ 100 = 0.15"]
  n24{{"divide · within"}}
  n0 --> n24
  n24 --> n23
  n23 -->|"to-decimal/divide / to-decimal/power_of_ten"| n2
  n25["80 ÷ 10 = 8"]
  n24 --> n25
  n25 --> n15
  n26["80 ÷ 100 = 0.8"]
  n24 --> n26
  n26 --> n5
  n27["15 ÷ 5 = 3"]
  n28{{"factor · within"}}
  n0 --> n28
  n28 --> n27
  n27 -->|"simplify-fraction/repeated"| n11
  n29["GCF(15, 100) = 5"]
  n28 --> n29
  n29 -->|"simplify-fraction/gcf"| n11
  n30["15 × 80 = 1200"]
  n31{{"multiply · across"}}
  n0 --> n31
  n31 --> n30
  n30 --> n8
  classDef cls fill:#eef0f6,stroke:#8a90a6,color:#222
  classDef first fill:#e3edfd,stroke:#5b7fd1,color:#222
  classDef second fill:#efe6fb,stroke:#8b63c9,color:#222
  classDef method fill:#fff1cc,stroke:#c99a1a,color:#222,font-weight:bold
  classDef skill fill:#e3f4e6,stroke:#3f9a55,stroke-dasharray:5 3,color:#222
  classDef step fill:#ffffff,stroke:#999,color:#222
  classDef ans fill:#fde4e1,stroke:#c4554a,color:#222
  class n22,n24,n28,n31 cls
  class n21,n23,n25,n26,n27,n29,n30 first
  class n2,n5,n8,n11,n15 method
  class n3,n12 skill
  class n4,n6,n7,n9,n10,n13,n14,n16,n17,n18,n19,n20 step
  class n0,n1 ans
```

Not applicable here: Ratio table (`ratio_table`)

### What is 35% of 60?

```mermaid
flowchart LR
  n0(["What is 35% of 60?"])
  n1(["Answer: 21"])
  n2["Convert to a decimal and multiply"]
  n3["Write 35/100 as a decimal → 0.35"]
  n2 --> n3
  n4["0.35 × 60 = 21"]
  n3 --> n4
  n4 --> n1
  n5["Find 1% first"]
  n6["60 ÷ 100 = 0.6"]
  n5 --> n6
  n7["35 × 0.6 = 21"]
  n6 --> n7
  n7 --> n1
  n8["Multiply, then divide by 100"]
  n9["35 × 60 = 2100"]
  n8 --> n9
  n10["2100 ÷ 100 = 21"]
  n9 --> n10
  n10 --> n1
  n11["Use a simplified fraction"]
  n12["Simplify 35/100 → 7/20"]
  n11 --> n12
  n13["60 ÷ 20 = 3"]
  n12 --> n13
  n14["7 × 3 = 21"]
  n13 --> n14
  n14 --> n1
  n15["Build from 10% and 5%"]
  n16["60 ÷ 10 = 6"]
  n15 --> n16
  n17["6 ÷ 2 = 3"]
  n16 --> n17
  n18["6 × 3 = 18"]
  n17 --> n18
  n19["3 × 1 = 3"]
  n18 --> n19
  n20["18 + 3 = 21"]
  n19 --> n20
  n20 --> n1
  n21["0.35 × 60 = 21"]
  n22{{"after 35 ÷ 100 = 0.35 in their head"}}
  n0 --> n22
  n22 --> n21
  n21 --> n2
  n23["35 ÷ 100 = 0.35"]
  n24{{"divide · within"}}
  n0 --> n24
  n24 --> n23
  n23 -->|"to-decimal/divide / to-decimal/power_of_ten"| n2
  n25["60 ÷ 10 = 6"]
  n24 --> n25
  n25 --> n15
  n26["60 ÷ 100 = 0.6"]
  n24 --> n26
  n26 --> n5
  n27["35 ÷ 5 = 7"]
  n28{{"factor · within"}}
  n0 --> n28
  n28 --> n27
  n27 -->|"simplify-fraction/repeated"| n11
  n29["GCF(35, 100) = 5"]
  n28 --> n29
  n29 -->|"simplify-fraction/gcf"| n11
  n30["35 × 60 = 2100"]
  n31{{"multiply · across"}}
  n0 --> n31
  n31 --> n30
  n30 --> n8
  classDef cls fill:#eef0f6,stroke:#8a90a6,color:#222
  classDef first fill:#e3edfd,stroke:#5b7fd1,color:#222
  classDef second fill:#efe6fb,stroke:#8b63c9,color:#222
  classDef method fill:#fff1cc,stroke:#c99a1a,color:#222,font-weight:bold
  classDef skill fill:#e3f4e6,stroke:#3f9a55,stroke-dasharray:5 3,color:#222
  classDef step fill:#ffffff,stroke:#999,color:#222
  classDef ans fill:#fde4e1,stroke:#c4554a,color:#222
  class n22,n24,n28,n31 cls
  class n21,n23,n25,n26,n27,n29,n30 first
  class n2,n5,n8,n11,n15 method
  class n3,n12 skill
  class n4,n6,n7,n9,n10,n13,n14,n16,n17,n18,n19,n20 step
  class n0,n1 ans
```

Not applicable here: Ratio table (`ratio_table`)


<a name="proportion-check"></a>

## Are two ratios proportional?

`proportion-check` · applied · prompt: *Are {a}:{b} and {c}:{d} proportional?*

Reduces to [compare-fractions](#compare-fractions) with `{"a": "a", "b": "b", "c": "c", "d": "d"}`. 

| Method | Idea | Steps use |
|---|---|---|
| **Cross-multiply** `cross_multiply` (= compare-fractions · cross_multiply) | {a}/{b} > {c}/{d} exactly when {a}×{d} > {c}×{b}. | — |
| **Common denominator** `common_denominator` (= compare-fractions · common_denominator) | Rewrite both fractions over the same denominator, then compare numerators. | — |
| **Rewrite one fraction over the other's denominator** `match_denominator` (= compare-fractions · match_denominator) | Turn {a}/{b} into something over {d}, then compare numerators with {c}. | — |
| **Common numerator** `common_numerator` (= compare-fractions · common_numerator) | With equal numerators, the smaller denominator gives the bigger fraction. | — |
| **Convert to decimals** `decimal` (= compare-fractions · decimal) | Write each fraction as a decimal and compare. | — |
| **Compare unit rates (flipped fractions)** `unit_rate` (= compare-fractions · unit_rate) | How much bottom per 1 of top? The bigger rate belongs to the smaller fraction. | — |
| **Compare scale factors** `scale_factor` (= compare-fractions · scale_factor) | How much do the tops grow ({c} ÷ {a}) compared with the bottoms ({d} ÷ {b})? | — |
| **Ratio table** `ratio_table` (= compare-fractions · ratio_table) | Scale {a}:{b} by 2, 3, 4, … until the top reaches {c}, then compare bottoms. | — |
| **Graph the points** `graph` (= compare-fractions · graph) | Plot ({a}, {b}) and ({c}, {d}); the steeper line from the origin belongs to the smaller fraction. | — |
| **Simplify both** `simplify` (= compare-fractions · simplify) | Reduce both fractions to lowest terms; equal fractions reduce to the same thing. | — |
| **Distance from 1** `distance_from_one` (= compare-fractions · distance_from_one) | Find how far each fraction is from 1; the one closer to 1 is bigger. | — |

Reading the graphs: **hexagons** group first steps by operation · scope; **blue** = first step, **purple** = second step (only where methods share a first step); **yellow** = method; **green dashed** = a call to another question (see its own page); edge labels show which skill method produced the step.

### Are 6:8 and 72:96 proportional?

```mermaid
flowchart LR
  n0(["Are 6:8 and 72:96 proportional?"])
  n1(["Answer: proportional"])
  n2["Cross-multiply"]
  n3["Find the cross products of 6/8 and 72/96 → 576/576"]
  n2 --> n3
  n4["576 = 576"]
  n3 --> n4
  n4 --> n1
  n5["Common denominator"]
  n6["Find a common multiple of 8 and 96 → 96"]
  n5 --> n6
  n7["Solve 6/8 = x/96 → 72"]
  n6 --> n7
  n8["Solve 72/96 = x/96 → 72"]
  n7 --> n8
  n9["72 = 72"]
  n8 --> n9
  n9 --> n1
  n10["Rewrite one fraction over the other's denominator"]
  n11["Solve 6/8 = x/96 → 72"]
  n10 --> n11
  n12["72 = 72"]
  n11 --> n12
  n12 --> n1
  n13["Common numerator"]
  n14["Find a common multiple of 6 and 72 → 72"]
  n13 --> n14
  n15["Solve 8/6 = x/72 → 96"]
  n14 --> n15
  n16["Solve 96/72 = x/72 → 96"]
  n15 --> n16
  n17["96 = 96"]
  n16 --> n17
  n17 --> n1
  n18["Convert to decimals"]
  n19["Write 6/8 as a decimal → 0.75"]
  n18 --> n19
  n20["Write 72/96 as a decimal → 0.75"]
  n19 --> n20
  n21["0.75 = 0.75"]
  n20 --> n21
  n21 --> n1
  n22["Compare unit rates (flipped fractions)"]
  n23["Write 8/6 as a decimal → ≈ 1.333"]
  n22 --> n23
  n24["Write 96/72 as a decimal → ≈ 1.333"]
  n23 --> n24
  n25["4/3 = 4/3"]
  n24 --> n25
  n25 --> n1
  n26["Compare scale factors"]
  n27["72 ÷ 6 = 12"]
  n26 --> n27
  n28["96 ÷ 8 = 12"]
  n27 --> n28
  n29["12 = 12"]
  n28 --> n29
  n29 --> n1
  n30["Ratio table"]
  n31["6 × 12 = 72"]
  n30 --> n31
  n32["8 × 12 = 96"]
  n31 --> n32
  n33["96 = 96"]
  n32 --> n33
  n33 --> n1
  n34["Graph the points"]
  n35["plot (6, 8), (72, 96)"]
  n34 --> n35
  n36["8 ÷ 6 ≈ 1.333"]
  n35 --> n36
  n37["96 ÷ 72 ≈ 1.333"]
  n36 --> n37
  n38["4/3 = 4/3"]
  n37 --> n38
  n38 --> n1
  n39["Simplify both"]
  n40["Simplify 6/8 → 3/4"]
  n39 --> n40
  n41["Simplify 72/96 → 3/4"]
  n40 --> n41
  n42["3:4 = 3:4"]
  n41 --> n42
  n42 --> n1
  n43["Distance from 1"]
  n44["8 − 6 = 2"]
  n43 --> n44
  n45["96 − 72 = 24"]
  n44 --> n45
  n46["Which is larger: 2/8 or 24/96? (Or are they equal?) → equal"]
  n45 --> n46
  n46 --> n1
  n47["72 ÷ 6 = 12"]
  n48{{"divide · across"}}
  n0 --> n48
  n48 --> n47
  n47 --> n26
  n49["96 ÷ 8 = 12"]
  n48 --> n49
  n49 -->|"missing-value/scale_factor"| n10
  n50["6 ÷ 8 = 0.75"]
  n51{{"divide · within"}}
  n0 --> n51
  n51 --> n50
  n52["then 0.75 × 96 = 72"]
  n50 --> n52
  n52 -->|"missing-value/unit_rate"| n10
  n53["then 72 ÷ 96 = 0.75"]
  n50 --> n53
  n53 -->|"to-decimal/divide"| n18
  n54["8 ÷ 6 ≈ 1.333"]
  n51 --> n54
  n55["then 96 ÷ 4/3 = 72"]
  n54 --> n55
  n55 -->|"missing-value/inverse_rate"| n10
  n56["then 96 ÷ 72 ≈ 1.333"]
  n54 --> n56
  n56 -->|"to-decimal/divide"| n22
  n57["GCF(6, 72) = 6"]
  n58{{"factor · across"}}
  n0 --> n58
  n58 --> n57
  n57 -->|"common-multiple/gcf_formula"| n13
  n59["GCF(8, 96) = 8"]
  n58 --> n59
  n59 -->|"common-multiple/gcf_formula"| n5
  n60["6 ÷ 2 = 3"]
  n61{{"factor · within"}}
  n0 --> n61
  n61 --> n60
  n62["then 8 ÷ 2 = 4"]
  n60 --> n62
  n62 -->|"simplify-fraction/repeated"| n10
  n62 -->|"simplify-fraction/repeated"| n39
  n63["GCF(6, 8) = 2"]
  n61 --> n63
  n64["then 6 ÷ 2 = 3"]
  n63 --> n64
  n64 -->|"simplify-fraction/gcf"| n10
  n64 -->|"simplify-fraction/gcf"| n39
  n65["6 × 72 = 432"]
  n66{{"multiply · across"}}
  n0 --> n66
  n66 --> n65
  n65 -->|"common-multiple/product"| n13
  n67["6 × 96 = 576"]
  n66 --> n67
  n68["then 72 × 8 = 576"]
  n67 --> n68
  n68 -->|"cross-products/diagonals"| n2
  n69["then 576 ÷ 8 = 72"]
  n67 --> n69
  n69 -->|"missing-value/cross_multiply"| n10
  n70["8 × 96 = 768"]
  n66 --> n70
  n70 -->|"common-multiple/product"| n5
  n71["LCM(6, 72) = 72"]
  n66 --> n71
  n71 -->|"common-multiple/recall"| n13
  n72["LCM(8, 96) = 96"]
  n66 --> n72
  n72 -->|"common-multiple/recall"| n5
  n73["6 × 12 = 72"]
  n74{{"multiply · within"}}
  n0 --> n74
  n74 --> n73
  n75["then 8 × 72 = 576"]
  n73 --> n75
  n75 -->|"missing-value/cross_multiply"| n13
  n76["then 72 ÷ 6 = 12"]
  n73 --> n76
  n76 -->|"missing-value/scale_factor"| n13
  n77["then 8 ÷ 6 ≈ 1.333"]
  n73 --> n77
  n77 -->|"to-decimal/divide"| n13
  n78["then 6 ÷ 8 = 0.75"]
  n73 --> n78
  n78 -->|"to-decimal/divide"| n13
  n79["then 8 × 125 = 1000"]
  n73 --> n79
  n79 -->|"to-decimal/power_of_ten"| n13
  n80["then 6 × 12 = 72"]
  n73 --> n80
  n80 -->|"missing-value/ratio_table"| n13
  n81["then GCF(8, 6) = 2"]
  n73 --> n81
  n81 -->|"simplify-fraction/gcf"| n13
  n82["then 8 ÷ 2 = 4"]
  n73 --> n82
  n82 -->|"simplify-fraction/repeated"| n13
  n83["then 8 × 12 = 96"]
  n73 --> n83
  n83 --> n30
  n84["8 × 12 = 96"]
  n74 --> n84
  n85["then 6 × 96 = 576"]
  n84 --> n85
  n85 -->|"missing-value/cross_multiply"| n5
  n86["then 96 ÷ 8 = 12"]
  n84 --> n86
  n86 -->|"missing-value/scale_factor"| n5
  n87["then 6 ÷ 8 = 0.75"]
  n84 --> n87
  n87 -->|"to-decimal/divide"| n5
  n88["then 8 × 125 = 1000"]
  n84 --> n88
  n88 -->|"to-decimal/power_of_ten"| n5
  n89["then 8 ÷ 6 ≈ 1.333"]
  n84 --> n89
  n89 -->|"to-decimal/divide"| n5
  n90["then 8 × 12 = 96"]
  n84 --> n90
  n90 -->|"missing-value/ratio_table"| n5
  n91["then GCF(6, 8) = 2"]
  n84 --> n91
  n91 -->|"simplify-fraction/gcf"| n5
  n92["then 6 ÷ 2 = 3"]
  n84 --> n92
  n92 -->|"simplify-fraction/repeated"| n5
  n93["then 6 × 12 = 72"]
  n84 --> n93
  n93 -->|"missing-value/ratio_table"| n10
  n94["8 × 125 = 1000"]
  n74 --> n94
  n95["then 6 × 125 = 750"]
  n94 --> n95
  n95 -->|"to-decimal/power_of_ten"| n18
  n95 -->|"to-decimal/power_of_ten"| n10
  n96["plot (6, 8), (72, 96)"]
  n97{{"represent · across"}}
  n0 --> n97
  n97 --> n96
  n96 --> n34
  n98["8 − 6 = 2"]
  n99{{"subtract · within"}}
  n0 --> n99
  n99 --> n98
  n98 --> n43
  classDef cls fill:#eef0f6,stroke:#8a90a6,color:#222
  classDef first fill:#e3edfd,stroke:#5b7fd1,color:#222
  classDef second fill:#efe6fb,stroke:#8b63c9,color:#222
  classDef method fill:#fff1cc,stroke:#c99a1a,color:#222,font-weight:bold
  classDef skill fill:#e3f4e6,stroke:#3f9a55,stroke-dasharray:5 3,color:#222
  classDef step fill:#ffffff,stroke:#999,color:#222
  classDef ans fill:#fde4e1,stroke:#c4554a,color:#222
  class n48,n51,n58,n61,n66,n74,n97,n99 cls
  class n47,n49,n50,n54,n57,n59,n60,n63,n65,n67,n70,n71,n72,n73,n84,n94,n96,n98 first
  class n52,n53,n55,n56,n62,n64,n68,n69,n75,n76,n77,n78,n79,n80,n81,n82,n83,n85,n86,n87,n88,n89,n90,n91,n92,n93,n95 second
  class n2,n5,n10,n13,n18,n22,n26,n30,n34,n39,n43 method
  class n3,n6,n7,n8,n11,n14,n15,n16,n19,n20,n23,n24,n40,n41,n46 skill
  class n4,n9,n12,n17,n21,n25,n27,n28,n29,n31,n32,n33,n35,n36,n37,n38,n42,n44,n45 step
  class n0,n1 ans
```

### Are 4:6 and 10:14 proportional?

```mermaid
flowchart LR
  n0(["Are 4:6 and 10:14 proportional?"])
  n1(["Answer: not proportional"])
  n2["Cross-multiply"]
  n3["Find the cross products of 4/6 and 10/14 → 56/60"]
  n2 --> n3
  n4["56 #lt; 60"]
  n3 --> n4
  n4 --> n1
  n5["Common denominator"]
  n6["Find a common multiple of 6 and 14 → 42"]
  n5 --> n6
  n7["Solve 4/6 = x/42 → 28"]
  n6 --> n7
  n8["Solve 10/14 = x/42 → 30"]
  n7 --> n8
  n9["28 #lt; 30"]
  n8 --> n9
  n9 --> n1
  n10["Rewrite one fraction over the other's denominator"]
  n11["Solve 4/6 = x/14 → 28/3"]
  n10 --> n11
  n12["28/3 #lt; 10"]
  n11 --> n12
  n12 --> n1
  n13["Common numerator"]
  n14["Find a common multiple of 4 and 10 → 20"]
  n13 --> n14
  n15["Solve 6/4 = x/20 → 30"]
  n14 --> n15
  n16["Solve 14/10 = x/20 → 28"]
  n15 --> n16
  n17["30 #gt; 28"]
  n16 --> n17
  n17 --> n1
  n18["Convert to decimals"]
  n19["Write 4/6 as a decimal → ≈ 0.667"]
  n18 --> n19
  n20["Write 10/14 as a decimal → ≈ 0.714"]
  n19 --> n20
  n21["2/3 #lt; 5/7"]
  n20 --> n21
  n21 --> n1
  n22["Compare unit rates (flipped fractions)"]
  n23["Write 6/4 as a decimal → 1.5"]
  n22 --> n23
  n24["Write 14/10 as a decimal → 1.4"]
  n23 --> n24
  n25["1.5 #gt; 1.4"]
  n24 --> n25
  n25 --> n1
  n26["Compare scale factors"]
  n27["10 ÷ 4 = 2.5"]
  n26 --> n27
  n28["14 ÷ 6 ≈ 2.333"]
  n27 --> n28
  n29["2.5 #gt; 7/3"]
  n28 --> n29
  n29 --> n1
  n30["Graph the points"]
  n31["plot (4, 6), (10, 14)"]
  n30 --> n31
  n32["6 ÷ 4 = 1.5"]
  n31 --> n32
  n33["14 ÷ 10 = 1.4"]
  n32 --> n33
  n34["1.5 #gt; 1.4"]
  n33 --> n34
  n34 --> n1
  n35["Simplify both"]
  n36["Simplify 4/6 → 2/3"]
  n35 --> n36
  n37["Simplify 10/14 → 5/7"]
  n36 --> n37
  n38["2:3 ≠ 5:7"]
  n37 --> n38
  n38 --> n1
  n39["Distance from 1"]
  n40["6 − 4 = 2"]
  n39 --> n40
  n41["14 − 10 = 4"]
  n40 --> n41
  n42["Which is larger: 2/6 or 4/14? (Or are they equal?) → first"]
  n41 --> n42
  n42 --> n1
  n43["10 ÷ 4 = 2.5"]
  n44{{"divide · across"}}
  n0 --> n44
  n44 --> n43
  n43 --> n26
  n45["14 ÷ 6 ≈ 2.333"]
  n44 --> n45
  n45 -->|"missing-value/scale_factor"| n10
  n46["4 ÷ 6 ≈ 0.667"]
  n47{{"divide · within"}}
  n0 --> n47
  n47 --> n46
  n48["then 2/3 × 14 = 28/3"]
  n46 --> n48
  n48 -->|"missing-value/unit_rate"| n10
  n49["then 10 ÷ 14 ≈ 0.714"]
  n46 --> n49
  n49 -->|"to-decimal/divide"| n18
  n50["6 ÷ 4 = 1.5"]
  n47 --> n50
  n51["then 14 ÷ 1.5 ≈ 9.333"]
  n50 --> n51
  n51 -->|"missing-value/inverse_rate"| n10
  n52["then 14 ÷ 10 = 1.4"]
  n50 --> n52
  n52 -->|"to-decimal/divide / to-decimal/power_of_ten"| n22
  n53["GCF(4, 10) = 2"]
  n54{{"factor · across"}}
  n0 --> n54
  n54 --> n53
  n53 -->|"common-multiple/gcf_formula"| n13
  n55["GCF(6, 14) = 2"]
  n54 --> n55
  n55 -->|"common-multiple/gcf_formula"| n5
  n56["4 ÷ 2 = 2"]
  n57{{"factor · within"}}
  n0 --> n57
  n57 --> n56
  n58["then 6 ÷ 2 = 3"]
  n56 --> n58
  n58 -->|"simplify-fraction/repeated"| n10
  n58 -->|"simplify-fraction/repeated"| n35
  n59["GCF(4, 6) = 2"]
  n57 --> n59
  n60["then 4 ÷ 2 = 2"]
  n59 --> n60
  n60 -->|"simplify-fraction/gcf"| n10
  n60 -->|"simplify-fraction/gcf"| n35
  n61["4 × 10 = 40"]
  n62{{"multiply · across"}}
  n0 --> n62
  n62 --> n61
  n61 -->|"common-multiple/product"| n13
  n63["4 × 14 = 56"]
  n62 --> n63
  n64["then 10 × 6 = 60"]
  n63 --> n64
  n64 -->|"cross-products/diagonals"| n2
  n65["then 56 ÷ 6 ≈ 9.333"]
  n63 --> n65
  n65 -->|"missing-value/cross_multiply"| n10
  n66["6 × 14 = 84"]
  n62 --> n66
  n66 -->|"common-multiple/product"| n5
  n67["LCM(4, 10) = 20"]
  n62 --> n67
  n67 -->|"common-multiple/recall"| n13
  n68["LCM(6, 14) = 42"]
  n62 --> n68
  n68 -->|"common-multiple/recall"| n5
  n69["4 × 25 = 100"]
  n70{{"multiply · within"}}
  n0 --> n70
  n70 --> n69
  n71["then 6 × 25 = 150"]
  n69 --> n71
  n71 -->|"to-decimal/power_of_ten"| n10
  n71 -->|"to-decimal/power_of_ten"| n22
  n72["4 × 5 = 20"]
  n70 --> n72
  n72 -->|"common-multiple/list_multiples"| n13
  n73["6 × 7 = 42"]
  n70 --> n73
  n73 -->|"common-multiple/list_multiples"| n5
  n74["plot (4, 6), (10, 14)"]
  n75{{"represent · across"}}
  n0 --> n75
  n75 --> n74
  n74 --> n30
  n76["6 − 4 = 2"]
  n77{{"subtract · within"}}
  n0 --> n77
  n77 --> n76
  n76 --> n39
  classDef cls fill:#eef0f6,stroke:#8a90a6,color:#222
  classDef first fill:#e3edfd,stroke:#5b7fd1,color:#222
  classDef second fill:#efe6fb,stroke:#8b63c9,color:#222
  classDef method fill:#fff1cc,stroke:#c99a1a,color:#222,font-weight:bold
  classDef skill fill:#e3f4e6,stroke:#3f9a55,stroke-dasharray:5 3,color:#222
  classDef step fill:#ffffff,stroke:#999,color:#222
  classDef ans fill:#fde4e1,stroke:#c4554a,color:#222
  class n44,n47,n54,n57,n62,n70,n75,n77 cls
  class n43,n45,n46,n50,n53,n55,n56,n59,n61,n63,n66,n67,n68,n69,n72,n73,n74,n76 first
  class n48,n49,n51,n52,n58,n60,n64,n65,n71 second
  class n2,n5,n10,n13,n18,n22,n26,n30,n35,n39 method
  class n3,n6,n7,n8,n11,n14,n15,n16,n19,n20,n23,n24,n36,n37,n42 skill
  class n4,n9,n12,n17,n21,n25,n27,n28,n29,n31,n32,n33,n34,n38,n40,n41 step
  class n0,n1 ans
```

Not applicable here: Ratio table (`ratio_table`)


<a name="common-multiple"></a>

## Find a common multiple

`common-multiple` · skill · prompt: *Find a common multiple of {x} and {y}.*

| Method | Idea | Steps use |
|---|---|---|
| **Know the LCM** `recall` | Recognize the least common multiple directly. | — |
| **List multiples** `list_multiples` | Count up by {x} until you reach a number {y} divides. | — |
| **Multiply them** `product` | {x} × {y} is always a common multiple. | — |
| **Use the GCF** `gcf_formula` | LCM = {x} ÷ GCF × {y}. | — |

Reading the graphs: **hexagons** group first steps by operation · scope; **blue** = first step, **purple** = second step (only where methods share a first step); **yellow** = method; **green dashed** = a call to another question (see its own page); edge labels show which skill method produced the step.

### Find a common multiple of 4 and 6.

```mermaid
flowchart LR
  n0(["Find a common multiple of 4 and 6."])
  n1(["Answer: 12"])
  n2["Know the LCM"]
  n3["LCM(4, 6) = 12"]
  n2 --> n3
  n3 --> n1
  n4["List multiples"]
  n5["4 × 3 = 12"]
  n4 --> n5
  n5 --> n1
  n6["Multiply them"]
  n7["4 × 6 = 24"]
  n6 --> n7
  n7 --> n1
  n8["Use the GCF"]
  n9["GCF(4, 6) = 2"]
  n8 --> n9
  n10["4 ÷ 2 = 2"]
  n9 --> n10
  n11["2 × 6 = 12"]
  n10 --> n11
  n11 --> n1
  n12["GCF(4, 6) = 2"]
  n13{{"factor · across"}}
  n0 --> n13
  n13 --> n12
  n12 --> n8
  n14["4 × 6 = 24"]
  n15{{"multiply · across"}}
  n0 --> n15
  n15 --> n14
  n14 --> n6
  n16["LCM(4, 6) = 12"]
  n15 --> n16
  n16 --> n2
  n17["4 × 3 = 12"]
  n18{{"multiply · within"}}
  n0 --> n18
  n18 --> n17
  n17 --> n4
  classDef cls fill:#eef0f6,stroke:#8a90a6,color:#222
  classDef first fill:#e3edfd,stroke:#5b7fd1,color:#222
  classDef second fill:#efe6fb,stroke:#8b63c9,color:#222
  classDef method fill:#fff1cc,stroke:#c99a1a,color:#222,font-weight:bold
  classDef skill fill:#e3f4e6,stroke:#3f9a55,stroke-dasharray:5 3,color:#222
  classDef step fill:#ffffff,stroke:#999,color:#222
  classDef ans fill:#fde4e1,stroke:#c4554a,color:#222
  class n13,n15,n18 cls
  class n12,n14,n16,n17 first
  class n2,n4,n6,n8 method
  class n3,n5,n7,n9,n10,n11 step
  class n0,n1 ans
```

### Find a common multiple of 4 and 7.

```mermaid
flowchart LR
  n0(["Find a common multiple of 4 and 7."])
  n1(["Answer: 28"])
  n2["Know the LCM"]
  n3["LCM(4, 7) = 28"]
  n2 --> n3
  n3 --> n1
  n4["List multiples"]
  n5["4 × 7 = 28"]
  n4 --> n5
  n5 --> n1
  n6["Multiply them"]
  n7["4 × 7 = 28"]
  n6 --> n7
  n7 --> n1
  n8["Use the GCF"]
  n9["GCF(4, 7) = 1"]
  n8 --> n9
  n10["4 ÷ 1 = 4"]
  n9 --> n10
  n11["4 × 7 = 28"]
  n10 --> n11
  n11 --> n1
  n12["GCF(4, 7) = 1"]
  n13{{"factor · across"}}
  n0 --> n13
  n13 --> n12
  n12 --> n8
  n14["LCM(4, 7) = 28"]
  n15{{"multiply · across"}}
  n0 --> n15
  n15 --> n14
  n14 --> n2
  n16["4 × 7 = 28"]
  n15 --> n16
  n17{{"multiply · within"}}
  n0 --> n17
  n17 --> n16
  n16 --> n4
  n16 --> n6
  classDef cls fill:#eef0f6,stroke:#8a90a6,color:#222
  classDef first fill:#e3edfd,stroke:#5b7fd1,color:#222
  classDef second fill:#efe6fb,stroke:#8b63c9,color:#222
  classDef method fill:#fff1cc,stroke:#c99a1a,color:#222,font-weight:bold
  classDef skill fill:#e3f4e6,stroke:#3f9a55,stroke-dasharray:5 3,color:#222
  classDef step fill:#ffffff,stroke:#999,color:#222
  classDef ans fill:#fde4e1,stroke:#c4554a,color:#222
  class n13,n15,n17 cls
  class n12,n14,n16 first
  class n2,n4,n6,n8 method
  class n3,n5,n7,n9,n10,n11 step
  class n0,n1 ans
```


<a name="cross-products"></a>

## Cross products

`cross-products` · skill · prompt: *Find the cross products of {a}/{b} and {c}/{d}.*

| Method | Idea | Steps use |
|---|---|---|
| **Multiply the diagonals** `diagonals` | Multiply each numerator by the other fraction's denominator. | — |

Reading the graphs: **hexagons** group first steps by operation · scope; **blue** = first step, **purple** = second step (only where methods share a first step); **yellow** = method; **green dashed** = a call to another question (see its own page); edge labels show which skill method produced the step.

### Find the cross products of 3/4 and 5/7.

```mermaid
flowchart LR
  n0(["Find the cross products of 3/4 and 5/7."])
  n1(["Answer: 21/20"])
  n2["Multiply the diagonals"]
  n3["3 × 7 = 21"]
  n2 --> n3
  n4["5 × 4 = 20"]
  n3 --> n4
  n4 --> n1
  n5["3 × 7 = 21"]
  n6{{"multiply · across"}}
  n0 --> n6
  n6 --> n5
  n5 --> n2
  classDef cls fill:#eef0f6,stroke:#8a90a6,color:#222
  classDef first fill:#e3edfd,stroke:#5b7fd1,color:#222
  classDef second fill:#efe6fb,stroke:#8b63c9,color:#222
  classDef method fill:#fff1cc,stroke:#c99a1a,color:#222,font-weight:bold
  classDef skill fill:#e3f4e6,stroke:#3f9a55,stroke-dasharray:5 3,color:#222
  classDef step fill:#ffffff,stroke:#999,color:#222
  classDef ans fill:#fde4e1,stroke:#c4554a,color:#222
  class n6 cls
  class n5 first
  class n2 method
  class n3,n4 step
  class n0,n1 ans
```

### Find the cross products of 6/8 and 72/96.

```mermaid
flowchart LR
  n0(["Find the cross products of 6/8 and 72/96."])
  n1(["Answer: 576/576"])
  n2["Multiply the diagonals"]
  n3["6 × 96 = 576"]
  n2 --> n3
  n4["72 × 8 = 576"]
  n3 --> n4
  n4 --> n1
  n5["6 × 96 = 576"]
  n6{{"multiply · across"}}
  n0 --> n6
  n6 --> n5
  n5 --> n2
  classDef cls fill:#eef0f6,stroke:#8a90a6,color:#222
  classDef first fill:#e3edfd,stroke:#5b7fd1,color:#222
  classDef second fill:#efe6fb,stroke:#8b63c9,color:#222
  classDef method fill:#fff1cc,stroke:#c99a1a,color:#222,font-weight:bold
  classDef skill fill:#e3f4e6,stroke:#3f9a55,stroke-dasharray:5 3,color:#222
  classDef step fill:#ffffff,stroke:#999,color:#222
  classDef ans fill:#fde4e1,stroke:#c4554a,color:#222
  class n6 cls
  class n5 first
  class n2 method
  class n3,n4 step
  class n0,n1 ans
```


<a name="simplify-fraction"></a>

## Simplify a fraction

`simplify-fraction` · skill · prompt: *Simplify {x}/{y}.*

| Method | Idea | Steps use |
|---|---|---|
| **Divide by the GCF** `gcf` | Find the greatest common factor once and divide both terms by it. | — |
| **Divide out common factors repeatedly** `repeated` | Keep dividing both terms by any shared factor (2, 3, 5, …) until none is left. | — |

Reading the graphs: **hexagons** group first steps by operation · scope; **blue** = first step, **purple** = second step (only where methods share a first step); **yellow** = method; **green dashed** = a call to another question (see its own page); edge labels show which skill method produced the step.

### Simplify 6/8.

```mermaid
flowchart LR
  n0(["Simplify 6/8."])
  n1(["Answer: 3/4"])
  n2["Divide by the GCF"]
  n3["GCF(6, 8) = 2"]
  n2 --> n3
  n4["6 ÷ 2 = 3"]
  n3 --> n4
  n5["8 ÷ 2 = 4"]
  n4 --> n5
  n5 --> n1
  n6["Divide out common factors repeatedly"]
  n7["6 ÷ 2 = 3"]
  n6 --> n7
  n8["8 ÷ 2 = 4"]
  n7 --> n8
  n8 --> n1
  n9["6 ÷ 2 = 3"]
  n10{{"factor · within"}}
  n0 --> n10
  n10 --> n9
  n9 --> n6
  n11["GCF(6, 8) = 2"]
  n10 --> n11
  n11 --> n2
  classDef cls fill:#eef0f6,stroke:#8a90a6,color:#222
  classDef first fill:#e3edfd,stroke:#5b7fd1,color:#222
  classDef second fill:#efe6fb,stroke:#8b63c9,color:#222
  classDef method fill:#fff1cc,stroke:#c99a1a,color:#222,font-weight:bold
  classDef skill fill:#e3f4e6,stroke:#3f9a55,stroke-dasharray:5 3,color:#222
  classDef step fill:#ffffff,stroke:#999,color:#222
  classDef ans fill:#fde4e1,stroke:#c4554a,color:#222
  class n10 cls
  class n9,n11 first
  class n2,n6 method
  class n3,n4,n5,n7,n8 step
  class n0,n1 ans
```

### Simplify 72/96.

```mermaid
flowchart LR
  n0(["Simplify 72/96."])
  n1(["Answer: 3/4"])
  n2["Divide by the GCF"]
  n3["GCF(72, 96) = 24"]
  n2 --> n3
  n4["72 ÷ 24 = 3"]
  n3 --> n4
  n5["96 ÷ 24 = 4"]
  n4 --> n5
  n5 --> n1
  n6["Divide out common factors repeatedly"]
  n7["72 ÷ 2 = 36"]
  n6 --> n7
  n8["96 ÷ 2 = 48"]
  n7 --> n8
  n9["36 ÷ 2 = 18"]
  n8 --> n9
  n10["48 ÷ 2 = 24"]
  n9 --> n10
  n11["18 ÷ 2 = 9"]
  n10 --> n11
  n12["24 ÷ 2 = 12"]
  n11 --> n12
  n13["9 ÷ 3 = 3"]
  n12 --> n13
  n14["12 ÷ 3 = 4"]
  n13 --> n14
  n14 --> n1
  n15["72 ÷ 2 = 36"]
  n16{{"factor · within"}}
  n0 --> n16
  n16 --> n15
  n15 --> n6
  n17["GCF(72, 96) = 24"]
  n16 --> n17
  n17 --> n2
  classDef cls fill:#eef0f6,stroke:#8a90a6,color:#222
  classDef first fill:#e3edfd,stroke:#5b7fd1,color:#222
  classDef second fill:#efe6fb,stroke:#8b63c9,color:#222
  classDef method fill:#fff1cc,stroke:#c99a1a,color:#222,font-weight:bold
  classDef skill fill:#e3f4e6,stroke:#3f9a55,stroke-dasharray:5 3,color:#222
  classDef step fill:#ffffff,stroke:#999,color:#222
  classDef ans fill:#fde4e1,stroke:#c4554a,color:#222
  class n16 cls
  class n15,n17 first
  class n2,n6 method
  class n3,n4,n5,n7,n8,n9,n10,n11,n12,n13,n14 step
  class n0,n1 ans
```


<a name="to-decimal"></a>

## Write a fraction as a decimal

`to-decimal` · skill · prompt: *Write {x}/{y} as a decimal.*

| Method | Idea | Steps use |
|---|---|---|
| **Divide** `divide` | Divide the numerator by the denominator (long division or a calculator). | — |
| **Scale to 10, 100, 1000** `power_of_ten` | Multiply top and bottom so the denominator becomes 10, 100, or 1000, then read off the decimal. | — |

Reading the graphs: **hexagons** group first steps by operation · scope; **blue** = first step, **purple** = second step (only where methods share a first step); **yellow** = method; **green dashed** = a call to another question (see its own page); edge labels show which skill method produced the step.

### Write 3/4 as a decimal.

```mermaid
flowchart LR
  n0(["Write 3/4 as a decimal."])
  n1(["Answer: 0.75"])
  n2["Divide"]
  n3["3 ÷ 4 = 0.75"]
  n2 --> n3
  n3 --> n1
  n4["Scale to 10, 100, 1000"]
  n5["4 × 25 = 100"]
  n4 --> n5
  n6["3 × 25 = 75"]
  n5 --> n6
  n7["75 ÷ 100 = 0.75"]
  n6 --> n7
  n7 --> n1
  n8["3 ÷ 4 = 0.75"]
  n9{{"divide · within"}}
  n0 --> n9
  n9 --> n8
  n8 --> n2
  n10["4 × 25 = 100"]
  n11{{"multiply · within"}}
  n0 --> n11
  n11 --> n10
  n10 --> n4
  classDef cls fill:#eef0f6,stroke:#8a90a6,color:#222
  classDef first fill:#e3edfd,stroke:#5b7fd1,color:#222
  classDef second fill:#efe6fb,stroke:#8b63c9,color:#222
  classDef method fill:#fff1cc,stroke:#c99a1a,color:#222,font-weight:bold
  classDef skill fill:#e3f4e6,stroke:#3f9a55,stroke-dasharray:5 3,color:#222
  classDef step fill:#ffffff,stroke:#999,color:#222
  classDef ans fill:#fde4e1,stroke:#c4554a,color:#222
  class n9,n11 cls
  class n8,n10 first
  class n2,n4 method
  class n3,n5,n6,n7 step
  class n0,n1 ans
```

### Write 5/8 as a decimal.

```mermaid
flowchart LR
  n0(["Write 5/8 as a decimal."])
  n1(["Answer: 0.625"])
  n2["Divide"]
  n3["5 ÷ 8 = 0.625"]
  n2 --> n3
  n3 --> n1
  n4["Scale to 10, 100, 1000"]
  n5["8 × 125 = 1000"]
  n4 --> n5
  n6["5 × 125 = 625"]
  n5 --> n6
  n7["625 ÷ 1000 = 0.625"]
  n6 --> n7
  n7 --> n1
  n8["5 ÷ 8 = 0.625"]
  n9{{"divide · within"}}
  n0 --> n9
  n9 --> n8
  n8 --> n2
  n10["8 × 125 = 1000"]
  n11{{"multiply · within"}}
  n0 --> n11
  n11 --> n10
  n10 --> n4
  classDef cls fill:#eef0f6,stroke:#8a90a6,color:#222
  classDef first fill:#e3edfd,stroke:#5b7fd1,color:#222
  classDef second fill:#efe6fb,stroke:#8b63c9,color:#222
  classDef method fill:#fff1cc,stroke:#c99a1a,color:#222,font-weight:bold
  classDef skill fill:#e3f4e6,stroke:#3f9a55,stroke-dasharray:5 3,color:#222
  classDef step fill:#ffffff,stroke:#999,color:#222
  classDef ans fill:#fde4e1,stroke:#c4554a,color:#222
  class n9,n11 cls
  class n8,n10 first
  class n2,n4 method
  class n3,n5,n6,n7 step
  class n0,n1 ans
```


## Word problems

A word problem needs **extraction** before any method applies: pull out the quantities, drop the distractors, pair the right numbers in the right order, and recognize which question the story is. Each problem below maps to one of the questions above; its **traps** are common wrong extractions, written as alternative mappings so the wrong answer each one produces is computed, not guessed. That lets an app diagnose an extraction mistake from a student's answer, and often from their first step.

### Extraction concepts

| Concept | What the student does | Cues | Typical mistake |
|---|---|---|---|
| **Recognize the question type** `question_type` | Decide which question the story is: missing value, compare, better buy, proportion check, percent of, add fractions. | at the same rate / speed; how many … for …; which is the better buy / deal; who is better / sweeter / faster; same taste / shade; % of, % off, tip, tax; in all, altogether (with fractions) | Solving a different question than the one asked (sale price instead of savings). |
| **Pull out each quantity** `quantity` | Write each number with its unit and what it counts: 4 spoons (of sugar), 6 glasses (of lemonade). | — | Keeping the number but losing what it counts, so it gets used in the wrong place. |
| **Spot numbers written as words** `implicit_number` | Turn words into numbers. | a dozen = 12; a pair = 2; half = 1/2; twice = 2 ×; a quarter = 1/4; a / an / each = 1 | Reading '2 dozen' as 2. |
| **Make units match** `unit_conversion` | Convert so both sides of a ratio use the same units. | minutes ↔ hours; cents ↔ dollars; inches ↔ feet | Mixing hours on one side with minutes on the other. |
| **Find the pair that forms the ratio** `rate_pair` | Identify which two quantities belong together. | per; for every; each; to make; out of; for; stands for; in (150 miles in 3 hours) | Pairing the wrong two numbers. |
| **Keep the same order on both sides** `correspondence` | If the known ratio is sugar : lemonade, the unknown ratio must be sugar : lemonade too. | — | Flipping one side: 4/6 = 18/x instead of 4/6 = x/18. |
| **Ignore numbers that don't matter** `distractor` | Recognize numbers the question doesn't need. | — | Using a distractor in place of a real quantity. |
| **Name the unknown** `unknown` | Say what's asked for and in what unit, before computing. | — | Computing a related number that isn't the one asked for. |
| **'More' vs 'in all'** `delta_vs_total` | Decide whether a number is an increase or a new total, and whether the answer should be. | more; additional; another; in all; altogether; total; already; left | Answering the total when the extra amount was asked for, or the reverse. |
| **Scale, don't add** `multiplicative` | Proportional quantities grow by the same factor, not by the same amount. | — | '18 more glasses, so 18 more spoons.' |
| **Which way wins** `direction` | In a comparison, decide whether the bigger or smaller ratio is better, and which ratio (sugar per glass, or glasses per spoon) the story is about. | cheaper; sweeter; better rate; faster; stronger | Picking the bigger number when the smaller one wins, or comparing the flipped ratio. |
| **Finish the story** `follow_up` | A step after the core computation: subtract what's already used, find the price after a discount. | — | Stopping after the core computation. |
| **Answer in the story's terms** `answer_in_context` | Name the person or offer, give units, write 19/12 as 1 7/12. | — | Answering 'first' or a bare number. |

| Word problem | Maps to | Concepts |
|---|---|---|
| [Cereal boxes](#cereal-boxes) | [better-buy](#better-buy) | Recognize the question type, Find the pair that forms the ratio, Which way wins, Ignore numbers that don't matter, Answer in the story's terms |
| [Free throws](#free-throws) | [compare-fractions](#compare-fractions) | Find the pair that forms the ratio, Which way wins, Answer in the story's terms |
| [Jacket on sale](#jacket-sale) | [percent-of](#percent-of) | Recognize the question type, Name the unknown, Finish the story |
| [Lemonade: how many in all](#lemonade-in-all) | [missing-value](#missing-value) | 'More' vs 'in all', Finish the story, Find the pair that forms the ratio, Scale, don't add |
| [Lemonade: more sugar](#lemonade-more-sugar) | [missing-value](#missing-value) | Recognize the question type, Pull out each quantity, Find the pair that forms the ratio, Keep the same order on both sides, Ignore numbers that don't matter, 'More' vs 'in all', Scale, don't add, Name the unknown |
| [Map scale](#map-scale) | [missing-value](#missing-value) | Find the pair that forms the ratio, Keep the same order on both sides, Spot numbers written as words |
| [Same shade of paint?](#paint-shade) | [proportion-check](#proportion-check) | Recognize the question type, Find the pair that forms the ratio, Scale, don't add, Answer in the story's terms |
| [Pancakes by the dozen](#pancakes-dozen) | [missing-value](#missing-value) | Spot numbers written as words, Ignore numbers that don't matter, Find the pair that forms the ratio, Keep the same order on both sides |
| [Sharing pizza](#pizza-shared) | [add-fractions](#add-fractions) | Recognize the question type, Pull out each quantity, Answer in the story's terms |
| [Whose lemonade is sweeter?](#sweeter-lemonade) | [compare-fractions](#compare-fractions) | Recognize the question type, Find the pair that forms the ratio, Which way wins, Scale, don't add, Answer in the story's terms |
| [Train in minutes](#train-minutes) | [missing-value](#missing-value) | Make units match, Find the pair that forms the ratio, Recognize the question type |
| [Walking to school](#walk-to-school) | [percent-of](#percent-of) | Recognize the question type, Ignore numbers that don't matter |

<a name="cereal-boxes"></a>

### Cereal boxes

> A 12-ounce box of cereal costs $3.00 and a 20-ounce box costs $4.50. The store is 2 miles from home. Which box is the better buy?

| Phrase | Value | Counts | Role |
|---|---|---|---|
| “a 12-ounce box” | 12 | cereal in the small box | used |
| “costs $3.00” | 3.00 | price of the small box | used |
| “a 20-ounce box” | 20 | cereal in the big box | used |
| “costs $4.50” | 4.50 | price of the big box | used |
| “2 miles from home” | 2 | distance to the store | distractor |

**Asked:** which box is the better buy (box). **Link:** “box … costs”: Each box pairs ounces with dollars; compare dollars per ounce, and the smaller wins.

**Maps to** [better-buy](#better-buy): q1 = 12, p1 = 3, q2 = 20, p2 = 4.5. **Answer:** the 20-ounce box ($0.225 per ounce vs $0.25).

```mermaid
flowchart LR
  w0(["Cereal boxes"])
  w1["Which is the better buy?: Offer 1: 12 units for $3. Offer 2: 20 units for $4.5. Which is the better buy?"]
  w2["a 12-ounce box"]
  w0 --> w2
  w2 -->|"q1"| w1
  w3["costs $3.00"]
  w0 --> w3
  w3 -->|"p1"| w1
  w4["a 20-ounce box"]
  w0 --> w4
  w4 -->|"q2"| w1
  w5["costs $4.50"]
  w0 --> w5
  w5 -->|"p2"| w1
  w6["2 miles from home (not needed)"]
  w0 --> w6
  w7(["Answer: the 20-ounce box ($0.225 per ounce vs $0.25)"])
  w1 --> w7
  w8["Compares prices only and picks the cheaper box. → the 12-ounce box"]
  w0 -.->|"Find the pair that forms the ratio"| w8
  w9["Finds ounces per dollar but picks the smaller one. → the 12-ounce box"]
  w0 -.->|"Which way wins"| w9
  classDef story fill:#fde4e1,stroke:#c4554a,color:#222
  classDef used fill:#e3edfd,stroke:#5b7fd1,color:#222
  classDef distractor fill:#f2f2f2,stroke:#999,stroke-dasharray:4 3,color:#777
  classDef question fill:#fff1cc,stroke:#c99a1a,color:#222,font-weight:bold
  classDef step fill:#ffffff,stroke:#999,color:#222
  classDef ans fill:#e3f4e6,stroke:#3f9a55,color:#222
  classDef trap fill:#fff,stroke:#c4554a,stroke-dasharray:5 3,color:#a33
  class w0 story
  class w2,w3,w4,w5 used
  class w6 distractor
  class w1 question
  class w7 ans
  class w8,w9 trap
```

| Trap | Mistake | Gives | Caught by the answer? |
|---|---|---|---|
| Find the pair that forms the ratio | Compares prices only and picks the cheaper box. | the 12-ounce box | yes |
| Which way wins | Finds ounces per dollar but picks the smaller one. | the 12-ounce box | yes |

<a name="free-throws"></a>

### Free throws

> Maya made 3 of her 4 free throws. Leo made 5 of his 7. Who has the better shooting rate?

| Phrase | Value | Counts | Role |
|---|---|---|---|
| “made 3” | 3 | Maya's made shots | used |
| “of her 4” | 4 | Maya's attempts | used |
| “made 5” | 5 | Leo's made shots | used |
| “of his 7” | 7 | Leo's attempts | used |

**Asked:** who has the better shooting rate (name). **Link:** “made … of”: Made out of attempted; the bigger fraction wins.

**Maps to** [compare-fractions](#compare-fractions): a = 3, b = 4, c = 5, d = 7. **Answer:** Maya (3/4 = 0.75 vs 5/7 ≈ 0.714).

```mermaid
flowchart LR
  w0(["Free throws"])
  w1["Compare two fractions: Which is larger: 3/4 or 5/7? (Or are they equal?)"]
  w2["made 3"]
  w0 --> w2
  w2 -->|"a"| w1
  w3["of her 4"]
  w0 --> w3
  w3 -->|"b"| w1
  w4["made 5"]
  w0 --> w4
  w4 -->|"c"| w1
  w5["of his 7"]
  w0 --> w5
  w5 -->|"d"| w1
  w6(["Answer: Maya (3/4 = 0.75 vs 5/7 ≈ 0.714)"])
  w1 --> w6
  w7["Compares shots made only (5 #gt; 3). → Leo"]
  w0 -.->|"Find the pair that forms the ratio"| w7
  w8["Compares misses per shot and picks the bigger. → Leo"]
  w0 -.->|"Which way wins"| w8
  classDef story fill:#fde4e1,stroke:#c4554a,color:#222
  classDef used fill:#e3edfd,stroke:#5b7fd1,color:#222
  classDef distractor fill:#f2f2f2,stroke:#999,stroke-dasharray:4 3,color:#777
  classDef question fill:#fff1cc,stroke:#c99a1a,color:#222,font-weight:bold
  classDef step fill:#ffffff,stroke:#999,color:#222
  classDef ans fill:#e3f4e6,stroke:#3f9a55,color:#222
  classDef trap fill:#fff,stroke:#c4554a,stroke-dasharray:5 3,color:#a33
  class w0 story
  class w2,w3,w4,w5 used
  class w1 question
  class w6 ans
  class w7,w8 trap
```

| Trap | Mistake | Gives | Caught by the answer? |
|---|---|---|---|
| Find the pair that forms the ratio | Compares shots made only (5 > 3). | Leo | yes |
| Which way wins | Compares misses per shot and picks the bigger. | Leo | yes |

First steps that give a trap away (each method's main route under the wrong reading; no correct route starts this way). Traps that just compare raw counts are caught by the answer instead.

| Student's first step | Suggests |
|---|---|
| `1 × 2 = 2` | Compares misses per shot and picks the bigger. |
| `1 × 7 = 7` | Compares misses per shot and picks the bigger. |
| `1 ÷ 4 = 0.25` | Compares misses per shot and picks the bigger. |
| `2 ÷ 1 = 2` | Compares misses per shot and picks the bigger. |
| `4 ÷ 1 = 4` | Compares misses per shot and picks the bigger. |
| `4 − 1 = 3` | Compares misses per shot and picks the bigger. |
| `GCF(1, 4) = 1` | Compares misses per shot and picks the bigger. |
| `LCM(1, 2) = 2` | Compares misses per shot and picks the bigger. |
| `plot (1, 4), (2, 7)` | Compares misses per shot and picks the bigger. |

<a name="jacket-sale"></a>

### Jacket on sale

> A jacket normally costs $80. This week it is 15% off. How much does the jacket cost this week?

| Phrase | Value | Counts | Role |
|---|---|---|---|
| “costs $80” | 80 | original price | used |
| “15% off” | 15 | discount | used |

**Asked:** how much does it cost this week (dollars). **Link:** “% off”: 15% of the original price is taken off.

**Maps to** [percent-of](#percent-of): p = 15, n = 80, then subtract the savings from the original price. **Answer:** $68.

```mermaid
flowchart LR
  w0(["Jacket on sale"])
  w1["Find a percent of a number: What is 15% of 80?"]
  w2["costs $80"]
  w0 --> w2
  w2 -->|"n"| w1
  w3["15% off"]
  w0 --> w3
  w3 -->|"p"| w1
  w4["result 12"]
  w1 --> w4
  w5["subtract the savings from the original price"]
  w4 --> w5
  w6(["Answer: $68"])
  w5 --> w6
  w7["Answers the savings instead of the new price. → 12"]
  w0 -.->|"Name the unknown"| w7
  w8["Takes off $15 instead of 15%. → 65"]
  w0 -.->|"Recognize the question type"| w8
  classDef story fill:#fde4e1,stroke:#c4554a,color:#222
  classDef used fill:#e3edfd,stroke:#5b7fd1,color:#222
  classDef distractor fill:#f2f2f2,stroke:#999,stroke-dasharray:4 3,color:#777
  classDef question fill:#fff1cc,stroke:#c99a1a,color:#222,font-weight:bold
  classDef step fill:#ffffff,stroke:#999,color:#222
  classDef ans fill:#e3f4e6,stroke:#3f9a55,color:#222
  classDef trap fill:#fff,stroke:#c4554a,stroke-dasharray:5 3,color:#a33
  class w0 story
  class w2,w3 used
  class w1 question
  class w4,w5 step
  class w6 ans
  class w7,w8 trap
```

| Trap | Mistake | Gives | Caught by the answer? |
|---|---|---|---|
| Name the unknown | Answers the savings instead of the new price. | 12 | yes |
| Recognize the question type | Takes off $15 instead of 15%. | 65 | yes |

<a name="lemonade-in-all"></a>

### Lemonade: how many in all

> Joe used 4 spoons of sugar to make the first 6 glasses of lemonade. He wants 18 glasses in all. How many more spoons of sugar does he need?

| Phrase | Value | Counts | Role |
|---|---|---|---|
| “4 spoons of sugar” | 4 | sugar already used | used |
| “the first 6 glasses” | 6 | lemonade made | used |
| “18 glasses in all” | 18 | lemonade wanted in total | used |

**Asked:** how many more spoons (spoons). **Link:** “to make”: 4 spoons per 6 glasses; 18 is a total, so the answer is total sugar minus sugar already used.

**Maps to** [missing-value](#missing-value): a = 4, b = 6, d = 18, then subtract the sugar already used. **Answer:** 8 more spoons of sugar.

```mermaid
flowchart LR
  w0(["Lemonade: how many in all"])
  w1["Find the missing value in a proportion: Solve 4/6 = x/18"]
  w2["4 spoons of sugar"]
  w0 --> w2
  w2 -->|"a"| w1
  w3["the first 6 glasses"]
  w0 --> w3
  w3 -->|"b"| w1
  w4["18 glasses in all"]
  w0 --> w4
  w4 -->|"d"| w1
  w5["result 12"]
  w1 --> w5
  w6["subtract the sugar already used"]
  w5 --> w6
  w7(["Answer: 8 more spoons of sugar"])
  w6 --> w7
  w8["Stops at the sugar for all 18 glasses. → 12"]
  w0 -.->|"Finish the story"| w8
  w9["Reads 18 as 18 more glasses. → 12"]
  w0 -.->|"'More' vs 'in all'"| w9
  w10["Adds instead of scaling: 12 more glasses, so 12 more spoons. → 12"]
  w0 -.->|"Scale, don't add"| w10
  classDef story fill:#fde4e1,stroke:#c4554a,color:#222
  classDef used fill:#e3edfd,stroke:#5b7fd1,color:#222
  classDef distractor fill:#f2f2f2,stroke:#999,stroke-dasharray:4 3,color:#777
  classDef question fill:#fff1cc,stroke:#c99a1a,color:#222,font-weight:bold
  classDef step fill:#ffffff,stroke:#999,color:#222
  classDef ans fill:#e3f4e6,stroke:#3f9a55,color:#222
  classDef trap fill:#fff,stroke:#c4554a,stroke-dasharray:5 3,color:#a33
  class w0 story
  class w2,w3,w4 used
  class w1 question
  class w5,w6 step
  class w7 ans
  class w8,w9,w10 trap
```

| Trap | Mistake | Gives | Caught by the answer? |
|---|---|---|---|
| Finish the story | Stops at the sugar for all 18 glasses. | 12 | yes |
| 'More' vs 'in all' | Reads 18 as 18 more glasses. | 12 | yes |
| Scale, don't add | Adds instead of scaling: 12 more glasses, so 12 more spoons. | 12 | yes |

<a name="lemonade-more-sugar"></a>

### Lemonade: more sugar

> Joe is having a party. He has 6 cups of water and 4 spoons of sugar, which make 6 glasses of lemonade. He needs 18 more glasses of lemonade. How many more spoons of sugar does he need?

| Phrase | Value | Counts | Role |
|---|---|---|---|
| “6 cups of water” | 6 | water | distractor |
| “4 spoons of sugar” | 4 | sugar | used |
| “6 glasses of lemonade” | 6 | lemonade | used |
| “18 more glasses” | 18 | extra lemonade | used |

**Asked:** how many more spoons of sugar (spoons). **Link:** “which make”: 4 spoons of sugar go with 6 glasses; the water is a distractor for a question about sugar.

**Maps to** [missing-value](#missing-value): a = 4, b = 6, d = 18. **Answer:** 12 more spoons of sugar.

```mermaid
flowchart LR
  w0(["Lemonade: more sugar"])
  w1["Find the missing value in a proportion: Solve 4/6 = x/18"]
  w2["6 cups of water (not needed)"]
  w0 --> w2
  w3["4 spoons of sugar"]
  w0 --> w3
  w3 -->|"a"| w1
  w4["6 glasses of lemonade"]
  w0 --> w4
  w4 -->|"b"| w1
  w5["18 more glasses"]
  w0 --> w5
  w5 -->|"d"| w1
  w6(["Answer: 12 more spoons of sugar"])
  w1 --> w6
  w7["Finds the sugar for all 24 glasses instead of the 18 extra. → 16"]
  w0 -.->|"'More' vs 'in all'"| w7
  w8["Reads 18 as the new total and subtracts the 4 spoons already used. → 8"]
  w0 -.->|"'More' vs 'in all'"| w8
  w9["Flips one side: glasses over sugar = x over glasses. → 27"]
  w0 -.->|"Keep the same order on both sides"| w9
  w10["Pairs sugar with the 6 cups of water instead of the 6 glasses. → 12  (same answer!)"]
  w0 -.->|"Ignore numbers that don't matter"| w10
  w11["Adds instead of scaling: 18 more glasses, so 18 more spoons. → 18"]
  w0 -.->|"Scale, don't add"| w11
  classDef story fill:#fde4e1,stroke:#c4554a,color:#222
  classDef used fill:#e3edfd,stroke:#5b7fd1,color:#222
  classDef distractor fill:#f2f2f2,stroke:#999,stroke-dasharray:4 3,color:#777
  classDef question fill:#fff1cc,stroke:#c99a1a,color:#222,font-weight:bold
  classDef step fill:#ffffff,stroke:#999,color:#222
  classDef ans fill:#e3f4e6,stroke:#3f9a55,color:#222
  classDef trap fill:#fff,stroke:#c4554a,stroke-dasharray:5 3,color:#a33
  class w0 story
  class w3,w4,w5 used
  class w2 distractor
  class w1 question
  class w6 ans
  class w7,w8,w9,w10,w11 trap
```

| Trap | Mistake | Gives | Caught by the answer? |
|---|---|---|---|
| 'More' vs 'in all' | Finds the sugar for all 24 glasses instead of the 18 extra. | 16 | yes |
| 'More' vs 'in all' | Reads 18 as the new total and subtracts the 4 spoons already used. | 8 | yes |
| Keep the same order on both sides | Flips one side: glasses over sugar = x over glasses. | 27 | yes |
| Ignore numbers that don't matter | Pairs sugar with the 6 cups of water instead of the 6 glasses. | 12 | **no**: same answer, so ask how they got it |
| Scale, don't add | Adds instead of scaling: 18 more glasses, so 18 more spoons. | 18 | yes |

First steps that give a trap away (each method's main route under the wrong reading; no correct route starts this way). Traps that just compare raw counts are caught by the answer instead.

| Student's first step | Suggests |
|---|---|
| `18 ÷ 4 = 4.5` | Flips one side: glasses over sugar = x over glasses. |
| `24 ÷ 6 = 4` | Finds the sugar for all 24 glasses instead of the 18 extra. |
| `4 × 24 = 96` | Finds the sugar for all 24 glasses instead of the 18 extra. |
| `6 × 18 = 108` | Flips one side: glasses over sugar = x over glasses. |
| `6 × 4 = 24` | Finds the sugar for all 24 glasses instead of the 18 extra. |

<a name="map-scale"></a>

### Map scale

> On a map, 1 inch stands for 25 miles. Two towns are 3.5 inches apart on the map. How far apart are they really?

| Phrase | Value | Counts | Role |
|---|---|---|---|
| “1 inch” | 1 | map distance | used |
| “25 miles” | 25 | real distance | used |
| “3.5 inches apart” | 3.5 | map distance between the towns | used |

**Asked:** how far apart really (miles). **Link:** “stands for”: 25 real miles per 1 map inch.

**Maps to** [missing-value](#missing-value): a = 25, b = 1, d = 3.5. **Answer:** 87.5 miles.

```mermaid
flowchart LR
  w0(["Map scale"])
  w1["Find the missing value in a proportion: Solve 25/1 = x/3.5"]
  w2["1 inch"]
  w0 --> w2
  w2 -->|"b"| w1
  w3["25 miles"]
  w0 --> w3
  w3 -->|"a"| w1
  w4["3.5 inches apart"]
  w0 --> w4
  w4 -->|"d"| w1
  w5(["Answer: 87.5 miles"])
  w1 --> w5
  w6["Flips one side: inches over miles. → 0.14"]
  w0 -.->|"Keep the same order on both sides"| w6
  w7["Divides the scale by the map distance. → 50/7"]
  w0 -.->|"Find the pair that forms the ratio"| w7
  classDef story fill:#fde4e1,stroke:#c4554a,color:#222
  classDef used fill:#e3edfd,stroke:#5b7fd1,color:#222
  classDef distractor fill:#f2f2f2,stroke:#999,stroke-dasharray:4 3,color:#777
  classDef question fill:#fff1cc,stroke:#c99a1a,color:#222,font-weight:bold
  classDef step fill:#ffffff,stroke:#999,color:#222
  classDef ans fill:#e3f4e6,stroke:#3f9a55,color:#222
  classDef trap fill:#fff,stroke:#c4554a,stroke-dasharray:5 3,color:#a33
  class w0 story
  class w2,w3,w4 used
  class w1 question
  class w5 ans
  class w6,w7 trap
```

| Trap | Mistake | Gives | Caught by the answer? |
|---|---|---|---|
| Keep the same order on both sides | Flips one side: inches over miles. | 0.14 | yes |
| Find the pair that forms the ratio | Divides the scale by the map distance. | 50/7 | yes |

First steps that give a trap away (each method's main route under the wrong reading; no correct route starts this way). Traps that just compare raw counts are caught by the answer instead.

| Student's first step | Suggests |
|---|---|
| `1 × 3.5 = 3.5` | Flips one side: inches over miles. |
| `3.5 ÷ 25 = 0.14` | Flips one side: inches over miles. |

<a name="paint-shade"></a>

### Same shade of paint?

> Paint A mixes 6 cans of blue with 8 cans of white. Paint B mixes 72 cans of blue with 96 cans of white. Will the two paints be the same shade?

| Phrase | Value | Counts | Role |
|---|---|---|---|
| “6 cans of blue” | 6 | blue in A | used |
| “8 cans of white” | 8 | white in A | used |
| “72 cans of blue” | 72 | blue in B | used |
| “96 cans of white” | 96 | white in B | used |

**Asked:** same shade? (yes/no). **Link:** “mixes … with”: Same shade means the same blue : white ratio.

**Maps to** [proportion-check](#proportion-check): a = 6, b = 8, c = 72, d = 96. **Answer:** Yes: both are 3 blue to 4 white.

```mermaid
flowchart LR
  w0(["Same shade of paint?"])
  w1["Are two ratios proportional?: Are 6:8 and 72:96 proportional?"]
  w2["6 cans of blue"]
  w0 --> w2
  w2 -->|"a"| w1
  w3["8 cans of white"]
  w0 --> w3
  w3 -->|"b"| w1
  w4["72 cans of blue"]
  w0 --> w4
  w4 -->|"c"| w1
  w5["96 cans of white"]
  w0 --> w5
  w5 -->|"d"| w1
  w6(["Answer: Yes: both are 3 blue to 4 white"])
  w1 --> w6
  w7["Compares the differences (2 more white vs 24 more white). → no"]
  w0 -.->|"Scale, don't add"| w7
  classDef story fill:#fde4e1,stroke:#c4554a,color:#222
  classDef used fill:#e3edfd,stroke:#5b7fd1,color:#222
  classDef distractor fill:#f2f2f2,stroke:#999,stroke-dasharray:4 3,color:#777
  classDef question fill:#fff1cc,stroke:#c99a1a,color:#222,font-weight:bold
  classDef step fill:#ffffff,stroke:#999,color:#222
  classDef ans fill:#e3f4e6,stroke:#3f9a55,color:#222
  classDef trap fill:#fff,stroke:#c4554a,stroke-dasharray:5 3,color:#a33
  class w0 story
  class w2,w3,w4,w5 used
  class w1 question
  class w6 ans
  class w7 trap
```

| Trap | Mistake | Gives | Caught by the answer? |
|---|---|---|---|
| Scale, don't add | Compares the differences (2 more white vs 24 more white). | no | yes |

<a name="pancakes-dozen"></a>

### Pancakes by the dozen

> A pancake recipe uses 2 cups of flour and 3 eggs to make 12 pancakes. How many cups of flour are needed for 2 dozen pancakes?

| Phrase | Value | Counts | Role |
|---|---|---|---|
| “2 cups of flour” | 2 | flour | used |
| “3 eggs” | 3 | eggs | distractor |
| “12 pancakes” | 12 | pancakes | used |
| “2 dozen pancakes” | 2 dozen → **24** | pancakes wanted | used |

**Asked:** how many cups of flour (cups). **Link:** “to make”: 2 cups of flour per 12 pancakes.

**Maps to** [missing-value](#missing-value): a = 2, b = 12, d = 24. **Answer:** 4 cups of flour.

```mermaid
flowchart LR
  w0(["Pancakes by the dozen"])
  w1["Find the missing value in a proportion: Solve 2/12 = x/24"]
  w2["2 cups of flour"]
  w0 --> w2
  w2 -->|"a"| w1
  w3["3 eggs (not needed)"]
  w0 --> w3
  w4["12 pancakes"]
  w0 --> w4
  w4 -->|"b"| w1
  w5["2 dozen pancakes = 24 24"]
  w0 --> w5
  w5 -->|"d"| w1
  w6(["Answer: 4 cups of flour"])
  w1 --> w6
  w7["Reads '2 dozen' as 2 pancakes. → 1/3"]
  w0 -.->|"Spot numbers written as words"| w7
  w8["Scales the eggs instead of the flour. → 6"]
  w0 -.->|"Ignore numbers that don't matter"| w8
  w9["Flips one side: pancakes over flour. → 144"]
  w0 -.->|"Keep the same order on both sides"| w9
  classDef story fill:#fde4e1,stroke:#c4554a,color:#222
  classDef used fill:#e3edfd,stroke:#5b7fd1,color:#222
  classDef distractor fill:#f2f2f2,stroke:#999,stroke-dasharray:4 3,color:#777
  classDef question fill:#fff1cc,stroke:#c99a1a,color:#222,font-weight:bold
  classDef step fill:#ffffff,stroke:#999,color:#222
  classDef ans fill:#e3f4e6,stroke:#3f9a55,color:#222
  classDef trap fill:#fff,stroke:#c4554a,stroke-dasharray:5 3,color:#a33
  class w0 story
  class w2,w4,w5 used
  class w3 distractor
  class w1 question
  class w6 ans
  class w7,w8,w9 trap
```

| Trap | Mistake | Gives | Caught by the answer? |
|---|---|---|---|
| Spot numbers written as words | Reads '2 dozen' as 2 pancakes. | 1/3 | yes |
| Ignore numbers that don't matter | Scales the eggs instead of the flour. | 6 | yes |
| Keep the same order on both sides | Flips one side: pancakes over flour. | 144 | yes |

First steps that give a trap away (each method's main route under the wrong reading; no correct route starts this way). Traps that just compare raw counts are caught by the answer instead.

| Student's first step | Suggests |
|---|---|
| `12 × 24 = 288` | Flips one side: pancakes over flour. |
| `12 ÷ 3 = 4` | Scales the eggs instead of the flour. |
| `2 × 2 = 4` | Reads '2 dozen' as 2 pancakes. |
| `24 ÷ 2 = 12` | Flips one side: pancakes over flour. |
| `3 × 24 = 72` | Scales the eggs instead of the flour. |
| `3 ÷ 12 = 0.25` | Scales the eggs instead of the flour. |
| `GCF(3, 12) = 3` | Scales the eggs instead of the flour. |

<a name="pizza-shared"></a>

### Sharing pizza

> Sam ate 5/6 of a pizza and Kim ate 3/4 of a pizza. How much pizza did they eat in all?

| Phrase | Value | Counts | Role |
|---|---|---|---|
| “5/6 of a pizza” | 5/6 | Sam's share | used |
| “3/4 of a pizza” | 3/4 | Kim's share | used |

**Asked:** how much in all (pizzas). **Link:** “in all”: Add the two fractions.

**Maps to** [add-fractions](#add-fractions): a = 5, b = 6, c = 3, d = 4. **Answer:** 1 7/12 pizzas.

```mermaid
flowchart LR
  w0(["Sharing pizza"])
  w1["Add two fractions: Find 5/6 + 3/4"]
  w2["5/6 of a pizza"]
  w0 --> w2
  w2 -->|"a"| w1
  w3["3/4 of a pizza"]
  w0 --> w3
  w3 -->|"c"| w1
  w4(["Answer: 1 7/12 pizzas"])
  w1 --> w4
  w5["Adds tops and bottoms: (5 + 3)/(6 + 4). → 0.8"]
  w0 -.->|"Recognize the question type"| w5
  classDef story fill:#fde4e1,stroke:#c4554a,color:#222
  classDef used fill:#e3edfd,stroke:#5b7fd1,color:#222
  classDef distractor fill:#f2f2f2,stroke:#999,stroke-dasharray:4 3,color:#777
  classDef question fill:#fff1cc,stroke:#c99a1a,color:#222,font-weight:bold
  classDef step fill:#ffffff,stroke:#999,color:#222
  classDef ans fill:#e3f4e6,stroke:#3f9a55,color:#222
  classDef trap fill:#fff,stroke:#c4554a,stroke-dasharray:5 3,color:#a33
  class w0 story
  class w2,w3 used
  class w1 question
  class w4 ans
  class w5 trap
```

| Trap | Mistake | Gives | Caught by the answer? |
|---|---|---|---|
| Recognize the question type | Adds tops and bottoms: (5 + 3)/(6 + 4). | 0.8 | yes |

<a name="sweeter-lemonade"></a>

### Whose lemonade is sweeter?

> Joe mixes 4 spoons of sugar into 6 glasses of lemonade. Ann mixes 10 spoons of sugar into 14 glasses. Whose lemonade is sweeter?

| Phrase | Value | Counts | Role |
|---|---|---|---|
| “4 spoons of sugar” | 4 | Joe's sugar | used |
| “6 glasses” | 6 | Joe's lemonade | used |
| “10 spoons of sugar” | 10 | Ann's sugar | used |
| “14 glasses” | 14 | Ann's lemonade | used |

**Asked:** whose is sweeter (name). **Link:** “mixes … into”: Sweetness is sugar per glass; the bigger fraction is sweeter.

**Maps to** [compare-fractions](#compare-fractions): a = 4, b = 6, c = 10, d = 14. **Answer:** Ann's (10/14 ≈ 0.714 spoons per glass vs 4/6 ≈ 0.667).

```mermaid
flowchart LR
  w0(["Whose lemonade is sweeter?"])
  w1["Compare two fractions: Which is larger: 4/6 or 10/14? (Or are they equal?)"]
  w2["4 spoons of sugar"]
  w0 --> w2
  w2 -->|"a"| w1
  w3["6 glasses"]
  w0 --> w3
  w3 -->|"b"| w1
  w4["10 spoons of sugar"]
  w0 --> w4
  w4 -->|"c"| w1
  w5["14 glasses"]
  w0 --> w5
  w5 -->|"d"| w1
  w6(["Answer: Ann's (10/14 ≈ 0.714 spoons per glass vs 4/6 ≈ 0.667)"])
  w1 --> w6
  w7["Compares glasses per spoon and calls the bigger one sweeter. → Joe"]
  w0 -.->|"Which way wins"| w7
  w8["Compares spoons of sugar only (10 #gt; 4). → Ann  (same answer!)"]
  w0 -.->|"Find the pair that forms the ratio"| w8
  w9["Compares glasses minus spoons (2 vs 4) and calls the smaller gap sweeter. → Joe"]
  w0 -.->|"Scale, don't add"| w9
  classDef story fill:#fde4e1,stroke:#c4554a,color:#222
  classDef used fill:#e3edfd,stroke:#5b7fd1,color:#222
  classDef distractor fill:#f2f2f2,stroke:#999,stroke-dasharray:4 3,color:#777
  classDef question fill:#fff1cc,stroke:#c99a1a,color:#222,font-weight:bold
  classDef step fill:#ffffff,stroke:#999,color:#222
  classDef ans fill:#e3f4e6,stroke:#3f9a55,color:#222
  classDef trap fill:#fff,stroke:#c4554a,stroke-dasharray:5 3,color:#a33
  class w0 story
  class w2,w3,w4,w5 used
  class w1 question
  class w6 ans
  class w7,w8,w9 trap
```

| Trap | Mistake | Gives | Caught by the answer? |
|---|---|---|---|
| Which way wins | Compares glasses per spoon and calls the bigger one sweeter. | Joe | yes |
| Find the pair that forms the ratio | Compares spoons of sugar only (10 > 4). | Ann | **no**: same answer, so ask how they got it |
| Scale, don't add | Compares glasses minus spoons (2 vs 4) and calls the smaller gap sweeter. | Joe | yes |

First steps that give a trap away (each method's main route under the wrong reading; no correct route starts this way). Traps that just compare raw counts are caught by the answer instead.

| Student's first step | Suggests |
|---|---|
| `6 × 10 = 60` | Compares glasses per spoon and calls the bigger one sweeter. |
| `plot (6, 4), (14, 10)` | Compares glasses per spoon and calls the bigger one sweeter. |

<a name="train-minutes"></a>

### Train in minutes

> A train travels 150 miles in 3 hours. At the same speed, how far does it travel in 90 minutes?

| Phrase | Value | Counts | Role |
|---|---|---|---|
| “150 miles” | 150 | distance | used |
| “3 hours” | 3 | time | used |
| “90 minutes” | 90 minutes → **1.5** | new time | used |

**Asked:** how far (miles). **Link:** “in … at the same speed”: 150 miles per 3 hours; the time must be in hours on both sides.

**Maps to** [missing-value](#missing-value): a = 150, b = 3, d = 1.5. **Answer:** 75 miles.

```mermaid
flowchart LR
  w0(["Train in minutes"])
  w1["Find the missing value in a proportion: Solve 150/3 = x/1.5"]
  w2["150 miles"]
  w0 --> w2
  w2 -->|"a"| w1
  w3["3 hours"]
  w0 --> w3
  w3 -->|"b"| w1
  w4["90 minutes = 1.5 hours"]
  w0 --> w4
  w4 -->|"d"| w1
  w5(["Answer: 75 miles"])
  w1 --> w5
  w6["Uses 90 without converting minutes to hours. → 4500"]
  w0 -.->|"Make units match"| w6
  w7["Flips one side: hours over miles. → 0.03"]
  w0 -.->|"Keep the same order on both sides"| w7
  classDef story fill:#fde4e1,stroke:#c4554a,color:#222
  classDef used fill:#e3edfd,stroke:#5b7fd1,color:#222
  classDef distractor fill:#f2f2f2,stroke:#999,stroke-dasharray:4 3,color:#777
  classDef question fill:#fff1cc,stroke:#c99a1a,color:#222,font-weight:bold
  classDef step fill:#ffffff,stroke:#999,color:#222
  classDef ans fill:#e3f4e6,stroke:#3f9a55,color:#222
  classDef trap fill:#fff,stroke:#c4554a,stroke-dasharray:5 3,color:#a33
  class w0 story
  class w2,w3,w4 used
  class w1 question
  class w5 ans
  class w6,w7 trap
```

| Trap | Mistake | Gives | Caught by the answer? |
|---|---|---|---|
| Make units match | Uses 90 without converting minutes to hours. | 4500 | yes |
| Keep the same order on both sides | Flips one side: hours over miles. | 0.03 | yes |

First steps that give a trap away (each method's main route under the wrong reading; no correct route starts this way). Traps that just compare raw counts are caught by the answer instead.

| Student's first step | Suggests |
|---|---|
| `1.5 ÷ 150 = 0.01` | Flips one side: hours over miles. |
| `150 × 90 = 13500` | Uses 90 without converting minutes to hours. |
| `3 × 1.5 = 4.5` | Flips one side: hours over miles. |
| `3 × 30 = 90` | Uses 90 without converting minutes to hours. |
| `90 ÷ 3 = 30` | Uses 90 without converting minutes to hours. |

<a name="walk-to-school"></a>

### Walking to school

> There are 60 students in a class. 35% of them walk to school, and 10 ride bikes. How many students walk to school?

| Phrase | Value | Counts | Role |
|---|---|---|---|
| “60 students” | 60 | the class | used |
| “35% of them walk” | 35 | walkers | used |
| “10 ride bikes” | 10 | bike riders | distractor |

**Asked:** how many students walk (students). **Link:** “% of them”: 'them' is the 60 students.

**Maps to** [percent-of](#percent-of): p = 35, n = 60. **Answer:** 21 students.

```mermaid
flowchart LR
  w0(["Walking to school"])
  w1["Find a percent of a number: What is 35% of 60?"]
  w2["60 students"]
  w0 --> w2
  w2 -->|"n"| w1
  w3["35% of them walk"]
  w0 --> w3
  w3 -->|"p"| w1
  w4["10 ride bikes (not needed)"]
  w0 --> w4
  w5(["Answer: 21 students"])
  w1 --> w5
  w6["Takes the 10 bike riders out of the class first. → 17.5"]
  w0 -.->|"Ignore numbers that don't matter"| w6
  w7["Takes 35% of the 10 bike riders. → 3.5"]
  w0 -.->|"Find the pair that forms the ratio"| w7
  classDef story fill:#fde4e1,stroke:#c4554a,color:#222
  classDef used fill:#e3edfd,stroke:#5b7fd1,color:#222
  classDef distractor fill:#f2f2f2,stroke:#999,stroke-dasharray:4 3,color:#777
  classDef question fill:#fff1cc,stroke:#c99a1a,color:#222,font-weight:bold
  classDef step fill:#ffffff,stroke:#999,color:#222
  classDef ans fill:#e3f4e6,stroke:#3f9a55,color:#222
  classDef trap fill:#fff,stroke:#c4554a,stroke-dasharray:5 3,color:#a33
  class w0 story
  class w2,w3 used
  class w4 distractor
  class w1 question
  class w5 ans
  class w6,w7 trap
```

| Trap | Mistake | Gives | Caught by the answer? |
|---|---|---|---|
| Ignore numbers that don't matter | Takes the 10 bike riders out of the class first. | 17.5 | yes |
| Find the pair that forms the ratio | Takes 35% of the 10 bike riders. | 3.5 | yes |

First steps that give a trap away (each method's main route under the wrong reading; no correct route starts this way). Traps that just compare raw counts are caught by the answer instead.

| Student's first step | Suggests |
|---|---|
| `10 ÷ 10 = 1` | Takes 35% of the 10 bike riders. |
| `10 ÷ 100 = 0.1` | Takes 35% of the 10 bike riders. |
| `35 × 10 = 350` | Takes 35% of the 10 bike riders. |
| `35 × 50 = 1750` | Takes the 10 bike riders out of the class first. |
| `50 ÷ 10 = 5` | Takes the 10 bike riders out of the class first. |
| `50 ÷ 100 = 0.5` | Takes the 10 bike riders out of the class first. |


## Rebuilding

```sh
cd v2 && python3 build.py --demo
```

This checks every method variant against every example, regenerates `v2/trees/`, `v2/graphs/` and this report, and runs the classifier on sample student steps.
