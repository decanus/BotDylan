# Vocoder fixtures

`reference.sha256` holds the SHA-256 of the two WAVs produced by an unmodified
`tools/vocoder_reference.py` under the pinned environment in
`tools/requirements-vocoder.txt`.

Regenerate them (they are gitignored — 1.2 MB each, and derived):

    cd /tmp && .../.venv-vocoder/bin/python .../tools/vocoder_reference.py

`vocoder_render.py --compare` checks its own output against these hashes. If
they stop matching, either the engine changed or the environment did — check
`pip freeze` against the pinned versions before assuming the former.

The reference script is committed **unmodified**. It is the spec, not a
starting point: it is the thing the productionised renderer is tested against,
so editing it would make the test vacuous.
