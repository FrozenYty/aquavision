# 06 — Training data comes from DUO, not URPC

- **Status:** Accepted
- **Date:** 2026-11-04
- **Supersedes:** —

## Context

The SRS named URPC (the underwater robot picking contest dataset) in its reference list, its
milestone plan and its risk table. Lane B built the training pipeline on DUO instead, because URPC
could not be obtained and DUO ships the same four species in a cleaner form.

Both cover holothurian, echinus, scallop and starfish. They differ in size, annotation discipline
and — most importantly — in whether a canonical test split exists.

## Decision

Use DUO (`github.com/chongweiliu/DUO`) as the only source of public training and evaluation data.

## Rationale

- **Size.** 7782 images with an official split and a 1111-image test set. The plan requires at least
  3000 training images and 500 test images; a single URPC edition does not reach 3000, and stitching
  two editions together mixes annotation standards.
- **Annotation quality.** DUO was built by re-cleaning and relabelling existing underwater sets into
  one COCO standard. URPC annotations vary between editions, which makes a mAP figure depend on
  which edition was used.
- **Reproducibility.** DUO ships a fixed test split. URPC has no canonical one, so a number produced
  on a self-made split cannot be compared with anything, including our own earlier runs.
- **Format.** COCO JSON out of the box; `scripts/prepare_dataset.py` reads it without conversion.

## Consequences

- **Never mix URPC into training.** DUO images overlap URPC. Mixing them puts near-duplicate frames
  on both sides of the split and silently inflates mAP — a failure nobody notices until review.
- Published URPC numbers are not comparable with ours; we report our own baseline only.
- DUO covers four species. Marine debris was dropped from scope rather than sourced elsewhere: a
  class evaluated on a different dataset would break the single-benchmark story the other four
  depend on. Recorded in SRS annex B V1.3.

## Revisit when

An advisor requires URPC specifically, or a cross-dataset comparison is needed to show the model is
not overfitted to one collection. Either would be a new ADR, not an edit to this one.
