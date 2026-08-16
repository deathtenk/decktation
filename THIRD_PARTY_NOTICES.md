# Third-party notices

Decktation's store artifact includes unmodified `ydotool` and `ydotoold`
version 1.0.4, built from commit
`57ba7d0af525e82da2de0e275d169477f293b197`.

- Source: <https://github.com/ReimuNotMoe/ydotool/tree/v1.0.4>
- License: GNU Affero General Public License v3.0 or later
- Build recipe: `backend/Dockerfile`
- Packaged license: `bin/licenses/ydotool-AGPL-3.0.txt`

The packaged runtime executable `bin/decktation-runtime` embeds Python runtime
dependencies resolved from `runtime/pyproject.toml` and locked by
`runtime/uv.lock`.
