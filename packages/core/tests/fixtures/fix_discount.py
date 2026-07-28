"""Fixture: a mock coding agent that fixes the discount bug.

Simulates an autonomous agent: reads the failing test, applies the
one-line fix, and reports success.
"""

import re
import sys
from pathlib import Path


def main() -> int:
    root = Path.cwd()
    target = root / "app" / "__init__.py"
    if not target.exists():
        print(f"ERROR: {target} not found", file=sys.stderr)
        return 1

    source = target.read_text(encoding="utf-8")
    fixed = source.replace("> 100  # bug: should be 50", "> 50")
    if fixed == source:
        fixed = re.sub(r">\s*100", "> 50", source)
    target.write_text(fixed, encoding="utf-8")

    print("FIXED: discount threshold changed from 100 to 50")
    return 0


if __name__ == "__main__":
    sys.exit(main())
