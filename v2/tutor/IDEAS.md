# Ideas for the tutor

This file keeps ideas that are not in the current plan, `PATHS.md`. An idea moves into the plan only when
the user agrees.

## Find the node with probabilities and no Claude

The build compiles each problem into a graph of nodes. A student moves from node to node as she works. The
idea is to find her node from her text with a probability model, and to use no Claude call while she
works.

The tutor answers two separate questions for each statement:

- **Where is she?** The localization finds her node. It does not judge.
- **Is she right?** The correctness check judges her arithmetic and her reading of the story.

### Localization

```
posterior(node) ∝ prior(node) × fits(numbers, node) × softmax(similarity(text, node) / temperature)
```

- **Prior.** The prior is uniform over the reachable nodes, and zero elsewhere. A reachable node is a node
  ahead of her position on an open path, a node on a trap path, or "other". The prior needs no table and
  no data.
- **Fits.** A reader without a model pulls the numbers and operations out of the text. A node gets 1 if
  the numbers could make that node, and 0 if they could not. A text with no numbers fits every node. The
  value of the result does not count here, so a wrong result can still find its node.
- **Softmax.** A small embedding model scores the words of the text against descriptions of each node. A
  softmax over the nodes that fit turns the scores into probabilities.

If one path has most of the mass, the tutor goes on. If the mass is spread over several paths, the student
breaks the step down, as `PATHS.md` describes.

The numbers must take part in the localization. An embedding puts `18 ÷ 6 = 3` and `4 ÷ 6 = 0.67` close
together, and many statements of a student are only numbers.

### Correctness

The correctness check runs on the node that the localization found:

1. **Arithmetic.** The check computes her operation on her numbers with exact fractions, and compares the
   result she wrote. A wrong result is a slip, and the feedback gives the expected result.
2. **Value.** The check compares her result with the exact value of the node.
3. **Reading.** A node on a trap path means a misreading of the story, and the feedback names it.

The check uses no model. It is the exact match of `PATHS.md`, applied to one node.

### Terms

| Term | Meaning |
|---|---|
| node | A quantity on a path, a story decision option, or "other" for text that fits nothing. |
| reachable node | A node ahead of her position on an open path, a node on a trap path, or "other". |
| localization | Finding the node of the student. |
| prior | The chance of a node before the tutor reads the text. |
| likelihood | How well the text fits a node. |
| posterior | The chance of a node after the tutor reads the text. |
| reading | One way to turn the text into numbers and operations. A text can have more than one reading. |
| slip | The operation and the numbers fit a node, but the result is wrong. |
| temperature | A number that sets how sharp the softmax is. |

## Plan for the arithmetic

The arithmetic reader replaces the part of the Claude reader that reads numbers. It uses rules and no
model.

### Normalize the text

1. Fix common spelling errors from a word list, for example "devided" and "tims".
2. Change number words to numbers. Examples are "two thirds" to 2/3, "a dozen" to 12, "one and a half"
   to 3/2, and "1 and 7/12" to 19/12.
3. Change percents to fractions of 100, and remove units and currency signs.
4. Keep a rounded decimal as the student wrote it, so the value check can allow for the rounding.

### Find every reading

1. Split the text into numbers, operation words and equals words.
2. Map each operation word to an operation. "Times", "of", "lots of" and "groups of" mean multiply.
   "Over", "divided by", "per" and "split into" mean divide. "Goes into" means divide with the numbers
   reversed. "Double", "triple" and "half of" have a hidden second number.
3. Parse each chain into steps. For example, `4 x 18 = 72 / 6 = 12` gives two steps.
4. Parse an expression with precedence into a tree. For example, `4/6 × 18 = 12` gives one tree of two
   steps.
5. Keep every reading when the words allow more than one. For example, "6 over 4" can be a fraction or a
   division.

### Give each node its fit and its correctness

| The reading | Fits | Correctness |
|---|---|---|
| has the operation and the operands of the node | 1 | right if the result equals the value, a slip if not |
| is a bare number equal to the value of the node | 1 | right, with the path still open |
| has a tree whose leaves are givens or known quantities, and whose value equals the node | 1 | right, and the steps inside the tree become done in the head |
| has numbers that fit no node | 0, except for "other" | the arithmetic check only |
| has no numbers | 1 for every node | nothing to check |

The operands of a node are its parents in the graph. An operand can be a given, a quantity the student
already has, or a quantity on the same path. The value check uses `Number.close_to`.

### Test the reader

The eval set `tutor/evals/cases.json` has 148 cases in 15 categories. Examples of categories are
`operation_words`, `fraction_words`, `typos`, `in_head`, `rounding` and `several_steps`. The rule reader
runs on every case without an API call. The test reports the accuracy for each category, next to the
accuracy of the Claude reader from the last eval run.

## Transition priors

The prior is uniform over the reachable nodes, so there are no conditional probability tables (CPTs). A
CPT gives the chance of each next node from the current node. Static tables add numbers that nobody can
check before there are logs.

The tests for the prior are these:

- An automatic student who writes every step ends with the true node at the top of the posterior.
- An automatic student who skips steps ends with the true path above the threshold, or in a decomposition.

If the logs later show that the uniform prior asks too many decomposition questions, the prior can learn
from counts of moves. The `best_when` condition of each method can also give a starting weight.

## Plan for the words

1. Write descriptions for each node at build time. The sources are the `say` text of the step, the
   `idea` of the method and the options of each story decision.
2. Add paraphrases that a student might write. Claude writes them once, offline, and the author checks
   them. They go into the source JSON, so the build stays without a model at run time.
3. Compute the embedding of every description at build time, and store the vectors with the trees.
4. Run the embedding model on the server, so that the text of a student does not leave the server.

## Order of the work

1. Wait for logs from steps 1 to 3 of `PATHS.md`.
2. Build the arithmetic reader and compare it with the Claude reader on the eval set.
3. Build the localization with the uniform prior and the number fit, and the correctness check.
4. Add the word match, and set the temperature and the threshold from the eval.
5. Remove the Claude reader from the live tutor only if the eval shows equal accuracy.

## Open questions

- **Which embedding model.** A small model that runs on the server keeps the text private. The size of
  the model must fit the dokku server.
- **Labelled data.** The temperature and the threshold need statements with their true nodes. The eval set gives a start, and the logs give more.
- **Number words.** The rules must cover the words that students use. The `fraction_words` and
  `operation_words` categories of the eval show how many the rules miss.
