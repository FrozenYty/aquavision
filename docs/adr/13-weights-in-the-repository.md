# 13 — The delivered model lives in the repository

- **Status:** Accepted
- **Date:** 2026-11-11
- **Supersedes:** the weights clause of `CONTRIBUTING.md` section 5 and the `*.pt` / `*.onnx` lines of
  `.gitignore` — *"Weights go to GitHub Releases"*

## Context

The rule this replaces was written with a stated rationale and no number: *size is a consequence, not a
target; what decides is whether a file needs to share history with the code.* Weights, datasets, video
and generated documents were put on the far side of that line, and the delivery channel was named as
GitHub Releases.

The channel was never used. When this decision was taken the repository had **zero releases and zero
tags**, and the README carried **no download link and no checksum** — the two things the rule itself
promised. So the rule had only ever been enforced in one direction: it kept weights out of the
repository, and nothing ever put them anywhere else.

The consequence surfaced on 2026-11-11 while bringing the rig up. A machine that cloned the repository
and installed `requirements-server.txt` had no model to register, so `POST /api/detect/frames` could
answer nothing but "no model weights are registered", and the P2 acceptance — press capture, see boxes
and counts — could not be demonstrated by anyone who was not sitting at the machine that trained the
model. The `model_version` table records a `weight_path`, and `tests/test_detect_real.py` resolves a
relative path against the repository root, so the design already expected a weight file that travels
with the code; only the rule forbade it.

## Decision

A delivered version's model is **tracked in the repository**, under `models/<version_name>/`, holding
`best.pt`, `labels.txt` and `metrics.json` — the artefacts SRS section 4 says go online together.

Everything else stays out: `data/` (the runtime root, which moves with `AV_DATA_DIR`), `datasets/`,
`runs/`, video, secrets, and any weight that is not a delivered version's.

The delivered directory is at the repository root, **not** under `data/`. `data/models/` was the layout
the data model described, and it is the one place this decision deliberately departs from it: a tracked
artefact must not live under a directory whose location is a configuration value.

## Alternatives considered

**Publish to GitHub Releases, as the old rule said.** The cheaper option for the repository, and it was
the documented channel. Rejected because it had produced nothing in the project's whole lifetime: it
depends on a step in a web interface that no contributor had ever performed, and a reader cannot find a
release that does not exist. A rule whose useful half is never executed is not a policy, it is a
placeholder.

**Git LFS.** Keeps the clone small and is the textbook answer for binaries. Rejected on proportionality:
the delivered files are single-digit megabytes, LFS adds a dependency, a separate quota and a failure
mode for everyone who clones, and this project has four contributors and a few delivered versions — not
the scale LFS is for.

**External storage, linked from the README with a checksum.** Same reachability problem as Releases with
more moving parts: the link can rot, the storage belongs to someone, and the checksum is only useful to
someone who can already fetch the file.

**Leave detection undemonstrable and keep the rule.** Honest, and unacceptable: the acceptance criteria
the project is graded on require boxes on a screen.

## Consequences

- **A clean clone can run the product.** Register the version and detection works, which is what makes
  the repository an open-source project rather than a source dump.
- **The repository carries each delivered version forever.** This is the cost, and it is why the tracked
  list is exactly SRS section 4's: no intermediate checkpoints, no `last.pt`, no second format unless a
  document requires it. A delivered model is a release artefact, not a training by-product.
- **A clone grows by the size of each delivered model.** At this project's scale that is a few megabytes
  per version; if it stops being true, this decision is the one to reopen, and LFS is the alternative to
  reconsider.
- **`model_version.weight_path` stays a relative path** resolved against the repository root, so a
  registration made on one machine is valid on another. Absolute paths in that column were always the
  thing that made the weights untransportable.
- **Provenance is now part of the deliverable.** The weights are trained on DUO, which declares no
  licence of its own; the README states what the weights are, what they are not, that no DUO image is
  redistributed here, and how to cite the dataset.

## Revisit when

A delivered model outgrows single-digit megabytes, the repository passes a few hundred megabytes, or
weights start being delivered per experiment rather than per version. At that point the delivery channel
becomes a real decision again, and LFS or Releases — this time actually used — are the candidates.
