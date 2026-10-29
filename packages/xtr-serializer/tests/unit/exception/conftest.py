"""What the error tests share."""

from __future__ import annotations

import traceback
from typing import TYPE_CHECKING

import pytest

from xtr_serializer.exception import SerializerError

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.fixture
def secret() -> str:
    """A value shaped like a credential, planted where data could reach an error.

    Tests that build an error from data check that the secret is absent from the
    traceback an escaping error renders: a secret there has reached the logs.
    """
    return "s3cr3t-t0ken-4f9a"


@pytest.fixture
def traceback_of() -> Callable[[SerializerError], str]:
    """Raise an error and return the traceback ``traceback.format_exception`` renders for it.

    The traceback is what an application's logs show when the error escapes, so it
    is the text a secret must stay out of.
    """

    def render(error: SerializerError) -> str:
        try:
            # The traceback only exists for a raised error, so the raise is the point.
            raise error
        except SerializerError as caught:
            return "".join(traceback.format_exception(caught))

    return render
