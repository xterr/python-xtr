"""An empty application package for probe-bundle unit tests.

The factory and wiring-helper unit tests build a kernel that scans a package and
activates only a probe bundle, which registers services through the helper or
factory under test directly. The package carries no configuration, so the build
resolves nothing beyond what the probe bundle declares.
"""

from __future__ import annotations
