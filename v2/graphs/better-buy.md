# Which is the better buy?

`better-buy` · applied · prompt: *Offer 1: {q1} units for ${p1}. Offer 2: {q2} units for ${p2}. Which is the better buy?*

Reduces to [compare-fractions](compare-fractions.md) with `{"a": "p1", "b": "q1", "c": "p2", "d": "q2"}`. Compare the prices per unit p1/q1 and p2/q2; the smaller one is the better buy, so 'first' (bigger) maps to 'second'.

| Method | Idea | Steps use |
|---|---|---|
| **Price per unit** `price_per_unit` (= compare-fractions · decimal) | Find the cost of 1 unit in each offer; lower is better. | — |
| **Units per dollar** `units_per_dollar` (= compare-fractions · unit_rate) | Find how much $1 buys; more is better. | — |
| **Common quantity** `common_quantity` (= compare-fractions · common_denominator) | Price both offers at the same quantity. | — |
| **Scale one offer to the other's size** `scale_up` (= compare-fractions · match_denominator) | What would offer 1 cost for {q2} units? | — |
| **Cross-multiply** `cross_multiply` (= compare-fractions · cross_multiply) | {a}/{b} > {c}/{d} exactly when {a}×{d} > {c}×{b}. | — |
| **Compare growth** `compare_growth` (= compare-fractions · scale_factor) | Price grows by {p2} ÷ {p1}, quantity by {q2} ÷ {q1}; quantity growing faster means offer 2 is better. | — |

Reading the graphs: **hexagons** group first steps by operation · scope; **blue** = first step, **purple** = second step (only where methods share a first step); **yellow** = method; **green dashed** = a call to another question (see its own page); edge labels show which skill method produced the step.

## Offer 1: 12 units for $3. Offer 2: 20 units for $4.5. Which is the better buy?

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

## Offer 1: 6 units for $4.2. Offer 2: 10 units for $7.5. Which is the better buy?

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
