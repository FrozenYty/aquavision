# 04 — Static frontend with fetch, no framework

- **Status:** Accepted
- **Date:** 2026-11-03
- **Supersedes:** —

## Context

The UI needs thirteen pages, a canvas review workbench, a real-time capture view and four chart
dashboards. Vue or React would be the default choice for a team with frontend experience.

## Decision

Plain HTML, Bootstrap 5 and ES modules loaded directly by the browser. No bundler, no build step,
no node toolchain. All HTTP calls go through a single `api.js` module.

## Rationale

- **The teammate builds the UI independently.** Without a build step, pages open straight from the
  server; the frontend can be developed against mock JSON before the API is finished.
- **Review is a click, not a build.** A reviewer opens the page and sees the change; nobody has to
  install Node or resolve a lockfile.
- **The hard parts are not framework problems.** Canvas overlay, WebSocket frame handling and
  chart configuration are the same work in any stack. A framework would not reduce them.
- **Demo stability.** Fewer moving parts on the demo laptop; there is no dev server to forget to
  start.

## Consequences

- No component model: shared markup is duplicated across pages, kept consistent by `app.css` and
  the shared navigation block.
- State management is manual; each page owns its own state and re-renders explicitly.
- ES modules require a modern browser — acceptable, we target current Chrome and Edge.

## Revisit when

The UI grows past roughly twenty pages, or two people need to edit the same component
simultaneously. Neither is expected before the defence.
