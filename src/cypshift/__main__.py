"""Allow ``python -m cypshift`` to invoke the CLI."""

from cypshift.cli import main

raise SystemExit(main())
