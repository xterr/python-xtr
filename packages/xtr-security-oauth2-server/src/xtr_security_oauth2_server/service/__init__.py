"""Services around the protocol rather than inside it.

What a deployment needs that no OAuth request ever asks for. One contract so
far: withdrawing everything a user or a client holds, which is what a password
change, an account closure or a client being withdrawn has to do.

The contract lives here and the implementations beside the persistence that
can actually run them, since taking back every credential of a user means one
statement per table rather than a walk through a manager.
"""

from __future__ import annotations

from .credentials_revoker_interface import CredentialsRevokerInterface

__all__ = ["CredentialsRevokerInterface"]
