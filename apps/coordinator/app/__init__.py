"""CommunityCompute coordinator package.

Sprint 6 bootstrap: puts the repo root on sys.path so the coordinator can
import the shared protocol package (`packages.protocol`). Remove once the
package is properly installed/packaged.
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
