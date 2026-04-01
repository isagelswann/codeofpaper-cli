# Changelog

## 0.1.1 — 2026-04-01

### Added

- `--ca-bundle` flag, `CODEOFPAPER_CA_BUNDLE` env var, and `ca_bundle` config key for custom TLS certificate bundles. Fixes SSL errors behind corporate proxies that perform TLS inspection.
- `--timeout` flag and `CODEOFPAPER_TIMEOUT` env var (default: 30s, was 10s).
- Documentation for corporate proxy / custom TLS setup in README.

### Fixed

- `status` command now reads correct API response keys (`status`, `services.database`, `services.redis`, `paper_count`).

## 0.1.0 — 2026-03-18

Initial release.
