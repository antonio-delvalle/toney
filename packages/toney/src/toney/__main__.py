"""Allow ``python -m toney`` to start the terminal UI."""

from toney.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
