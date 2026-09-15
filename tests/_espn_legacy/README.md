# Legacy ESPN tests

These tests cover the ESPN implementation that was replaced by the SofaScore
data source. They import modules that now live in
`custom_components/teamtracker/_espn_legacy/` (`event.py`, `set_*.py`,
`utils.py`) and will not run against the current integration.

They are kept here for reference only and are excluded from collection by
`pyproject.toml`. The fixtures they rely on are in `tests/tt/`.

Current tests live in `tests/sofascore/`.
