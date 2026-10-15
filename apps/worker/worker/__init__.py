"""CommunityCompute worker package.

Sprint 9 bootstrap: puts the repo root on sys.path so the worker can import
the shared protocol package (`packages.protocol`) in every entry point
(direct scripts bootstrap it too; this covers pytest/standalone imports).
Remove once the package is properly installed/packaged.
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

__version__ = "0.1.0-sprint24"
