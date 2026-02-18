# Changelog

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
