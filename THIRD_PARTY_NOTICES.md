# Third-party code

## TuViMCP / ansaotuvi engine

This project vendors the deterministic chart and star-placement engine from:

- Repository: https://github.com/nmhaaa3218/TuViMCP
- Author: Manh Ha Nguyen / nmhaaa3218
- License: MIT License
- Pinned commit: `667c68f564e135cae207df3471273f639fa2feb4`

The engine is kept inside this repository under `vendor/tuvi_mcp`. The application imports it through `vendor.tuvi_mcp` and does not import the external/root `tuvi_mcp` package.

The upstream copyright and MIT licensing terms remain applicable to the vendored source.
