# Test plan

> Chinese version: [test-plan-zh.md](test-plan-zh.md). This file is the source of truth.

> Owner: @IkeaFyj · Revisit when: a metric or an acceptance item changes

## 1. Scope and levels

| Level | What it covers | Tool | When |
|---|---|---|---|
| Unit | Quality scoring, coordinate conversion, threshold logic | `pytest` | Every commit |
| API | Envelope, error codes, permissions, pagination | `pytest` + `httpx` | Every PR |
| End-to-end | Capture → detect → review → report | Manual script | Weekly |
| Model | mAP, per-class recall, counting deviation | `scripts/train_baseline.py` | Each model version |

Coverage is not a target. The rule is simpler: **any module with a branch that can silently
produce a wrong number must have a test.** That means quality scoring, coordinate conversion,
deduplication and statistics — not CRUD endpoints.

## 2. Datasets and splitting

| Role | Source | Size | Used for |
|---|---|---|---|
| Train | Public underwater dataset | ≥ 3000 images | Fitting |
| Validation | Held out from train | 10–15% | Epoch and threshold selection |
| **Test** | Held out, frozen | ≥ 500 images | Reported metrics only |
| Demo | Self-captured in the tank | 200–400 frames | Live demo and E4 fine-tuning |

**Split by video or session, never by frame.** Adjacent frames are near-duplicates; splitting them
randomly inflates mAP by a wide margin. After splitting, run a perceptual-hash check and drop any
test image that is visually identical to a training image.

The test set is frozen once. The manifest (`test-manifest.txt`, one `filename md5` per line) is
committed; the images themselves are not.

## 3. Metrics and acceptance

| ID | Metric | Target | Measured on |
|---|---|---|---|
| AL-01 | mAP@0.5, four species | ≥ 0.75 | Frozen test set |
| AL-02 | mAP@0.5:0.95 | ≥ 0.45 | Frozen test set |
| AL-03 | Per-class recall | all four ≥ 0.75 | Frozen test set |
| AL-04 | Improvement over baseline | mAP@0.5 +0.03 | Same data, epochs and seed |
| AL-05 | Inference speed | ≥ 90% of baseline | 100 images, same hardware |
| AL-06 | Parameter growth | ≤ 20% | Model summary |
| AL-07 | Counting deviation | ≤ 15% | Three 3-minute videos, manual count |

A single +0.03 margin sits close to run-to-run noise on a 500-image test set. Run the baseline and
the improved model with three seeds and report mean ± standard deviation.

## 4. Test data and fixtures

- Committed fixtures do not exist yet. The capture tests synthesise what they need in code — a
  sharp noise frame, a blurred copy of it, a flat frame and a blue-cast frame — and write the JPEGs
  they need into `tmp_path`; deterministic generation is why no fixtures are necessary.
- No test may open a real camera. Capture is mocked through a fixture that returns frames.
- Tests that need a database use a temporary SQLite file, created and dropped per session.

## 5. Tools and commands

```
ruff check .            # lint
ruff format --check .   # formatting
pytest -q               # all tests
python scripts/train_baseline.py   # train, then evaluate on the frozen test split
python scripts/check-bilingual.py
```

Evaluation is not separated from training yet. `scripts/train_baseline.py` trains the baseline and
then evaluates the best weights on the frozen test split, writing `metrics.json` into the run
directory; `scripts/register_model.py` reads that file and writes the `model_version` row, so a
version and its numbers are never separated.

## 6. Defect handling

| Level | Meaning | Rule |
|---|---|---|
| Blocker | System unusable, data loss, metrics unmet | Fixed before submission |
| Major | Core path blocked, permission bypass | Fixed before submission |
| Minor | Cosmetic, non-critical page | At most 5 open, listed with an owner |

A model that misses its metric target is a blocker. Lowering the threshold to pass is not an
acceptable fix; the experiment record must show what was tried.
