"""The controllers answering the provider's endpoints.

:class:`UserInfoController` answers the userinfo endpoint: the claims of the
end-user an access token stands for.
"""

from __future__ import annotations

from .user_info_controller import UserInfoController

__all__ = ["UserInfoController"]
