#!/usr/bin/env python3
"""
Import glossary terms from CSV into backend/app/data/dialects/*.json.
"""
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from scripts.import_glossary import main

if __name__ == "__main__":
    main()
