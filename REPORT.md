# Solving arithmetic problems: methods classified by first step

Most arithmetic questions can be solved in several ways. This report catalogs the methods for a family of
ratio, fraction, and percent questions, and the word problems built on them. Each method is classified by **the first
step a student takes**, with the second step used only when methods share a first step. The goal is an app that guides a
student step by step: from each step the student writes, a classifier works out which route through the graph they
are on, and the app responds with help for *that* route.

## How the data is organized

Everything is written in one step language (see `v2/vocabulary.json`). A **step** is one thing a student does, and every
step has a sentence. Steps run in sequence. **`all`** marks steps that can be done in any order. **`choose`** marks a
decision with one correct option and its traps. **`use`** calls another question as a single step.

- **Skills** are small questions that other methods call: simplify a fraction, write it as a decimal, find a common
  multiple, cross products. Each has its own methods (a common multiple can be recalled, found by listing multiples,
  by multiplying, or from the GCF).
- **Core questions** (compare fractions, missing value, add fractions) have methods built from steps and skill calls.
- **Applied questions** are core questions in context: a proportion check *is* comparing fractions for equality, a
  better buy *is* comparing price ÷ quantity, and a percent of a number *is* a missing value with denominator 100.
- **Word problems** start with **extraction**: a set of decisions (which numbers go together, which way round,
  "more" or "in all", which numbers aren't needed), done in any order. Each decision has a correct option and traps,
  and the decisions together pick the question and its numbers.

`v2/build.py` expands every skill call into every combination of skill methods and every `all` block into every order,
runs each variant on the examples to check the answer, and groups variants by their first step (then their second) to
make the classifier's trees. The hand-written first version is in `v1/` for comparison.

## Reading the graphs

Every diagram uses the same grammar, and every diagram carries a legend at the bottom.

- **Rectangles are steps**: the sentence, then the worked expression, then tags. A first step is tagged with its
  operation · scope; a step inside a called question is tagged *in: that question*.
- **× hexagons are choices**: the student picks one way forward. This is where the classifier works. Arrows leaving a
  choice are always labeled: with the method they lead to, or with the extraction answer (✓). Red dashed arrows are traps (✗).
- **"all" diamonds** split into branches that are all done, in any order, and join again.
- **Boxes with side bars are calls** to another question, shown with what goes in and what comes out; each has its own page.
- **Thick green arrows carry data** into a question: the extracted numbers, with what they count.
- A **method is a route**, not a box. Steps that methods share are drawn once, and the method's name sits on the arrow
  where its route becomes unique.

## What expanding the skills revealed

Shared first steps that only appear once skills and `all` blocks are expanded:

- In *compare fractions*, `3 × 7` starts both **cross-multiply** and **rewrite one fraction over the other's
  denominator** (through missing value's cross-multiply). The next step decides: `5 × 4` vs `21 ÷ 4`.
- In *proportion check*, `6 ÷ 8` starts both **decimal** and **rewrite over the other's denominator**,
  and `GCF(6, 8)` starts both **simplify** and the same rewrite.
- `3 × 5 = 15` can come from **listing multiples** or from **multiplying**; the graphs show it as one step.

Known limit: the generated trees store a student-chosen multiplier as a wildcard, so a typed classifier sees
`4 × 25` as matching three methods. The per-example graphs tell those apart by value.

## How the questions reuse each other

Green = skill, yellow = core, blue = applied. Solid arrows: a method uses that question as a step. Dotted arrows: the applied question *is* the core question in context. (compare-fractions also calls itself: *distance from 1* ends by comparing the two gaps.)

[![How the questions reuse each other](v2/svg/index.svg)](v2/svg/index.svg)

<sub>Click the graph to open it full size · [mermaid source](v2/svg/index.mmd)</sub>

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

Its methods call: [common-multiple](#common-multiple), [cross-products](#cross-products), [missing-value](#missing-value), [simplify-fraction](#simplify-fraction), [to-decimal](#to-decimal)

| Method | Idea | Best when | Calls |
|---|---|---|---|
| **Common denominator** `common_denominator` | Rewrite both fractions over a common denominator, add the numerators, simplify. | Always; use the least common multiple to keep numbers small. | [common-multiple](#common-multiple), [missing-value](#missing-value), [simplify-fraction](#simplify-fraction) |
| **Bow-tie (cross-multiply)** `bow_tie` | ({a}×{d} + {c}×{b}) / ({b}×{d}), then simplify. | Quick, with small denominators. | [cross-products](#cross-products), [simplify-fraction](#simplify-fraction) |
| **Convert to decimals** `decimal` | Write each fraction as a decimal and add. | An approximate answer is enough. | [to-decimal](#to-decimal) |

Each graph starts at the question and branches at **× Which first step?** into every first step a student might write. Methods that share a first step meet there and split at **× Which next step?**. Each route then follows its method to the answer. The legend at the bottom of each graph explains the shapes.

### Find 5/6 + 3/4.

[![Find 5/6 + 3/4.](v2/svg/add-fractions-1.svg)](v2/svg/add-fractions-1.svg)

<sub>Click the graph to open it full size · [mermaid source](v2/svg/add-fractions-1.mmd)</sub>

### Find 2/3 + 1/5.

[![Find 2/3 + 1/5.](v2/svg/add-fractions-2.svg)](v2/svg/add-fractions-2.svg)

<sub>Click the graph to open it full size · [mermaid source](v2/svg/add-fractions-2.mmd)</sub>


<a name="compare-fractions"></a>

## Compare two fractions

`compare-fractions` · core · prompt: *Which is larger: {a}/{b} or {c}/{d}? (Or are they equal?)*

Its methods call: [common-multiple](#common-multiple), [compare-fractions](#compare-fractions), [cross-products](#cross-products), [missing-value](#missing-value), [simplify-fraction](#simplify-fraction), [to-decimal](#to-decimal)

| Method | Idea | Best when | Calls |
|---|---|---|---|
| **Cross-multiply** `cross_multiply` | {a}/{b} > {c}/{d} exactly when {a}×{d} > {c}×{b}. | A quick check with small numbers. | [cross-products](#cross-products) |
| **Common denominator** `common_denominator` | Rewrite both fractions over the same denominator, then compare numerators. | The denominators are small or related. | [common-multiple](#common-multiple), [missing-value](#missing-value) |
| **Rewrite one fraction over the other's denominator** `match_denominator` | Turn {a}/{b} into something over {d}, then compare its top with {c}. | {d} is a multiple of {b}. | [missing-value](#missing-value) |
| **Common numerator** `common_numerator` | With equal numerators, the smaller denominator gives the bigger fraction. | The numerators are smaller or simpler than the denominators. | [common-multiple](#common-multiple), [missing-value](#missing-value) |
| **Convert to decimals** `decimal` | Write each fraction as a decimal and compare. | A calculator is allowed. | [to-decimal](#to-decimal) |
| **Compare unit rates (flipped fractions)** `unit_rate` | How much bottom per 1 of top? The bigger rate belongs to the smaller fraction. | The context is a rate (miles per hour, items per dollar). | [to-decimal](#to-decimal) |
| **Compare scale factors** `scale_factor` | How much do the tops grow ({c} ÷ {a}) compared with the bottoms ({d} ÷ {b})? | One fraction looks like a scaled-up version of the other. | — |
| **Ratio table** `ratio_table` | Scale {a}:{b} by 2, 3, 4, … until the top reaches {c}, then compare bottoms. | {c} is a small whole-number multiple of {a}. | — |
| **Graph the points** `graph` | Plot ({a}, {b}) and ({c}, {d}); the steeper line from the origin belongs to the smaller fraction. | Building intuition. | — |
| **Simplify both** `simplify` | Reduce both fractions to lowest terms; equal fractions reduce to the same thing. | Checking equality (proportions). | [simplify-fraction](#simplify-fraction) |
| **Distance from 1** `distance_from_one` | Find how far each fraction is from 1; the one closer to 1 is bigger. | Both fractions are just below 1 (7/8 vs 9/10). | [compare-fractions](#compare-fractions) |

Each graph starts at the question and branches at **× Which first step?** into every first step a student might write. Methods that share a first step meet there and split at **× Which next step?**. Each route then follows its method to the answer. The legend at the bottom of each graph explains the shapes.

### Which is larger: 3/4 or 5/7? (Or are they equal?)

[![Which is larger: 3/4 or 5/7? (Or are they equal?)](v2/svg/compare-fractions-1.svg)](v2/svg/compare-fractions-1.svg)

<sub>Click the graph to open it full size · [mermaid source](v2/svg/compare-fractions-1.mmd)</sub>

Not applicable here: Ratio table (`ratio_table`)

### Which is larger: 3/8 or 2/5? (Or are they equal?)

[![Which is larger: 3/8 or 2/5? (Or are they equal?)](v2/svg/compare-fractions-2.svg)](v2/svg/compare-fractions-2.svg)

<sub>Click the graph to open it full size · [mermaid source](v2/svg/compare-fractions-2.mmd)</sub>

Not applicable here: Ratio table (`ratio_table`)


<a name="missing-value"></a>

## Find the missing value in a proportion

`missing-value` · core · prompt: *Solve {a}/{b} = x/{d}.*

Its methods call: [simplify-fraction](#simplify-fraction), [to-decimal](#to-decimal)

| Method | Idea | Best when | Calls |
|---|---|---|---|
| **Cross-multiply and divide** `cross_multiply` | {a} × {d} = {b} × x, so x = {a} × {d} ÷ {b}. | Always works; most useful when there's no whole-number scale factor. | — |
| **Scale factor** `scale_factor` | Find what turns {b} into {d}, then do the same to {a}. | {d} is a whole-number multiple of {b}. | — |
| **Unit rate** `unit_rate` | Find the value per 1, then scale up to {d}. | {a}/{b} is a friendly decimal. | [to-decimal](#to-decimal) |
| **Inverse rate** `inverse_rate` | Find how many of the second quantity per 1 of the first, then divide. | {b}/{a} is a friendly number. | [to-decimal](#to-decimal) |
| **Ratio table** `ratio_table` | Build {a}:{b} up by ×2, ×3, … until the second term reaches {d}. | {d} is a small whole-number multiple of {b}. | — |
| **Simplify, then scale** `simplify_then_scale` | Reduce {a}/{b} first so a whole-number scale factor appears. | {a}/{b} isn't in lowest terms. | [simplify-fraction](#simplify-fraction) |

Each graph starts at the question and branches at **× Which first step?** into every first step a student might write. Methods that share a first step meet there and split at **× Which next step?**. Each route then follows its method to the answer. The legend at the bottom of each graph explains the shapes.

### Solve 3/5 = x/40.

[![Solve 3/5 = x/40.](v2/svg/missing-value-1.svg)](v2/svg/missing-value-1.svg)

<sub>Click the graph to open it full size · [mermaid source](v2/svg/missing-value-1.mmd)</sub>

### Solve 4/6 = x/15.

[![Solve 4/6 = x/15.](v2/svg/missing-value-2.svg)](v2/svg/missing-value-2.svg)

<sub>Click the graph to open it full size · [mermaid source](v2/svg/missing-value-2.mmd)</sub>

Not applicable here: Ratio table (`ratio_table`)


<a name="better-buy"></a>

## Which is the better buy?

`better-buy` · applied · prompt: *Offer 1: {q1} units for ${p1}. Offer 2: {q2} units for ${p2}. Which is the better buy?*

This is [compare-fractions](#compare-fractions) in context, with `{"a": "p1", "b": "q1", "c": "p2", "d": "q2"}`. Compare the prices per unit p1/q1 and p2/q2; the smaller one is the better buy, so 'first' (bigger) maps to 'second'.

| Method | Idea | Best when | Calls |
|---|---|---|---|
| **Price per unit** `price_per_unit` (= compare-fractions · decimal) | Find the cost of 1 unit in each offer; lower is better. | A calculator is allowed. | [to-decimal](#to-decimal) |
| **Units per dollar** `units_per_dollar` (= compare-fractions · unit_rate) | Find how much $1 buys; more is better. | The context is a rate (miles per hour, items per dollar). | [to-decimal](#to-decimal) |
| **Common quantity** `common_quantity` (= compare-fractions · common_denominator) | Price both offers at the same quantity. | The denominators are small or related. | [common-multiple](#common-multiple), [missing-value](#missing-value) |
| **Scale one offer to the other's size** `scale_up` (= compare-fractions · match_denominator) | What would offer 1 cost for {q2} units? | {d} is a multiple of {b}. | [missing-value](#missing-value) |
| **Cross-multiply** `cross_multiply` (= compare-fractions · cross_multiply) | {a}/{b} > {c}/{d} exactly when {a}×{d} > {c}×{b}. | A quick check with small numbers. | [cross-products](#cross-products) |
| **Compare growth** `compare_growth` (= compare-fractions · scale_factor) | Price grows by {p2} ÷ {p1}, quantity by {q2} ÷ {q1}; quantity growing faster means offer 2 is better. | One fraction looks like a scaled-up version of the other. | — |

Each graph starts at the question and branches at **× Which first step?** into every first step a student might write. Methods that share a first step meet there and split at **× Which next step?**. Each route then follows its method to the answer. The legend at the bottom of each graph explains the shapes.

### Offer 1: 12 units for $3. Offer 2: 20 units for $4.5. Which is the better buy?

[![Offer 1: 12 units for $3. Offer 2: 20 units for $4.5. Which is the better buy?](v2/svg/better-buy-1.svg)](v2/svg/better-buy-1.svg)

<sub>Click the graph to open it full size · [mermaid source](v2/svg/better-buy-1.mmd)</sub>

### Offer 1: 6 units for $4.2. Offer 2: 10 units for $7.5. Which is the better buy?

[![Offer 1: 6 units for $4.2. Offer 2: 10 units for $7.5. Which is the better buy?](v2/svg/better-buy-2.svg)](v2/svg/better-buy-2.svg)

<sub>Click the graph to open it full size · [mermaid source](v2/svg/better-buy-2.mmd)</sub>


<a name="percent-of"></a>

## Find a percent of a number

`percent-of` · applied · prompt: *What is {p}% of {n}?*

This is [missing-value](#missing-value) in context, with `{"a": "p", "b": 100, "d": "n"}`. p% of n means p/100 = x/n.

| Method | Idea | Best when | Calls |
|---|---|---|---|
| **Convert to a decimal and multiply** `decimal` (= missing-value · unit_rate) | {p}% = {p} ÷ 100; multiply that by {n}. | {a}/{b} is a friendly decimal. | [to-decimal](#to-decimal) |
| **Find 1% first** `one_percent` (= missing-value · scale_factor) | 1% of {n} is {n} ÷ 100; multiply by {p}. | {d} is a whole-number multiple of {b}. | — |
| **Multiply, then divide by 100** `multiply_first` (= missing-value · cross_multiply) | {p} × {n} ÷ 100. | Always works; most useful when there's no whole-number scale factor. | — |
| **Use a simplified fraction** `fraction` (= missing-value · simplify_then_scale) | {p}/100 simplifies (15/100 = 3/20); take that fraction of {n}. | {a}/{b} isn't in lowest terms. | [simplify-fraction](#simplify-fraction) |
| **Ratio table** `ratio_table` (= missing-value · ratio_table) | Scale {p}:100 until the 100 becomes {n}. | {d} is a small whole-number multiple of {b}. | — |
| **Build from 10% and 5%** `benchmark_10_5` | 10% is easy (÷ 10) and 5% is half of that; add up the pieces. | The percent is a multiple of 5. | — |

Each graph starts at the question and branches at **× Which first step?** into every first step a student might write. Methods that share a first step meet there and split at **× Which next step?**. Each route then follows its method to the answer. The legend at the bottom of each graph explains the shapes.

### What is 15% of 80?

[![What is 15% of 80?](v2/svg/percent-of-1.svg)](v2/svg/percent-of-1.svg)

<sub>Click the graph to open it full size · [mermaid source](v2/svg/percent-of-1.mmd)</sub>

Not applicable here: Ratio table (`ratio_table`)

### What is 35% of 60?

[![What is 35% of 60?](v2/svg/percent-of-2.svg)](v2/svg/percent-of-2.svg)

<sub>Click the graph to open it full size · [mermaid source](v2/svg/percent-of-2.mmd)</sub>

Not applicable here: Ratio table (`ratio_table`)


<a name="proportion-check"></a>

## Are two ratios proportional?

`proportion-check` · applied · prompt: *Are {a}:{b} and {c}:{d} proportional?*

This is [compare-fractions](#compare-fractions) in context, with `{"a": "a", "b": "b", "c": "c", "d": "d"}`. 

| Method | Idea | Best when | Calls |
|---|---|---|---|
| **Cross-multiply** `cross_multiply` (= compare-fractions · cross_multiply) | {a}/{b} > {c}/{d} exactly when {a}×{d} > {c}×{b}. | A quick check with small numbers. | [cross-products](#cross-products) |
| **Common denominator** `common_denominator` (= compare-fractions · common_denominator) | Rewrite both fractions over the same denominator, then compare numerators. | The denominators are small or related. | [common-multiple](#common-multiple), [missing-value](#missing-value) |
| **Rewrite one fraction over the other's denominator** `match_denominator` (= compare-fractions · match_denominator) | Turn {a}/{b} into something over {d}, then compare its top with {c}. | {d} is a multiple of {b}. | [missing-value](#missing-value) |
| **Common numerator** `common_numerator` (= compare-fractions · common_numerator) | With equal numerators, the smaller denominator gives the bigger fraction. | The numerators are smaller or simpler than the denominators. | [common-multiple](#common-multiple), [missing-value](#missing-value) |
| **Convert to decimals** `decimal` (= compare-fractions · decimal) | Write each fraction as a decimal and compare. | A calculator is allowed. | [to-decimal](#to-decimal) |
| **Compare unit rates (flipped fractions)** `unit_rate` (= compare-fractions · unit_rate) | How much bottom per 1 of top? The bigger rate belongs to the smaller fraction. | The context is a rate (miles per hour, items per dollar). | [to-decimal](#to-decimal) |
| **Compare scale factors** `scale_factor` (= compare-fractions · scale_factor) | How much do the tops grow ({c} ÷ {a}) compared with the bottoms ({d} ÷ {b})? | One fraction looks like a scaled-up version of the other. | — |
| **Ratio table** `ratio_table` (= compare-fractions · ratio_table) | Scale {a}:{b} by 2, 3, 4, … until the top reaches {c}, then compare bottoms. | {c} is a small whole-number multiple of {a}. | — |
| **Graph the points** `graph` (= compare-fractions · graph) | Plot ({a}, {b}) and ({c}, {d}); the steeper line from the origin belongs to the smaller fraction. | Building intuition. | — |
| **Simplify both** `simplify` (= compare-fractions · simplify) | Reduce both fractions to lowest terms; equal fractions reduce to the same thing. | Checking equality (proportions). | [simplify-fraction](#simplify-fraction) |
| **Distance from 1** `distance_from_one` (= compare-fractions · distance_from_one) | Find how far each fraction is from 1; the one closer to 1 is bigger. | Both fractions are just below 1 (7/8 vs 9/10). | [compare-fractions](#compare-fractions) |

Each graph starts at the question and branches at **× Which first step?** into every first step a student might write. Methods that share a first step meet there and split at **× Which next step?**. Each route then follows its method to the answer. The legend at the bottom of each graph explains the shapes.

### Are 6:8 and 72:96 proportional?

[![Are 6:8 and 72:96 proportional?](v2/svg/proportion-check-1.svg)](v2/svg/proportion-check-1.svg)

<sub>Click the graph to open it full size · [mermaid source](v2/svg/proportion-check-1.mmd)</sub>

### Are 4:6 and 10:14 proportional?

[![Are 4:6 and 10:14 proportional?](v2/svg/proportion-check-2.svg)](v2/svg/proportion-check-2.svg)

<sub>Click the graph to open it full size · [mermaid source](v2/svg/proportion-check-2.mmd)</sub>

Not applicable here: Ratio table (`ratio_table`)


<a name="common-multiple"></a>

## Find a common multiple

`common-multiple` · skill · prompt: *Find a common multiple of {x} and {y}.*

| Method | Idea | Best when | Calls |
|---|---|---|---|
| **Know the LCM** `recall` | Recognize the least common multiple directly. | Small, familiar numbers. | — |
| **List multiples** `list_multiples` | Count up by {x} until you reach a number {y} divides. | Small numbers. | — |
| **Multiply them** `product` | {x} × {y} is always a common multiple. | The numbers share no factors (then it's also the least). | — |
| **Use the GCF** `gcf_formula` | LCM = {x} ÷ GCF × {y}. | Large numbers whose GCF you can find. | — |

Each graph starts at the question and branches at **× Which first step?** into every first step a student might write. Methods that share a first step meet there and split at **× Which next step?**. Each route then follows its method to the answer. The legend at the bottom of each graph explains the shapes.

### Find a common multiple of 4 and 6.

[![Find a common multiple of 4 and 6.](v2/svg/common-multiple-1.svg)](v2/svg/common-multiple-1.svg)

<sub>Click the graph to open it full size · [mermaid source](v2/svg/common-multiple-1.mmd)</sub>

### Find a common multiple of 4 and 7.

[![Find a common multiple of 4 and 7.](v2/svg/common-multiple-2.svg)](v2/svg/common-multiple-2.svg)

<sub>Click the graph to open it full size · [mermaid source](v2/svg/common-multiple-2.mmd)</sub>


<a name="cross-products"></a>

## Cross products

`cross-products` · skill · prompt: *Find the cross products of {a}/{b} and {c}/{d}.*

| Method | Idea | Best when | Calls |
|---|---|---|---|
| **Multiply the diagonals** `diagonals` | Multiply each numerator by the other fraction's denominator. |  | — |

Each graph starts at the question and branches at **× Which first step?** into every first step a student might write. Methods that share a first step meet there and split at **× Which next step?**. Each route then follows its method to the answer. The legend at the bottom of each graph explains the shapes.

### Find the cross products of 3/4 and 5/7.

[![Find the cross products of 3/4 and 5/7.](v2/svg/cross-products-1.svg)](v2/svg/cross-products-1.svg)

<sub>Click the graph to open it full size · [mermaid source](v2/svg/cross-products-1.mmd)</sub>

### Find the cross products of 6/8 and 72/96.

[![Find the cross products of 6/8 and 72/96.](v2/svg/cross-products-2.svg)](v2/svg/cross-products-2.svg)

<sub>Click the graph to open it full size · [mermaid source](v2/svg/cross-products-2.mmd)</sub>


<a name="simplify-fraction"></a>

## Simplify a fraction

`simplify-fraction` · skill · prompt: *Simplify {x}/{y}.*

| Method | Idea | Best when | Calls |
|---|---|---|---|
| **Divide by the GCF** `gcf` | Find the greatest common factor once and divide both terms by it. | You can spot the GCF. | — |
| **Divide out common factors repeatedly** `repeated` | Keep dividing both terms by any shared factor (2, 3, 5, …) until none is left. | The numbers are large and the GCF isn't obvious. | — |

Each graph starts at the question and branches at **× Which first step?** into every first step a student might write. Methods that share a first step meet there and split at **× Which next step?**. Each route then follows its method to the answer. The legend at the bottom of each graph explains the shapes.

### Simplify 6/8.

[![Simplify 6/8.](v2/svg/simplify-fraction-1.svg)](v2/svg/simplify-fraction-1.svg)

<sub>Click the graph to open it full size · [mermaid source](v2/svg/simplify-fraction-1.mmd)</sub>

### Simplify 72/96.

[![Simplify 72/96.](v2/svg/simplify-fraction-2.svg)](v2/svg/simplify-fraction-2.svg)

<sub>Click the graph to open it full size · [mermaid source](v2/svg/simplify-fraction-2.mmd)</sub>


<a name="to-decimal"></a>

## Write a fraction as a decimal

`to-decimal` · skill · prompt: *Write {x}/{y} as a decimal.*

| Method | Idea | Best when | Calls |
|---|---|---|---|
| **Divide** `divide` | Divide the numerator by the denominator (long division or a calculator). | Always works. | — |
| **Scale to 10, 100, 1000** `power_of_ten` | Multiply top and bottom so the denominator becomes 10, 100, or 1000, then read off the decimal. | The denominator only has factors 2 and 5 (2, 4, 5, 8, 20, 25, …). | — |

Each graph starts at the question and branches at **× Which first step?** into every first step a student might write. Methods that share a first step meet there and split at **× Which next step?**. Each route then follows its method to the answer. The legend at the bottom of each graph explains the shapes.

### Write 3/4 as a decimal.

[![Write 3/4 as a decimal.](v2/svg/to-decimal-1.svg)](v2/svg/to-decimal-1.svg)

<sub>Click the graph to open it full size · [mermaid source](v2/svg/to-decimal-1.mmd)</sub>

### Write 5/8 as a decimal.

[![Write 5/8 as a decimal.](v2/svg/to-decimal-2.svg)](v2/svg/to-decimal-2.svg)

<sub>Click the graph to open it full size · [mermaid source](v2/svg/to-decimal-2.mmd)</sub>


## Word problems

A word problem needs **extraction** before any method applies. Extraction is a set of decisions, done in any order: which question the story is, which numbers go together and which way round, whether a number is extra or a total, which numbers aren't needed. Each decision has one correct option and its **traps**: the mistakes students actually make. A trap is the correct reading with that one decision swapped, so the build computes the wrong answer it leads to, and the first steps that give it away (steps no correct reading starts with). That lets an app diagnose an extraction mistake from a student's answer, and often from their first step.

### Extraction concepts

| Concept | What the student decides | Cues | Typical mistake |
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

| Word problem | Is a | Decisions |
|---|---|---|
| [Cereal boxes](#cereal-boxes) | [Which is the better buy?](#better-buy) | Recognize the question type, Ignore numbers that don't matter, Find the pair that forms the ratio, Which way wins |
| [Free throws](#free-throws) | [Compare two fractions](#compare-fractions) | Recognize the question type, Find the pair that forms the ratio, Which way wins |
| [Jacket on sale](#jacket-sale) | [Find a percent of a number](#percent-of) | Recognize the question type, Name the unknown |
| [Lemonade: how many in all](#lemonade-in-all) | [Find the missing value in a proportion](#missing-value) | Recognize the question type, Find the pair that forms the ratio, 'More' vs 'in all', Finish the story, Scale, don't add |
| [Lemonade: more sugar](#lemonade-more-sugar) | [Find the missing value in a proportion](#missing-value) | Recognize the question type, Find the pair that forms the ratio, Keep the same order on both sides, 'More' vs 'in all', Scale, don't add |
| [Map scale](#map-scale) | [Find the missing value in a proportion](#missing-value) | Recognize the question type, Find the pair that forms the ratio, Name the unknown, Keep the same order on both sides |
| [Same shade of paint?](#paint-shade) | [Are two ratios proportional?](#proportion-check) | Recognize the question type, Scale, don't add |
| [Pancakes by the dozen](#pancakes-dozen) | [Find the missing value in a proportion](#missing-value) | Recognize the question type, Find the pair that forms the ratio, Spot numbers written as words, Keep the same order on both sides |
| [Sharing pizza](#pizza-shared) | [Add two fractions](#add-fractions) | Recognize the question type, Answer in the story's terms |
| [Whose lemonade is sweeter?](#sweeter-lemonade) | [Compare two fractions](#compare-fractions) | Recognize the question type, Which way wins, Find the pair that forms the ratio, Scale, don't add |
| [Train in minutes](#train-minutes) | [Find the missing value in a proportion](#missing-value) | Recognize the question type, Find the pair that forms the ratio, Make units match, Keep the same order on both sides |
| [Walking to school](#walk-to-school) | [Find a percent of a number](#percent-of) | Recognize the question type, Find the pair that forms the ratio, Ignore numbers that don't matter |

<a name="cereal-boxes"></a>

### Cereal boxes

> A 12-ounce box of cereal costs $3.00 and a 20-ounce box costs $4.50. The store is 2 miles from home. Which box is the better buy?

**Asked:** which box is the better buy (box). **Is a:** [Which is the better buy?](#better-buy). **Answer:** the 20-ounce box ($0.225 per ounce vs $0.25).

| Phrase | Value | Counts | Needed? |
|---|---|---|---|
| “a 12-ounce box” | 12 ounces | cereal in the small box | yes |
| “costs $3.00” | 3.00 dollars | price of the small box | yes |
| “a 20-ounce box” | 20 ounces | cereal in the big box | yes |
| “costs $4.50” | 4.50 dollars | price of the big box | yes |
| “2 miles from home” | 2 miles | distance to the store | **no** |

| Decision | Concept | Correct | Traps → wrong answer |
|---|---|---|---|
| What kind of question is this? | Recognize the question type | Which costs less for what you get: a better buy | — |
| Which number isn't needed? | Ignore numbers that don't matter | 2 miles from home | — |
| What do you compare? | Find the pair that forms the ratio | Each box's price per ounce | Just the prices → the 12-ounce box |
| Which way wins? | Which way wins | The lower price per ounce | The higher price per ounce → the 12-ounce box |

The graph starts at the story. The **Extract** frame holds the decisions; red dashed arrows leave a decision for each trap and run to the wrong answer it produces. The thick green arrow carries the extracted numbers into the question, drawn exactly as on the question's own page. Any follow-up step comes after, then the answer in the story's terms. The legend is at the bottom.

[![Cereal boxes](v2/svg/wp-cereal-boxes.svg)](v2/svg/wp-cereal-boxes.svg)

<sub>Click the graph to open it full size · [mermaid source](v2/svg/wp-cereal-boxes.mmd)</sub>

| Trap | Mistake | Leads to | Caught by the answer? | Gives itself away with |
|---|---|---|---|---|
| Find the pair that forms the ratio | Compares prices only and picks the cheaper box. | the 12-ounce box | yes | — |
| Which way wins | Picks the box with the higher price per ounce. | the 12-ounce box | yes | — |

<a name="free-throws"></a>

### Free throws

> Maya made 3 of her 4 free throws. Leo made 5 of his 7. Who has the better shooting rate?

**Asked:** who has the better shooting rate (name). **Is a:** [Compare two fractions](#compare-fractions). **Answer:** Maya (3/4 = 0.75 vs 5/7 ≈ 0.714).

| Phrase | Value | Counts | Needed? |
|---|---|---|---|
| “made 3” | 3 shots | Maya's made shots | yes |
| “of her 4” | 4 shots | Maya's attempts | yes |
| “made 5” | 5 shots | Leo's made shots | yes |
| “of his 7” | 7 shots | Leo's attempts | yes |

| Decision | Concept | Correct | Traps → wrong answer |
|---|---|---|---|
| What kind of question is this? | Recognize the question type | Whose rate is higher: compare two fractions | — |
| What is each player's rate? | Find the pair that forms the ratio | Shots made out of shots taken | Just the shots made → Leo |
| Which way wins? | Which way wins | The bigger fraction made | The bigger fraction missed → Leo |

The graph starts at the story. The **Extract** frame holds the decisions; red dashed arrows leave a decision for each trap and run to the wrong answer it produces. The thick green arrow carries the extracted numbers into the question, drawn exactly as on the question's own page. Any follow-up step comes after, then the answer in the story's terms. The legend is at the bottom.

[![Free throws](v2/svg/wp-free-throws.svg)](v2/svg/wp-free-throws.svg)

<sub>Click the graph to open it full size · [mermaid source](v2/svg/wp-free-throws.mmd)</sub>

| Trap | Mistake | Leads to | Caught by the answer? | Gives itself away with |
|---|---|---|---|---|
| Find the pair that forms the ratio | Compares shots made only (5 > 3). | Leo | yes | — |
| Which way wins | Compares misses per shot and picks the bigger. | Leo | yes | `1 × 7 = 7`, `LCM(1, 2) = 2`, `1 ÷ 4 = 0.25`, `4 ÷ 1 = 4` |

<a name="jacket-sale"></a>

### Jacket on sale

> A jacket normally costs $80. This week it is 15% off. How much does the jacket cost this week?

**Asked:** how much does it cost this week (dollars). **Is a:** [Find a percent of a number](#percent-of). **Answer:** $68.

| Phrase | Value | Counts | Needed? |
|---|---|---|---|
| “costs $80” | 80 dollars | original price | yes |
| “15% off” | 15 percent | discount | yes |

| Decision | Concept | Correct | Traps → wrong answer |
|---|---|---|---|
| What kind of question is this? | Recognize the question type | 15% of the price comes off: a percent of a number | $15 comes off → 65 |
| What does the question ask for? | Name the unknown | The new price | The savings → 12 |

The graph starts at the story. The **Extract** frame holds the decisions; red dashed arrows leave a decision for each trap and run to the wrong answer it produces. The thick green arrow carries the extracted numbers into the question, drawn exactly as on the question's own page. Any follow-up step comes after, then the answer in the story's terms. The legend is at the bottom.

[![Jacket on sale](v2/svg/wp-jacket-sale.svg)](v2/svg/wp-jacket-sale.svg)

<sub>Click the graph to open it full size · [mermaid source](v2/svg/wp-jacket-sale.mmd)</sub>

| Trap | Mistake | Leads to | Caught by the answer? | Gives itself away with |
|---|---|---|---|---|
| Recognize the question type | Takes off $15 instead of 15%. | 65 | yes | — |
| Name the unknown | Answers the savings instead of the new price. | 12 | yes | — |

<a name="lemonade-in-all"></a>

### Lemonade: how many in all

> Joe used 4 spoons of sugar to make the first 6 glasses of lemonade. He wants 18 glasses in all. How many more spoons of sugar does he need?

**Asked:** how many more spoons of sugar (spoons). **Is a:** [Find the missing value in a proportion](#missing-value). **Answer:** 8 more spoons of sugar.

| Phrase | Value | Counts | Needed? |
|---|---|---|---|
| “4 spoons of sugar” | 4 spoons | sugar already used | yes |
| “the first 6 glasses” | 6 glasses | lemonade made | yes |
| “18 glasses in all” | 18 glasses | lemonade wanted in total | yes |

| Decision | Concept | Correct | Traps → wrong answer |
|---|---|---|---|
| What kind of question is this? | Recognize the question type | Same recipe, more glasses: a missing value | — |
| Which two quantities go together? | Find the pair that forms the ratio | 4 spoons of sugar with 6 glasses | — |
| Is 18 the extra glasses or the total? | 'More' vs 'in all' | 18 is the total | 18 is the extra glasses → 12 |
| Is the sugar for all 18 glasses the answer? | Finish the story | No: subtract the 4 spoons already used | Yes → 12 |
| How does the sugar change when the glasses go up? | Scale, don't add | It scales by the same factor | It goes up by the same number of extra glasses → 12 |

The graph starts at the story. The **Extract** frame holds the decisions; red dashed arrows leave a decision for each trap and run to the wrong answer it produces. The thick green arrow carries the extracted numbers into the question, drawn exactly as on the question's own page. Any follow-up step comes after, then the answer in the story's terms. The legend is at the bottom.

[![Lemonade: how many in all](v2/svg/wp-lemonade-in-all.svg)](v2/svg/wp-lemonade-in-all.svg)

<sub>Click the graph to open it full size · [mermaid source](v2/svg/wp-lemonade-in-all.mmd)</sub>

| Trap | Mistake | Leads to | Caught by the answer? | Gives itself away with |
|---|---|---|---|---|
| 'More' vs 'in all' | Reads 18 as 18 more glasses. | 12 | yes | — |
| Finish the story | Stops at the sugar for all 18 glasses. | 12 | yes | — |
| Scale, don't add | Adds instead of scaling: 12 more glasses, so 12 more spoons. | 12 | yes | — |

<a name="lemonade-more-sugar"></a>

### Lemonade: more sugar

> Joe is having a party. He has 6 cups of water and 4 spoons of sugar, which make 6 glasses of lemonade. He needs 18 more glasses of lemonade. How many more spoons of sugar does he need?

**Asked:** how many more spoons of sugar (spoons). **Is a:** [Find the missing value in a proportion](#missing-value). **Answer:** 12 more spoons of sugar.

| Phrase | Value | Counts | Needed? |
|---|---|---|---|
| “6 cups of water” | 6 cups | water | **no** |
| “4 spoons of sugar” | 4 spoons | sugar | yes |
| “6 glasses of lemonade” | 6 glasses | lemonade | yes |
| “18 more glasses” | 18 glasses | extra lemonade | yes |

| Decision | Concept | Correct | Traps → wrong answer |
|---|---|---|---|
| What kind of question is this? | Recognize the question type | Same recipe, more glasses: a missing value | — |
| Which two quantities go together? | Find the pair that forms the ratio | 4 spoons of sugar with 6 glasses | 4 spoons of sugar with 6 cups of water → 12 |
| Which way round does the ratio go? | Keep the same order on both sides | Sugar over glasses on both sides | Glasses over sugar on one side → 27 |
| Is 18 the extra glasses or the total? | 'More' vs 'in all' | 18 is the extra glasses | 18 more makes 24 in all, so use 24 → 16; 18 is the total, so subtract the sugar used → 8 |
| How does the sugar change when the glasses go up? | Scale, don't add | It scales by the same factor | It goes up by the same 18 → 18 |

The graph starts at the story. The **Extract** frame holds the decisions; red dashed arrows leave a decision for each trap and run to the wrong answer it produces. The thick green arrow carries the extracted numbers into the question, drawn exactly as on the question's own page. Any follow-up step comes after, then the answer in the story's terms. The legend is at the bottom.

[![Lemonade: more sugar](v2/svg/wp-lemonade-more-sugar.svg)](v2/svg/wp-lemonade-more-sugar.svg)

<sub>Click the graph to open it full size · [mermaid source](v2/svg/wp-lemonade-more-sugar.mmd)</sub>

| Trap | Mistake | Leads to | Caught by the answer? | Gives itself away with |
|---|---|---|---|---|
| Find the pair that forms the ratio | Pairs sugar with the water, which isn't needed. | 12 | **no**: same answer, so ask how they got it | — |
| Keep the same order on both sides | Flips one side: glasses over sugar = x over glasses. | 27 | yes | `6 × 18 = 108`, `18 ÷ 4 = 4.5` |
| 'More' vs 'in all' | Finds the sugar for all 24 glasses instead of the 18 extra. | 16 | yes | `4 × 24 = 96`, `24 ÷ 6 = 4`, `6 × 4 = 24` |
| 'More' vs 'in all' | Reads 18 as the new total and subtracts the 4 spoons already used. | 8 | yes | — |
| Scale, don't add | Adds instead of scaling: 18 more glasses, so 18 more spoons. | 18 | yes | — |

<a name="map-scale"></a>

### Map scale

> On a map, 1 inch stands for 25 miles. Two towns are 3.5 inches apart on the map. How far apart are they really?

**Asked:** how far apart really (miles). **Is a:** [Find the missing value in a proportion](#missing-value). **Answer:** 87.5 miles.

| Phrase | Value | Counts | Needed? |
|---|---|---|---|
| “1 inch” | 1 inch | map distance | yes |
| “25 miles” | 25 miles | real distance | yes |
| “3.5 inches apart” | 3.5 inches | map distance between the towns | yes |

| Decision | Concept | Correct | Traps → wrong answer |
|---|---|---|---|
| What kind of question is this? | Recognize the question type | Same scale, new distance: a missing value | — |
| Which two quantities go together? | Find the pair that forms the ratio | 25 real miles for each 1 map inch | The scale and the map distance → 50/7 |
| What gets scaled up? | Name the unknown | The 3.5 inches between the towns | — |
| Which way round does the ratio go? | Keep the same order on both sides | Miles over inches on both sides | Inches over miles on one side → 0.14 |

The graph starts at the story. The **Extract** frame holds the decisions; red dashed arrows leave a decision for each trap and run to the wrong answer it produces. The thick green arrow carries the extracted numbers into the question, drawn exactly as on the question's own page. Any follow-up step comes after, then the answer in the story's terms. The legend is at the bottom.

[![Map scale](v2/svg/wp-map-scale.svg)](v2/svg/wp-map-scale.svg)

<sub>Click the graph to open it full size · [mermaid source](v2/svg/wp-map-scale.mmd)</sub>

| Trap | Mistake | Leads to | Caught by the answer? | Gives itself away with |
|---|---|---|---|---|
| Find the pair that forms the ratio | Divides the scale by the map distance. | 50/7 | yes | — |
| Keep the same order on both sides | Flips one side: inches over miles. | 0.14 | yes | `1 × 3.5 = 3.5`, `3.5 ÷ 25 = 0.14` |

<a name="paint-shade"></a>

### Same shade of paint?

> Paint A mixes 6 cans of blue with 8 cans of white. Paint B mixes 72 cans of blue with 96 cans of white. Will the two paints be the same shade?

**Asked:** will they be the same shade (yes or no). **Is a:** [Are two ratios proportional?](#proportion-check). **Answer:** Yes: both are 3 blue to 4 white.

| Phrase | Value | Counts | Needed? |
|---|---|---|---|
| “6 cans of blue” | 6 cans | blue in A | yes |
| “8 cans of white” | 8 cans | white in A | yes |
| “72 cans of blue” | 72 cans | blue in B | yes |
| “96 cans of white” | 96 cans | white in B | yes |

| Decision | Concept | Correct | Traps → wrong answer |
|---|---|---|---|
| What kind of question is this? | Recognize the question type | Same shade means the same ratio: a proportion check | — |
| How do the mixes compare? | Scale, don't add | By ratio | By difference: white minus blue → no |

The graph starts at the story. The **Extract** frame holds the decisions; red dashed arrows leave a decision for each trap and run to the wrong answer it produces. The thick green arrow carries the extracted numbers into the question, drawn exactly as on the question's own page. Any follow-up step comes after, then the answer in the story's terms. The legend is at the bottom.

[![Same shade of paint?](v2/svg/wp-paint-shade.svg)](v2/svg/wp-paint-shade.svg)

<sub>Click the graph to open it full size · [mermaid source](v2/svg/wp-paint-shade.mmd)</sub>

| Trap | Mistake | Leads to | Caught by the answer? | Gives itself away with |
|---|---|---|---|---|
| Scale, don't add | Compares the differences (2 more white vs 24 more white). | no | yes | — |

<a name="pancakes-dozen"></a>

### Pancakes by the dozen

> A pancake recipe uses 2 cups of flour and 3 eggs to make 12 pancakes. How many cups of flour are needed for 2 dozen pancakes?

**Asked:** how many cups of flour (cups). **Is a:** [Find the missing value in a proportion](#missing-value). **Answer:** 4 cups of flour.

| Phrase | Value | Counts | Needed? |
|---|---|---|---|
| “2 cups of flour” | 2 cups | flour | yes |
| “3 eggs” | 3 eggs | eggs | **no** |
| “12 pancakes” | 12 pancakes | pancakes | yes |
| “2 dozen pancakes” | 2 dozen | pancakes wanted | yes |

| Decision | Concept | Correct | Traps → wrong answer |
|---|---|---|---|
| What kind of question is this? | Recognize the question type | Same recipe, more pancakes: a missing value | — |
| Which two quantities go together? | Find the pair that forms the ratio | 2 cups of flour with 12 pancakes | 3 eggs with 12 pancakes → 6 |
| How many pancakes is 2 dozen? | Spot numbers written as words | 24 | 2 → 1/3 |
| Which way round does the ratio go? | Keep the same order on both sides | Flour over pancakes on both sides | Pancakes over flour on one side → 144 |

The graph starts at the story. The **Extract** frame holds the decisions; red dashed arrows leave a decision for each trap and run to the wrong answer it produces. The thick green arrow carries the extracted numbers into the question, drawn exactly as on the question's own page. Any follow-up step comes after, then the answer in the story's terms. The legend is at the bottom.

[![Pancakes by the dozen](v2/svg/wp-pancakes-dozen.svg)](v2/svg/wp-pancakes-dozen.svg)

<sub>Click the graph to open it full size · [mermaid source](v2/svg/wp-pancakes-dozen.mmd)</sub>

| Trap | Mistake | Leads to | Caught by the answer? | Gives itself away with |
|---|---|---|---|---|
| Find the pair that forms the ratio | Scales the eggs instead of the flour. | 6 | yes | `3 × 24 = 72`, `3 ÷ 12 = 0.25`, `12 ÷ 3 = 4`, `GCF(3, 12) = 3` |
| Spot numbers written as words | Reads '2 dozen' as 2 pancakes. | 1/3 | yes | `2 × 2 = 4` |
| Keep the same order on both sides | Flips one side: pancakes over flour. | 144 | yes | `12 × 24 = 288`, `24 ÷ 2 = 12` |

<a name="pizza-shared"></a>

### Sharing pizza

> Sam ate 5/6 of a pizza and Kim ate 3/4 of a pizza. How much pizza did they eat in all?

**Asked:** how much pizza in all (pizzas). **Is a:** [Add two fractions](#add-fractions). **Answer:** 1 7/12 pizzas.

| Phrase | Value | Counts | Needed? |
|---|---|---|---|
| “5/6 of a pizza” | 5 sixths | Sam's share (top) | yes |
| “5/6 of a pizza” | 6  | Sam's share (bottom) | yes |
| “3/4 of a pizza” | 3 quarters | Kim's share (top) | yes |
| “3/4 of a pizza” | 4  | Kim's share (bottom) | yes |

| Decision | Concept | Correct | Traps → wrong answer |
|---|---|---|---|
| What kind of question is this? | Recognize the question type | 'In all': add the two fractions | Add the tops and add the bottoms → 0.8 |
| How do you say 19/12 of a pizza? | Answer in the story's terms | 1 7/12 pizzas | — |

The graph starts at the story. The **Extract** frame holds the decisions; red dashed arrows leave a decision for each trap and run to the wrong answer it produces. The thick green arrow carries the extracted numbers into the question, drawn exactly as on the question's own page. Any follow-up step comes after, then the answer in the story's terms. The legend is at the bottom.

[![Sharing pizza](v2/svg/wp-pizza-shared.svg)](v2/svg/wp-pizza-shared.svg)

<sub>Click the graph to open it full size · [mermaid source](v2/svg/wp-pizza-shared.mmd)</sub>

| Trap | Mistake | Leads to | Caught by the answer? | Gives itself away with |
|---|---|---|---|---|
| Recognize the question type | Adds tops and bottoms: (5 + 3)/(6 + 4). | 0.8 | yes | — |

<a name="sweeter-lemonade"></a>

### Whose lemonade is sweeter?

> Joe mixes 4 spoons of sugar into 6 glasses of lemonade. Ann mixes 10 spoons of sugar into 14 glasses. Whose lemonade is sweeter?

**Asked:** whose lemonade is sweeter (name). **Is a:** [Compare two fractions](#compare-fractions). **Answer:** Ann's (10/14 ≈ 0.714 spoons per glass vs 4/6 ≈ 0.667).

| Phrase | Value | Counts | Needed? |
|---|---|---|---|
| “4 spoons of sugar” | 4 spoons | Joe's sugar | yes |
| “6 glasses” | 6 glasses | Joe's lemonade | yes |
| “10 spoons of sugar” | 10 spoons | Ann's sugar | yes |
| “14 glasses” | 14 glasses | Ann's lemonade | yes |

| Decision | Concept | Correct | Traps → wrong answer |
|---|---|---|---|
| What kind of question is this? | Recognize the question type | Whose mix is stronger: compare two fractions | — |
| What measures sweetness? | Which way wins | Sugar per glass: more is sweeter | Glasses per spoon: more is sweeter → Joe |
| What do you compare? | Find the pair that forms the ratio | Each mix's sugar per glass | Just the spoons of sugar → Ann |
| How do the mixes differ? | Scale, don't add | By ratio | By difference: glasses minus spoons → Joe |

The graph starts at the story. The **Extract** frame holds the decisions; red dashed arrows leave a decision for each trap and run to the wrong answer it produces. The thick green arrow carries the extracted numbers into the question, drawn exactly as on the question's own page. Any follow-up step comes after, then the answer in the story's terms. The legend is at the bottom.

[![Whose lemonade is sweeter?](v2/svg/wp-sweeter-lemonade.svg)](v2/svg/wp-sweeter-lemonade.svg)

<sub>Click the graph to open it full size · [mermaid source](v2/svg/wp-sweeter-lemonade.mmd)</sub>

| Trap | Mistake | Leads to | Caught by the answer? | Gives itself away with |
|---|---|---|---|---|
| Which way wins | Compares glasses per spoon and calls the bigger one sweeter. | Joe | yes | `(6, 4), (14, 10)` |
| Find the pair that forms the ratio | Compares spoons of sugar only (10 > 4). | Ann | **no**: same answer, so ask how they got it | — |
| Scale, don't add | Compares glasses minus spoons (2 vs 4) and calls the smaller gap sweeter. | Joe | yes | — |

<a name="train-minutes"></a>

### Train in minutes

> A train travels 150 miles in 3 hours. At the same speed, how far does it travel in 90 minutes?

**Asked:** how far (miles). **Is a:** [Find the missing value in a proportion](#missing-value). **Answer:** 75 miles.

| Phrase | Value | Counts | Needed? |
|---|---|---|---|
| “150 miles” | 150 miles | distance | yes |
| “3 hours” | 3 hours | time | yes |
| “90 minutes” | 90 minutes | new time | yes |

| Decision | Concept | Correct | Traps → wrong answer |
|---|---|---|---|
| What kind of question is this? | Recognize the question type | Same speed, new time: a missing value | — |
| Which two quantities go together? | Find the pair that forms the ratio | 150 miles in 3 hours | — |
| Are the two times in the same units? | Make units match | No: convert 90 minutes to hours | Use 90 as it is → 4500 |
| Which way round does the ratio go? | Keep the same order on both sides | Miles over hours on both sides | Hours over miles on one side → 0.03 |

The graph starts at the story. The **Extract** frame holds the decisions; red dashed arrows leave a decision for each trap and run to the wrong answer it produces. The thick green arrow carries the extracted numbers into the question, drawn exactly as on the question's own page. Any follow-up step comes after, then the answer in the story's terms. The legend is at the bottom.

[![Train in minutes](v2/svg/wp-train-minutes.svg)](v2/svg/wp-train-minutes.svg)

<sub>Click the graph to open it full size · [mermaid source](v2/svg/wp-train-minutes.mmd)</sub>

| Trap | Mistake | Leads to | Caught by the answer? | Gives itself away with |
|---|---|---|---|---|
| Make units match | Uses 90 without converting minutes to hours. | 4500 | yes | `150 × 90 = 13500`, `90 ÷ 3 = 30`, `3 × 30 = 90` |
| Keep the same order on both sides | Flips one side: hours over miles. | 0.03 | yes | `3 × 1.5 = 4.5`, `1.5 ÷ 150 = 0.01` |

<a name="walk-to-school"></a>

### Walking to school

> There are 60 students in a class. 35% of them walk to school, and 10 ride bikes. How many students walk to school?

**Asked:** how many students walk (students). **Is a:** [Find a percent of a number](#percent-of). **Answer:** 21 students.

| Phrase | Value | Counts | Needed? |
|---|---|---|---|
| “60 students” | 60 students | the class | yes |
| “35% of them walk” | 35 percent | walkers | yes |
| “10 ride bikes” | 10 students | bike riders | **no** |

| Decision | Concept | Correct | Traps → wrong answer |
|---|---|---|---|
| What kind of question is this? | Recognize the question type | 35% of a group: a percent of a number | — |
| 35% of what? | Find the pair that forms the ratio | Of all 60 students | Of the 10 bike riders → 3.5 |
| What about the 10 bike riders? | Ignore numbers that don't matter | Not needed | Take them out first → 17.5 |

The graph starts at the story. The **Extract** frame holds the decisions; red dashed arrows leave a decision for each trap and run to the wrong answer it produces. The thick green arrow carries the extracted numbers into the question, drawn exactly as on the question's own page. Any follow-up step comes after, then the answer in the story's terms. The legend is at the bottom.

[![Walking to school](v2/svg/wp-walk-to-school.svg)](v2/svg/wp-walk-to-school.svg)

<sub>Click the graph to open it full size · [mermaid source](v2/svg/wp-walk-to-school.mmd)</sub>

| Trap | Mistake | Leads to | Caught by the answer? | Gives itself away with |
|---|---|---|---|---|
| Find the pair that forms the ratio | Takes 35% of the 10 bike riders. | 3.5 | yes | `10 ÷ 100 = 0.1`, `35 × 10 = 350`, `10 ÷ 10 = 1` |
| Ignore numbers that don't matter | Takes the 10 bike riders out of the class first. | 17.5 | yes | `50 ÷ 100 = 0.5`, `35 × 50 = 1750`, `50 ÷ 10 = 5` |


## Rebuilding

```sh
cd v2 && python3 build.py --demo
```

This checks every method variant against every example and every word problem against its answer; regenerates `v2/trees/`, `v2/graphs/`, the graph images in `v2/svg/` (with `mmdc`), and this report; builds the website in `docs/` (with Quarto); and runs the classifier on sample student steps.
