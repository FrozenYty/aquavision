# 08 — Four tables added, and the nine-table decision revised

- **Status:** Accepted
- **Date:** 2026-11-06
- **Supersedes:** the nine-table merge recorded in SRS V1.1 §4.1 (site, annotation, dataset-version,
  alert and training-job tables removed; dataset snapshot and training parameters merged into
  `train_experiment`)

## Context

SRS V1.1 cut five tables and merged the dataset snapshot and the training parameters into
`train_experiment`. That decision was right for the tables it removed: a site is a column, annotation
moved to an offline tool, an alert is a message. The merge rested on one assumption, though — that a
dataset snapshot and its training parameters only ever exist inside an experiment.

Building the `P1-02` skeleton disproved it three times:

1. **A snapshot exists before the experiment that consumes it.** The export page produces `DS-V3`
   today; training runs next week. Between those two moments no `train_experiment` row references the
   snapshot, so it has nowhere to live, and the export page cannot list what it just produced.
2. **A report history is a query, not a directory.** FR-M5-04 and AC-22 filter history by period,
   template and basis. A folder of files cannot be filtered; the audit log records that something
   happened, not what it was about.
3. **Parameters must persist and stay auditable.** FR-M7-01 and AC-27 require a changed concurrency
   limit to constrain later jobs and to show its before and after values. Environment variables are
   read at start-up and audited by whoever edited the file.

Two further facts settled the direction. `AC-09` says a cleaned-up frame must leave its references
**nulled** — a file reference cannot be nulled, only a column can. And the model already stores binary
artefacts as *row plus path*: `model_version.weight_path`, `media_asset.file_path`. A report and a
dataset are the same shape as a weight file, not an exception to it.

## Decision

Add four tables and revise SRS §4.1 to thirteen.

- **`dataset`** — one exported snapshot: name, split ratio, seed, size, manifest path, status.
- **`dataset_item`** — one frame in one snapshot and its split. Membership is a table rather than a
  JSON list because three questions are joins: which frames trained this model, may this frame be
  cleaned up, and do similar frames still stay on one side of a split (AC-18). `group_key` carries the
  grouping.
- **`report`** — period, template, basis, model version, file path, status. The document stays a file;
  the row is what makes it queryable.
- **`sys_param`** — key/value with a `value_type` and an audit column. Key/value rather than one column
  per setting, so adding a parameter never needs a migration.

`train_experiment.dataset_snapshot` stays as it is: it is a string reference to a snapshot, and it
continues to be the field the training page reads.

## Alternatives considered

**Files plus the audit log** — snapshots as `manifest.json`, reports as documents, history read from
`sys_log`. Nothing to migrate, and the SRS's nine-table claim survives. Rejected because it
re-implements a database badly: every later feature (filter reports by period, list datasets with
counts, show a parameter's history) becomes a directory scan, and none of them can enforce that a
snapshot still points at frames that exist.

**Three tables, membership in the manifest** — cheaper by one table. Rejected: it gives up the join
that answers "which frames trained this model", which is the traceability AC-35 is about, and it
re-introduces the dangling-reference problem AC-09 names.

**Do nothing, keep answering 501** — honest in the short term and wrong in the long one. These are
three P1 requirements; they will be built, and building them later against the wrong shape costs more
than a schema decision now.

## Consequences

- SRS rises to V1.5; the data model, the README and the twelve-table references move with it in the
  same change. The revision history records what changed and why.
- `EXPECTED_COLUMNS` grows to thirteen entries, so a column added on one side only fails a test.
- The database is still created from scratch by `scripts/init_db.py`; there is no migration tool, and
  none is needed until a deployed database must survive a schema change. Any existing development
  database is deleted and rebuilt — it holds no data that cannot be re-captured.
- The status codes inside these tables (dataset 0/1/2, report 0/1/2, split 1/2/3) follow the existing
  convention of `SMALLINT` codes documented in the field dictionary rather than a database enum.
