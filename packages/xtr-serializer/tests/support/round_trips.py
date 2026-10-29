"""The copies of an error that every error must survive: pickled, copied and deep-copied."""

from __future__ import annotations

import copy
import pickle
from typing import TypeVar

__all__ = ["round_trips"]

_ErrorT = TypeVar("_ErrorT", bound=BaseException)


def round_trips(error: _ErrorT) -> tuple[_ErrorT, ...]:
    """Return ``error`` rebuilt by a pickle round trip (once, and twice), a copy and a deep copy.

    The pickle module is only ever handed bytes this function produced from the
    error itself, never bytes from outside, so the unpickling is safe here.
    """
    # Only bytes this function just wrote are unpickled, so no untrusted input reaches loads.
    return (
        pickle.loads(pickle.dumps(error)),  # noqa: S301
        pickle.loads(pickle.dumps(pickle.loads(pickle.dumps(error)))),  # noqa: S301
        copy.copy(error),
        copy.deepcopy(error),
    )
