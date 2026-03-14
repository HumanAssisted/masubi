# Task 007: Build providers/ollama.py -- OllamaGenerator

## Context
The Ollama provider implements `GeneratorProvider` for local LLM generation using Dolphin 3.0 (or other local models). It's used for synthetic email chain generation in the data pipeline. It wraps the `ollama` Python package and includes a `check_available()` method that verifies the daemon is running and the model is pulled. See CURSOR_PLAN.md "Implementation Details > 5. providers/ > providers/ollama.py".

## Goal
Implement a concrete `GeneratorProvider` that generates text via the local Ollama daemon.

## Research First
- [ ] Read CURSOR_PLAN.md section on `providers/ollama.py`
- [ ] Read `autotrust/providers/__init__.py` (TASK_006) for GeneratorProvider interface
- [ ] Check `ollama` Python package API: `ollama.chat()`, `ollama.list()`, `ollama.pull()`
- [ ] Read spec.yaml `providers.generator` for default model name

## TDD: Tests First (Red)
Write tests FIRST. They should FAIL before implementation.

### Unit Tests (all in `tests/test_providers.py`, using mocks)
- [ ] Test: `test_ollama_generate_returns_string` -- mock ollama.chat, verify generate() returns string response -- in `tests/test_providers.py`
- [ ] Test: `test_ollama_generate_batch` -- mock ollama.chat, verify generate_batch() returns list of strings with correct length -- in `tests/test_providers.py`
- [ ] Test: `test_ollama_check_available_true` -- mock ollama.list to return model, verify check_available() returns True -- in `tests/test_providers.py`
- [ ] Test: `test_ollama_check_available_false` -- mock ollama.list to raise ConnectionError, verify check_available() returns False -- in `tests/test_providers.py`
- [ ] Test: `test_ollama_uses_spec_model` -- verify OllamaGenerator uses model name from spec.yaml config -- in `tests/test_providers.py`

## Implementation
- [ ] Step 1: Create `autotrust/providers/ollama.py` with class `OllamaGenerator(GeneratorProvider)`:
  - `__init__(self, model: str)`: store model name
  - `generate(self, prompt: str, **kwargs) -> str`: call `ollama.chat(model=self.model, messages=[{"role": "user", "content": prompt}])`, return `response["message"]["content"]`
  - `generate_batch(self, prompts: list[str], concurrency: int = 4) -> list[str]`: sequential calls to generate() (can be upgraded to async later)
  - `check_available(self) -> bool`: try `ollama.list()`, check if self.model is in the list, return True/False. Catch ConnectionError -> False
- [ ] Step 2: Register OllamaGenerator in `get_provider()` factory for backend="local_ollama"
- [ ] DRY check: retry and logging handled by BaseProvider, not re-implemented here

## TDD: Tests Pass (Green)
- [ ] All 5 new tests pass
- [ ] All existing tests still pass

## Acceptance Criteria
- [ ] `autotrust/providers/ollama.py` exists with OllamaGenerator class
- [ ] Implements all GeneratorProvider abstract methods
- [ ] `check_available()` handles daemon-not-running gracefully
- [ ] Registered in `get_provider()` for "local_ollama" backend
- [ ] All tests pass

## Execution
- **Agent Type**: python
- **Wave**: 3 (depends on TASK_006 providers registry)
- **Complexity**: Low
