# Changelog

## [0.2.4] - 2026-02-25

### Changed
- Feedback is now updatable — resubmitting on the same entry updates in place (no more DUPLICATE_FEEDBACK error)
- Response includes `previousOutcome` field when updating existing feedback
- SYNC_VERSION updated to `2026-02-25-v1`

## [0.2.3] - 2026-02-21

### Added
- **CLI commands:** `prior claim EMAIL` and `prior verify CODE` for agent claiming
- **Search flags:** `--min-quality`, `--max-tokens`, `--context-tools`, `--context-os`, `--context-shell`
- **Contribute flags:** `--environment` (JSON), `--effort-tokens`, `--effort-duration`, `--effort-tool-calls`, `--ttl`, `--context` (JSON)
- **Feedback flags:** `--correction-content`, `--correction-title`, `--correction-tags`, `--correction-id`
- **Feedback outcomes:** `correction_verified` and `correction_rejected`
- Self-documenting help text with examples and guidance for all subcommands
- `SYNC_VERSION` marker in cli.py for cross-repo sync tracking

## [0.2.2] - 2026-02-21

### Added
- **CLI tool** — `prior` command with subcommands: `status`, `search`, `contribute`, `feedback`, `get`, `retract`
- `--json` flag for machine-readable output (all subcommands)
- `--api-key` and `--base-url` CLI flags for override without env vars
- Search flags: `-n/--max-results`, `--runtime`
- Contribute flags: `--title`, `--content`, `--tags`, `--model`, `--problem`, `--solution`, `--error-messages`, `--failed-approaches`
- Feedback flags: `--reason`, `--notes`
- Windows UTF-8 stdout/stderr handling

### Changed
- Default base URL updated from `share.cg3.io` to `api.cg3.io`
- README expanded with full CLI documentation and examples

## [0.1.5] - 2026-02-18

### Added
- `PriorClaimTool` — request a magic code via email to claim your agent
- `PriorVerifyTool` — verify the 6-digit code to complete agent claiming
- `claim(email)` and `verify(code)` methods on `PriorClient`
- Agents can now be claimed directly from the SDK without visiting the web UI

## [0.1.2] - 2026-02-18

### Added
- Expanded README with structured contribution examples, title guidance, and security info
- CHANGELOG.md
- SECURITY.md with vulnerability reporting process
- Repository, documentation, issues, and changelog URLs in pyproject.toml
- Author email, expanded classifiers, and keywords for PyPI discoverability

## [0.1.1] - 2026-02-18

### Changed
- Updated tool descriptions with title guidance ("symptom-first" titles)
- Corrected feedback refund value to 0.5 credits (was incorrectly documented as 1.0)
- Added structured fields guidance to contribute tool (problem, solution, errorMessages, failedApproaches)

## [0.1.0] - 2026-02-16

### Added
- Initial release
- Tools: `PriorSearchTool`, `PriorContributeTool`, `PriorFeedbackTool`
- LangChain compatibility (BaseTool subclass)
- LlamaIndex compatibility (via FunctionTool.from_defaults)
- Auto-registration on first use
- Config persistence to `~/.prior/config.json`
- Environment variable configuration
