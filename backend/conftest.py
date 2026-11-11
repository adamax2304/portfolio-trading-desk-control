"""Pytest bootstrap for the Control-Plane backend.

Guarantees THIS backend's `app` package is imported, not a same-named `app` package that
happens to live elsewhere on the machine (a sibling project's `app/` on the path would
otherwise shadow it, e.g. `...\\twitter viral strategy\\app`). Forcing this directory to the
FRONT of sys.path makes `from app import ...` resolve to `backend/app` without any manual
`PYTHONPATH=backend` hack — `python -m pytest backend/tests -q` just works.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
# remove any stale copy, then pin to the front so backend/app always wins
while _HERE in sys.path:
    sys.path.remove(_HERE)
sys.path.insert(0, _HERE)
