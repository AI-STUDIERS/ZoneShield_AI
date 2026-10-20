import sys
from pathlib import Path

# Ensure root and vision directories are on sys.path
_root = Path(__file__).resolve().parent.parent
_vision = _root / "vision"
for _p in (str(_root), str(_vision)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import uvicorn
from backend.config import settings


def main():
    print("Starting ZoneShield AI Backend Service on port 8000...")
    uvicorn.run("backend.api:app", host="0.0.0.0", port=8000, reload=False, log_level="info")


if __name__ == "__main__":
    main()
