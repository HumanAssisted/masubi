# Task 005: autotrust/export.py -- PyTorch/GGUF Export

## Context
The REDESIGN_AUTOSEARCH_TRD specifies that Stage 2 produces a PyTorch checkpoint that can be exported to GGUF for local deployment. Currently no export functionality exists. The PRD file layout shows `export_formats: [pytorch, gguf]` in `spec.yaml` and the execution order includes "Export: PyTorch checkpoint -> GGUF for local testing" as step 20.

## Goal
Implement `autotrust/export.py` with functions to save clean PyTorch checkpoints and convert them to GGUF format for local inference via Ollama/llama.cpp.

## Research First
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/docs/REDESIGN_AUTOSEARCH.md` lines 113-123 (Stage 3 production inference)
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/schemas.py` -- `CheckpointMeta` from TASK_002
- [ ] Read `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/student.py` -- `DenseStudent` from TASK_003
- [ ] Verify `llama-cpp-python` availability or make it optional
- [ ] Check if `spec.yaml` `stage2.export_formats` is loaded (TASK_001)

## TDD: Tests First (Red)

### Unit Tests
- [ ] Test: `test_export_pytorch_creates_file` in `tests/test_export.py` -- `export_pytorch(model, path)` creates a `.pt` file
- [ ] Test: `test_export_pytorch_loadable` -- saved checkpoint can be loaded with `torch.load()` and model reproduces same outputs
- [ ] Test: `test_export_pytorch_includes_config` -- checkpoint includes `StudentConfig` and optional `MoEConfig`
- [ ] Test: `test_export_pytorch_includes_meta` -- checkpoint includes `CheckpointMeta` (stage, composite, param_count)
- [ ] Test: `test_checkpoint_meta_roundtrip` -- `CheckpointMeta` saved in checkpoint deserializes correctly
- [ ] Test: `test_export_gguf_skips_if_unavailable` -- if `llama-cpp-python` is not installed, `export_gguf()` raises `ImportError` with helpful message
- [ ] Test: `test_list_checkpoints` -- `list_checkpoints(run_dir)` returns list of `CheckpointMeta` sorted by composite descending

## Implementation
- [ ] Step 1: Create `/Users/jonathan.hendler/personal/autoresearch-helpful/autotrust/export.py`
- [ ] Step 2: Implement `export_pytorch()`:
  ```python
  def export_pytorch(
      model: nn.Module,
      config: StudentConfig,
      meta: CheckpointMeta,
      output_path: Path,
      moe_config: MoEConfig | None = None,
  ) -> Path:
      """Save model state dict + config + meta to a .pt file."""
      checkpoint = {
          "state_dict": model.state_dict(),
          "config": config.model_dump(),
          "meta": meta.model_dump(mode="json"),
      }
      if moe_config:
          checkpoint["moe_config"] = moe_config.model_dump()
      torch.save(checkpoint, output_path)
      return output_path
  ```
- [ ] Step 3: Implement `load_pytorch()`:
  ```python
  def load_pytorch(checkpoint_path: Path) -> tuple[nn.Module, StudentConfig, CheckpointMeta]:
      """Load model from a .pt checkpoint."""
      checkpoint = torch.load(checkpoint_path, weights_only=False)
      config = StudentConfig(**checkpoint["config"])
      meta = CheckpointMeta(**checkpoint["meta"])
      # Reconstruct model
      if "moe_config" in checkpoint:
          moe_config = MoEConfig(**checkpoint["moe_config"])
          model = MoEStudent.from_config(config, moe_config)
      else:
          model = DenseStudent.from_config(config)
      model.load_state_dict(checkpoint["state_dict"])
      return model, config, meta
  ```
- [ ] Step 4: Implement `export_gguf()` (optional dependency):
  ```python
  def export_gguf(checkpoint_path: Path, output_path: Path) -> Path:
      """Convert PyTorch checkpoint to GGUF format. Requires llama-cpp-python."""
      try:
          import llama_cpp
      except ImportError:
          raise ImportError(
              "GGUF export requires llama-cpp-python. "
              "Install with: pip install llama-cpp-python"
          )
      # Load model, convert weights, write GGUF
      ...
  ```
- [ ] Step 5: Implement `list_checkpoints()`:
  ```python
  def list_checkpoints(run_dir: Path) -> list[CheckpointMeta]:
      """List all checkpoints in a run directory, sorted by composite descending."""
  ```
- [ ] Step 6: Add CLI: `uv run python -m autotrust.export --checkpoint <path> --format pytorch|gguf`
- [ ] Step 7: Add `llama-cpp-python` as optional dependency in `pyproject.toml`:
  ```toml
  [project.optional-dependencies]
  export = ["llama-cpp-python>=0.2"]
  ```
- [ ] DRY check: Use `CheckpointMeta` and `StudentConfig` from `schemas.py`; no duplicate config structures

## TDD: Tests Pass (Green)
- [ ] All new tests in `test_export.py` pass
- [ ] All existing tests still pass

## Acceptance Criteria
- [ ] `export_pytorch()` creates a loadable `.pt` checkpoint file
- [ ] `load_pytorch()` reconstructs the model and produces identical outputs
- [ ] Checkpoint includes `StudentConfig` and `CheckpointMeta`
- [ ] `export_gguf()` raises helpful `ImportError` when `llama-cpp-python` is not installed
- [ ] CLI works for PyTorch export
- [ ] No existing test is broken

## Execution
- **Agent Type**: coding subagent
- **Wave**: 2 (parallel with TASK_003, TASK_004; depends on Wave 1)
- **Complexity**: Medium
