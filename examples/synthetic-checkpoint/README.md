# AEL checkpoint example — synthetic fixture

**This is NOT a real AEL session export.** No live AEL installation, database, machine, or user history was accessed. Every event and identifier in this folder is invented solely to show the two portable output shapes.

The format follows the current checkpoint design in `ael/checkpoints.py` and `ael/context.py` of [AEL Runtime Accountability](https://github.com/memoryprismv1/ael-runtime-accountability): one human-readable Markdown projection and one machine-readable JSON payload for the same account/project/chat scope. The JSON retains the full excluded event content; the Markdown only displays its event identity/status and a short content digest.

Use the JSON for machine-readable audit inspection. Keep the Markdown alongside it as the reading copy. Check the adjacent SHA-256 file before relying on either file.

The IDs use `SYNTHETIC` deliberately. These files must never be counted as real AEL history or evidence that AEL was deployed or used.
