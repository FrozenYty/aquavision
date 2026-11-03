## What changed

<!-- One or two sentences. If it needs "and", it is probably two PRs. -->

## How it was verified

<!-- Commands run, pages clicked, numbers checked. Not "tested locally". -->

## Affected modules

<!-- capture / detect / review / stats / model / web / firmware / docs -->

## Checklist

- [ ] `ruff check .` and `ruff format --check .` pass
- [ ] `pytest -q` passes
- [ ] `python scripts/check-bilingual.py` passes (if docs changed)
- [ ] Bilingual pairs updated in this same PR
- [ ] `docs/` updated if behaviour changed
- [ ] No weights, datasets or `.env` included
