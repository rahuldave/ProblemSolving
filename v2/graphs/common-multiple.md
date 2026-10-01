# Find a common multiple

`common-multiple` · skill · prompt: *Find a common multiple of {x} and {y}.*

| Method | Idea | Steps use |
|---|---|---|
| **Know the LCM** `recall` | Recognize the least common multiple directly. | — |
| **List multiples** `list_multiples` | Count up by {x} until you reach a number {y} divides. | — |
| **Multiply them** `product` | {x} × {y} is always a common multiple. | — |
| **Use the GCF** `gcf_formula` | LCM = {x} ÷ GCF × {y}. | — |

Reading the graphs: **hexagons** group first steps by operation · scope; **blue** = first step, **purple** = second step (only where methods share a first step); **yellow** = method; **green dashed** = a call to another question (see its own page); edge labels show which skill method produced the step.

## Find a common multiple of 4 and 6.

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

## Find a common multiple of 4 and 7.

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
