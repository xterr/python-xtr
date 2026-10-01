"""A fake third-party package that extends the security family through the seams.

No xtr-security code knows this package. Its bundle prepends an authenticator
factory (key ``fake_oauth2``) and a token-handler factory onto the security
config; an application configures a firewall with both, requests authenticate
through them, scopes gate routes, and ``debug:firewall`` lists the firewall —
the proof that seams S-1 and S-2 are open.
"""

from __future__ import annotations
