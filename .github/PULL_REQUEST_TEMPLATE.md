## What changed

<!-- One or two sentences. If it needs "and", it is probably two PRs. -->

## How it was verified

<!-- Commands run, pages clicked, numbers checked. Not "tested locally". -->

## Affected modules

<!-- capture / detect / review / stats / model / web / firmware / docs -->

## Documents touched

<!-- Which of these did you have to change? Tick, or write "none". The list is in docs/INDEX-en.md §4. -->
- [ ] field name or type → `data-model`, `api-contract`, mock data, SRS field table
- [ ] endpoint → `api-contract`, `api.js`, mock server, SRS module table
- [ ] metric or acceptance item → SRS §3.5 and §8, `test-plan`, `PLAN.md` P4
- [ ] class or class order → `glossary`, `species_dict`, `prepare_dataset.CLASS_CODES`, colour tokens
- [ ] hardware → `procurement`, SRS table 2-3, `PLAN.md` P1-06
- [ ] a document added, renamed or removed → `docs/INDEX-en.md` and `INDEX-zh.md`

## Checklist

- [ ] `ruff check .` and `ruff format --check .` pass
- [ ] `pytest -q` passes
- [ ] `python scripts/check-bilingual.py` passes (if docs changed)
- [ ] `python scripts/check-language.py` passes (no Chinese in English documents)
- [ ] `python scripts/check-progress.py` passes (if `PROGRESS.md` changed)
- [ ] Bilingual pairs updated in this same PR
- [ ] `docs/` updated if behaviour changed
- [ ] No weights, datasets or `.env` included
