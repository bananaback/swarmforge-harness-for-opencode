# Prompting Guide: What Actually Works (and What's Overhyped)

Distilled from an AI engineer's 6 months of testing prompting techniques across
GPT-4, Claude, and Gemini, documenting hundreds of hours of results.

## TL;DR

1. **Chain-of-thought still reigns supreme** — but only when scaffolded correctly.
2. **Role prompting alone is weak** — combine it with persona + goal + constraint.
3. **XML tags outperform markdown** in structured prompts by ~30% accuracy.
4. **Negative examples ("don't do X") are underused** and wildly effective.
5. **Prompt chaining beats mega-prompts** almost every single time.

---

## 1. Chain-of-Thought — Add a "Reasoning Scaffold"

**The technique:** Don't just say "think step by step." Give the model a
structured scaffold: observation → hypothesis → test → conclusion. This forces
it to actually reason instead of pattern-matching to a confident-sounding
answer.

**Before:**

```
Solve this. Think step by step.
```

**After:**

```
Before answering, work through this:
<observation>What do I know for certain?</observation>
<hypothesis>What's my best guess and why?</hypothesis>
<test>What would disprove my hypothesis?</test>
<conclusion>Given the above, my answer is...</conclusion>
```

---

## 2. The "Persona + Goal + Anti-goal" Triple

**The technique:** Most people only define the persona. Combine it with an
explicit goal AND an anti-goal. The anti-goal is where the magic happens — it
steers the model away from its default failure mode.

**Weak:**

```
You are an expert editor.
```

**Strong:**

```
You are a sharp developmental editor at a top literary agency.
Goal: Help writers find the structural weaknesses in their argument.
Anti-goal: Do NOT rewrite their sentences. Surface issues, don't fix them.
```

---

## 3. XML Tags Over Markdown for Structured Inputs

**Why it works:** Markdown is ambiguous — a `##` heading might be rendered or
raw text depending on context. XML tags create unambiguous delimiters. On
structured extraction tasks, switching from markdown headers to XML tags
measured ~28% fewer errors.

---

## 4. Contrastive Examples (the Underused Gem)

**The technique:** Show what you DON'T want alongside what you do want. Models
learn boundaries far better from contrast than from positive examples alone.
One negative example often beats three positive ones.

```
Good response: "The data suggests a 12% uplift in retention."
Bad response: "The data shows we did amazingly well and retention skyrocketed!"

Match the tone of the good response — precise, qualified, no hype.
```

---

## 5. Prompt Chaining Over Mega-Prompts

**The technique:** A 3000-token mega-prompt usually underperforms three
500-token chained prompts where each step feeds the next. Decompose. The
model's attention is finite — don't compete for it with 10 instructions at
once.

---

## Quick Reference

| Technique | Do this | Not this |
| --- | --- | --- |
| Chain-of-thought | Structured scaffold (observation → hypothesis → test → conclusion) | "Think step by step" |
| Role prompting | Persona + goal + anti-goal | Persona only |
| Structured input | XML tags | Markdown headings |
| Examples | Good + bad (contrastive) | Positive examples only |
| Complex tasks | Chained prompts (each feeds the next) | One giant mega-prompt |

---

*Source: u/LoadOld2629, r/PromptEngineering — "I spent 6 months testing every
major prompting technique. Here's what actually works (and what's overhyped) —
with real examples." Accuracy figures are the author's self-reported test
results, not independently verified.*
