"""The ``security:hash-password`` console command.

Importing this module declares it. With a container, the security bundle loads
it when the console bundle is active, and the command resolves a named user
class's hasher through the container's factory. Without one, the console builds
it bare and it hashes with the secure default hasher.

Needs the ``console`` extra: ``xtr-password-hasher[console]``.
"""

from __future__ import annotations

from .user_password_hash_command import UserPasswordHashCommand

__all__ = ["UserPasswordHashCommand"]
