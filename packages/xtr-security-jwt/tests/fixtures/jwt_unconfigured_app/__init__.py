"""An application package that lists the JWT bundle but configures no signing key.

The bundle is an add-on that cannot sign a token without a key the application
must choose, so a kernel that lists it with no ``<app>/config/jwt.py`` fails the
build. This package carries no configuration, so building a kernel over it drives
exactly that failure.
"""

from __future__ import annotations
