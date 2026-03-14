# Task 014: Write program.md -- Agent Instruction Set

## Context
`program.md` is the tiny instruction set that the research agent (Sonnet) reads at each loop iteration. It tells the agent the rules: only edit train.py, budget constraints, the three-gate policy, the structured explanation contract, and experiment priorities. It must be concise but complete enough for the agent to make good decisions. See CURSOR_PLAN.md "Implementation Details > 11. program.md".

## Goal
Create a concise, complete instruction document for the autoresearch agent that clearly communicates the three-gate policy and structured output contract.

## Research First
- [ ] Read CURSOR_PLAN.md section "Implementation Details > 11. program.md" (the full program.md content is provided verbatim)
- [ ] Read spec.yaml for current limits, provider models, and thresholds
- [ ] Read CURSOR_PLAN.md "Key Policy Decisions" for three-gate explanation

## TDD: Tests First (Red)
No code tests (documentation only).

## Implementation
- [ ] Step 1: Create `program.md` at project root with the exact content from CURSOR_PLAN.md section 11, which includes:
  - Role statement: "optimizing a content-only email trust scorer"
  - Rule: only edit train.py
  - Budget: references spec.yaml limits
  - Base model: references spec.yaml providers.scorer
  - Three-gate keep/discard policy:
    1. Composite score must improve (Kappa-adjusted)
    2. Gold-set veto: no axis may degrade (raw labels, all axes including zero-weighted)
    3. Explanation gate: quality >= 0.5 after baseline
  - Gold-set veto absolute authority explanation
  - Structured JSON output contract (trust_vector + explanation with reasons array)
  - Trust axes from spec.yaml
  - Experiment priorities (thread encoder -> multi-task heads -> explanation reasons -> LoRA)

## TDD: Tests Pass (Green)
- [ ] Content matches specification

## Acceptance Criteria
- [ ] `program.md` exists at project root
- [ ] Contains three-gate policy description
- [ ] Contains structured output contract
- [ ] References spec.yaml for dynamic values (limits, models)
- [ ] Experiment priority list present
- [ ] Concise (fits in one screen)

## Execution
- **Agent Type**: python (content writing)
- **Wave**: 5 (depends on spec.yaml; parallel with TASK_013)
- **Complexity**: Low
