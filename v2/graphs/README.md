# Question graphs (v2)

How the questions reuse each other. Green = skill, yellow = core, blue = applied. Solid arrows: a method calls that question as a step. Dotted arrows: the applied question *is* the core question in context. (compare-fractions also calls itself: *distance from 1* ends by comparing the two gaps.)

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
| [Add two fractions](add-fractions.md) | core | 3 | common-multiple, cross-products, missing-value, simplify-fraction, to-decimal |
| [Which is the better buy?](better-buy.md) | applied | 6 | compare-fractions |
| [Find a common multiple](common-multiple.md) | skill | 4 | — |
| [Compare two fractions](compare-fractions.md) | core | 11 | common-multiple, compare-fractions, cross-products, missing-value, simplify-fraction, to-decimal |
| [Cross products](cross-products.md) | skill | 1 | — |
| [Find the missing value in a proportion](missing-value.md) | core | 6 | simplify-fraction, to-decimal |
| [Find a percent of a number](percent-of.md) | applied | 6 | missing-value |
| [Are two ratios proportional?](proportion-check.md) | applied | 11 | compare-fractions |
| [Simplify a fraction](simplify-fraction.md) | skill | 2 | — |
| [Write a fraction as a decimal](to-decimal.md) | skill | 2 | — |
