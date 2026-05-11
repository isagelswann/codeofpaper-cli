# Changelog

## 0.1.3 — 2026-05-11

### Added

- `search` command: `--year`, `--after`, `--before`, `--venue` filters matching the API. `--after` / `--before` accept `YYYY` (expanded to Jan 1 / Dec 31) or `YYYY-MM-DD`.
- Per-phase HTTP timeouts: connect phase capped at 10s (or `--timeout`, whichever is lower) so corporate networks that black-hole packets fail fast instead of hanging until the global timeout.

### Fixed

- More precise error messages for connect-vs-read timeouts; connect failures now suggest checking network/proxy or passing `--api-url`.

## 0.1.2 — 2026-04-01

### Added

- `--timeout` flag and `CODEOFPAPER_TIMEOUT` env var (default: 30s, was 10s).

### Fixed

- `status` command now reads correct API response keys (`status`, `services.database`, `services.redis`, `paper_count`).

## 0.1.1 — 2026-04-01

### Added

- `--ca-bundle` flag, `CODEOFPAPER_CA_BUNDLE` env var, and `ca_bundle` config key for custom TLS certificate bundles. Fixes SSL errors behind corporate proxies that perform TLS inspection.
- Documentation for corporate proxy / custom TLS setup in README.

## 0.1.0 — 2026-03-18

Initial release.
