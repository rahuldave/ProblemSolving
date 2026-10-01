# Find the missing value in a proportion

`missing-value` · core · prompt: *Solve {a}/{b} = x/{d}.*

Uses: [simplify-fraction](simplify-fraction.md), [to-decimal](to-decimal.md)

| Method | Idea | Steps use |
|---|---|---|
| **Cross-multiply and divide** `cross_multiply` | {a} × {d} = {b} × x, so x = {a} × {d} ÷ {b}. | — |
| **Scale factor** `scale_factor` | Find what turns {b} into {d}, then do the same to {a}. | — |
| **Unit rate** `unit_rate` | Find the value per 1, then scale up to {d}. | to-decimal |
| **Inverse rate** `inverse_rate` | Find how many of the second quantity per 1 of the first, then divide. | to-decimal |
| **Ratio table** `ratio_table` | Build {a}:{b} up by ×2, ×3, … until the second term reaches {d}. | — |
| **Simplify, then scale** `simplify_then_scale` | Reduce {a}/{b} first so a whole-number scale factor appears. | simplify-fraction |

Reading the graphs: **hexagons** group first steps by operation · scope; **blue** = first step, **purple** = second step (only where methods share a first step); **yellow** = method; **green dashed** = a call to another question (see its own page); edge labels show which skill method produced the step.

## Solve 3/5 = x/40.

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

## Solve 4/6 = x/15.

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
