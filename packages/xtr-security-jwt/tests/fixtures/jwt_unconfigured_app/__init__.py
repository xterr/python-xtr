"""An application package that lists the JWT bundle but configures no signing key.

A kernel over it builds and boots — its console can mint the missing key — and the
first token it signs or verifies raises ``MissingKeyError``.
"""

from __future__ import annotations
