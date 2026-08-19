# Third-party code

## TuViMCP / ansaotuvi engine

This project integrates the deterministic chart and star-placement engine from:

- Repository: https://github.com/nmhaaa3218/TuViMCP
- Author: Manh Ha Nguyen / nmhaaa3218
- License: MIT License
- Pinned commit: `667c68f564e135cae207df3471273f639fa2feb4`

The upstream project is installed as a pinned Python dependency and is exposed to this application through `tuvi_lap_so_engine.py`. The adapter converts the upstream object model to the application's clean JSON schema.

The upstream copyright and MIT licensing terms remain applicable to the integrated dependency.
