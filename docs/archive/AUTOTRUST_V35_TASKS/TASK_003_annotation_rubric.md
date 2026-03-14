# Task 003: Write annotation_rubric.md

## Context
The annotation rubric MUST be written BEFORE any data generation. It defines the semantics of every trust axis so that human annotators (2-3 per chain) label consistently. Without this, gold-set annotations will be unreliable and Kappa scores will be low. See CURSOR_PLAN.md "Implementation Details > 2. annotation_rubric.md".

## Goal
Create a comprehensive annotation rubric document that enables consistent human labeling across all 10 trust axes.

## Research First
- [ ] Read CURSOR_PLAN.md section "Implementation Details > 2. annotation_rubric.md"
- [ ] Read `spec.yaml` trust_axes for the full axis list with types (binary vs continuous)
- [ ] Understand the distinction: binary axes (phish, verify_by_search) need clear 0/1 criteria; continuous axes need 0.0/0.5/1.0 anchor examples

## TDD: Tests First (Red)
No code tests for this task (documentation only).

## Implementation
- [ ] Step 1: Create `annotation_rubric.md` at project root with the following structure:

  **Section 1: Overview**
  - Purpose of annotation, number of annotators, scoring independently

  **Section 2: Binary Axes** (for each: definition, 0 criteria, 1 criteria, edge cases)
  - `phish`: What constitutes phishing (0 = legitimate, 1 = phishing attempt)
  - `verify_by_search`: When to flag for external verification (0 = self-contained, 1 = claims require search)

  **Section 3: Continuous Axes** (for each: definition, examples at 0.0, 0.5, 1.0, boundary conditions)
  - `truthfulness`: factual accuracy spectrum
  - `manipulation`: emotional/psychological manipulation (distinguish legitimate urgency from manipulative urgency)
  - `deceit`: hidden intent, misdirection
  - `vulnerability_risk`: exploitation of recipient's situation
  - `subtle_toxicity`: implicit toxicity, microaggressions
  - `polarization`: zero-sum framing, emotional blackmail
  - `classic_email_metrics`: spam signals, formatting, professionalism
  - `authority_impersonation`: false authority claims (distinguish friendly authority from impersonation)

  **Section 4: Edge Cases**
  - Multi-intent emails (score each axis independently)
  - Sarcasm/humor (score the surface intent AND the likely interpretation)
  - Cultural context (note when cultural norms affect interpretation)
  - Thread context (later emails in a chain can change meaning of earlier ones)

  **Section 5: Annotator Instructions**
  - Score each axis independently; do not let one axis bias another
  - Document uncertainty with a note field
  - Flag ambiguous chains for discussion
  - Inter-annotator calibration: first 20 chains scored jointly, then independently

## TDD: Tests Pass (Green)
- [ ] Document is complete and covers all 10 axes

## Acceptance Criteria
- [ ] `annotation_rubric.md` exists at project root
- [ ] All 10 trust axes have definitions with concrete examples
- [ ] Binary axes have clear 0/1 criteria
- [ ] Continuous axes have anchor examples at 0.0, 0.5, 1.0
- [ ] Edge case section covers multi-intent, sarcasm, cultural context, thread context
- [ ] Annotator instructions include calibration process

## Execution
- **Agent Type**: python (content generation)
- **Wave**: 1 (parallel with TASK_001, TASK_002)
- **Complexity**: Medium
