# Issue 006: TrustVector not validated at model construction time

## Severity
High

## Category
Omission

## Description
The PRD states "TrustVector is dict[str, float] validated against spec.yaml axis names at construction time." However, `validate_trust_vector()` is a standalone function that must be explicitly called. The `EmailChain`, `ScorerOutput`, and `GoldChain` models accept any `dict[str, float]` for `trust_vector`, `labels`, and `consensus_labels` without validating that keys match spec axis names.

This means invalid trust vectors (missing axes, extra axes, values outside [0,1]) can propagate through the system without detection until (or unless) `validate_trust_vector()` is explicitly called.

## Evidence
- File: `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/schemas.py:62-68` -- `EmailChain` has `trust_vector: dict[str, float]` with no validator
- File: `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/schemas.py:76-78` -- `ScorerOutput` has `trust_vector: dict[str, float]` with no validator
- File: `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/schemas.py:23-46` -- `validate_trust_vector()` is standalone, not called by models
- PRD Requirement: INITIAL_DESIGN_CHOICES.md "TrustVector as dict[str, float]" -- "validated against spec.yaml axis names at construction time"

## Suggested Fix
Add a pydantic model validator to `ScorerOutput` and `EmailChain` that calls `validate_trust_vector()`:
```python
from pydantic import model_validator

class ScorerOutput(BaseModel):
    trust_vector: dict[str, float]
    explanation: Explanation

    @model_validator(mode='after')
    def _validate_trust_vector(self) -> ScorerOutput:
        from autotrust.config import get_spec
        validate_trust_vector(self.trust_vector, get_spec())
        return self
```
Alternatively, keep validation external but document clearly that it must be called explicitly, and add validation calls at all trust vector creation points.

## Affected Files
- `autotrust/schemas.py`
