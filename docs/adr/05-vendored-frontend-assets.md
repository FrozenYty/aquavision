# 05 — Frontend libraries and fonts are vendored, no CDN at runtime

- **Status:** Accepted
- **Date:** 2026-11-04
- **Supersedes:** —

## Context

ADR 04 settles on Bootstrap 5, ECharts 5 and plain ES modules with no build step. It does not say
where those files come from. The usual shortcut is a CDN `<link>` or `<script>`, which needs the
network every time a page loads.

Architecture §1 puts "works offline, on a laptop, without network configuration" among the three
design goals, and the defence room's network is not under our control.

## Decision

Every third-party file a page loads is committed under `web/static/` and served by our own process:

- `web/static/vendor/<library>-<version>/` — Bootstrap 5.3.3 today; ECharts 5 joins when the chart
  pages land.
- `web/static/fonts/` — Latin-only subsets of Saira Condensed and JetBrains Mono (@fontsource
  5.3.0), each with its SIL OFL licence beside it. Chinese text uses the system font stack.

No page references an external URL for code, styles or fonts.

## Rationale

- **Offline demo.** Pulling the network cable does not change how a page looks or behaves.
- **Versions are pinned by the path.** `bootstrap-5.3.3/` cannot drift the way an unversioned or
  `@5` CDN URL can, and the version is visible in every diff that touches it.
- **No lockfile, no toolchain.** Consistent with ADR 04: nobody installs Node to get the
  dependencies; cloning the repository is enough.
- **Small.** About 0.4 MB today and roughly 1.5 MB with ECharts, well under the 20 MB limit in
  `CONTRIBUTING.md`.

## Consequences

- Upgrading a library is a manual step: download the new version into a new versioned folder,
  update the references, delete the old folder, in one PR.
- Minified vendor files are reviewed by source and version, not line by line.
- Fonts stay Latin-only; a full Chinese web font (several MB) is out of scope.
- Licence files travel with the assets they cover.

## Revisit when

The demo machine is guaranteed a network connection, or a build step is introduced (which would
first require superseding ADR 04).
