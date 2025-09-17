from __future__ import annotations

import os
import sys

if __name__ == "__main__":
    # Allow `python run.py [args...]` to behave like `python -m src.main [args...]`
    from src.main import main
    sys.exit(main())
