"""A served application on the security bundle, for the integration tests.

The kernel scans this package: the token handler, the recording listeners, a
password-authenticated user provider and the security configuration are picked
up so an integration test can drive a real firewall over ``httpx.ASGITransport``.
"""

from __future__ import annotations
