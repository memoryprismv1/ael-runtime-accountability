# Contributing

Thanks for helping test the AEL Runtime prototype.

## Current project status

This is an experimental implementation, not the canonical AEL specification or a production-ready accountability service. Read the original source links in [`SOURCES.md`](SOURCES.md) and the current mechanism status in [`DESIGN_ALIGNMENT.md`](DESIGN_ALIGNMENT.md) before proposing changes.

## Useful contributions

- Reproducible bug reports with steps, expected behavior, actual behavior, and test output.
- Tests demonstrating a specific invariant or regression.
- Portability and usability improvements that do not weaken the context or audit boundaries.
- Suggestions that distinguish an implementation bug from a new or changed design requirement.

## Design authority and attribution

AEL's framework and source architecture belong to the author. Do not present this implementation as the origin of AEL or modify the meaning of its mechanisms under the guise of a code cleanup. Changes to the interpretation of the framework require the author's explicit review. A passing test suite demonstrates only the behavior covered by those tests; it does not prove that the full AEL design is implemented.

## Tests

The project uses the Python standard library:

```bash
python -m unittest discover -s tests -v
python -m compileall -q runtime.py ael_chat.py tests
```

Do not commit personal databases, handoffs, chat exports, API tokens, or local model data. They belong outside the source repository.
