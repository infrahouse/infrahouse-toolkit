"""
Skeema helpers.

Provides :class:`Skeema` for running the skeema executable with database credentials kept off
its command line, :class:`SkeemaDiff` for reading what ``skeema diff`` prints, and
:class:`Preflight` for reporting what a push would do and what it would cost.
"""

from infrahouse_toolkit.skeema.diff import SkeemaDiff
from infrahouse_toolkit.skeema.exceptions import (
    SkeemaDiffError,
    SkeemaDigestMismatch,
    SkeemaError,
)
from infrahouse_toolkit.skeema.preflight import Preflight
from infrahouse_toolkit.skeema.skeema import Skeema

# skeema exits with 0 for no differences, 1 for differences and 2 or more for errors.
# ih-skeema errors use 2 as well, so a caller can tell a failure from pending changes.
EXIT_ERROR = 2

__all__ = [
    "EXIT_ERROR",
    "Preflight",
    "Skeema",
    "SkeemaDiff",
    "SkeemaDiffError",
    "SkeemaDigestMismatch",
    "SkeemaError",
]
