"""A configured application whose user provider also upgrades passwords.

An upgrading provider over one in-memory user, a migrating hasher over it —
argon2id best, PBKDF2 verifying the stored legacy hash — and a secured
firewall, so a container test drives a password login's full listener chain
and watches the hash get re-stored.
"""

from __future__ import annotations
