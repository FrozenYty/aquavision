# Documentation index

> Chinese version: [INDEX-zh.md](INDEX-zh.md). This file is the source of truth.

> Owner: @FrozenYty · Revisit when: a document is added, renamed or removed

One page that answers three questions: which document answers what, which one wins when two of them
disagree, and which other files have to change when you touch one. Read this before opening anything
else.

## 1. Where to start

Two layers. The test is one question: **will this file change next week?**

| Layer | Holds | Rule |
|---|---|---|
| repository root | `README`, `README-zh`, `AGENTS`, `CONTRIBUTING`, `LICENSE`, `PLAN`, `PROGRESS` | yes — entry points and live state |
| `docs/` | everything else | no — reference material, every file in an `-en` / `-zh` pair |

`PLAN.md` and `PROGRESS.md` sit at the root because they change daily; that is also why they are the
only single-language files above the line. Within `docs/`, the fastest route is this table:

| You want to | Read |
|---|---|
| work in this repository for the first time | `README.md`, then `CONTRIBUTING.md` |
| know what is being built and how it is judged | `srs-en.md` — §3 requirements, §8 acceptance |
| pick up a task | `PLAN.md` for the contract, `PROGRESS.md` for why it moved |
| understand how the system is shaped | `architecture-en.md`, then the ADR that touches it |
| call or serve an API | `api-contract-en.md` |
| add a table or a column | `data-model-en.md` |
| buy or wire hardware | `procurement-en.md` |
| know what the prototype shows | `prototype-en.md` |
| name a thing consistently | `glossary-en-zh.md` |
| know why a decision was made | `adr/` |

## 2. The map

| Document | Answers | Changes when | Owner |
|---|---|---|---|
| `srs-en/zh.md` | what the system does, how it is accepted | a requirement or an acceptance item changes | @FrozenYty |
| `architecture-en/zh.md` | layers, dependency direction, runtime model | the shape changes, not the code | @FrozenYty |
| `api-contract-en/zh.md` | endpoint paths, envelope, error codes, WebSocket | an endpoint or a field changes | @Gtechson |
| `data-model-en/zh.md` | tables, columns, indexes, file layout | a table or column changes | @Gtechson |
| `test-plan-en/zh.md` | levels, datasets, metrics, defect classes | a metric or acceptance item changes | @IkeaFyj |
| `prototype-en/zh.md` | what the 11-06 walkthrough shows, screen by screen | the prototype is replaced by the real slice | @chemflowers |
| `procurement-en/zh.md` | what to buy, why these parts, how to accept them | hardware changes | @FrozenYty |
| `copy-review-en/zh.md` | findings on the interface copy, by page | the copy is rewritten or the page set changes | @FrozenYty |
| `test-cases-en/zh.md` | one case per acceptance item, and how to run it | an acceptance item changes, or a case is executed | @IkeaFyj |
| `glossary-en-zh.md` | the one word for each concept | a new concept appears | @FrozenYty |
| `adr/01-06` | why a decision was taken and when to revisit it | never edited; superseded instead | the author of that ADR |
| `PLAN.md` | phases, tasks, gates | a task is delivered or re-scoped | every lane |
| `PROGRESS.md` | what happened and why it moved | continuously, append only | whoever did the work |

## 3. When documents disagree

Each document is authoritative over its own subject, and none of them is authoritative over all of
them:

- **acceptance** — the SRS wins;
- **endpoint shape** — `api-contract` wins, even where the SRS describes the same call in prose;
- **table structure** — `data-model` wins;
- **layering and dependency direction** — `architecture` wins;
- **history** — `PROGRESS` wins, but it never describes the present.

If the disagreement comes from a decision that changed, fix the documents, not your memory. If it
comes from a decision nobody made yet, make it, record it in `PROGRESS`, and raise an ADR if it is
expensive to reverse.

## 4. Where a change lands

A change is rarely local. This is the list that keeps `grep` from being the only defence:

| If you change | Also update |
|---|---|
| a field name or type | `data-model`, `api-contract`, the mock data, the SRS field list |
| an endpoint | `api-contract`, `api.js`, the mock server, the SRS module table |
| a metric or acceptance item | SRS §3.5 and §8, `test-plan`, `PLAN.md` P4 |
| a class or its order | `glossary`, `species_dict` seed, `prepare_dataset.CLASS_CODES`, the frontend colour tokens |
| hardware | `procurement`, SRS table 2-3, `PLAN.md` P1-06 |
| a phase boundary | `PLAN.md`, `PROGRESS.md`, and this index if a document was added |
| anything with a doc pair | both languages, in the same commit |

## 5. Documents that do not exist yet

Planned, and deliberately absent until the phase that needs them:

| Document | Appears at |
|---|---|
| database DDL note | P1-01 |
| demo script and screenshots | P4-06 |
| metric report | P4-04 |

Writing them early would mean writing them twice.

## 6. Keeping this index honest

Pairs are written 
ame-en/zh.md above; both files exist and both are kept in step by CI.

A document that is not in the map above does not exist as far as the team is concerned. Adding,
renaming or deleting a document means editing this page in the same commit; the pull request template
asks for it.
