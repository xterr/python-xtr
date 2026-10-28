"""The dotenv bundle: the cascade its ``dotenv:dump`` and ``debug:dotenv`` commands describe.

The bundle loads nothing — ``bookshop.kernel.load_environment`` does, before the kernel is
built. This config must describe the same cascade, so both read the same constants.
"""

from __future__ import annotations

from xtr_dependency_injection import configure
from xtr_dotenv.bundle import DotenvConfig

from bookshop.kernel import DEBUG_KEY, ENV_KEY, PROD_ENVS, TEST_ENVS

__all__ = ["dotenv"]


@configure
def dotenv() -> DotenvConfig:
    """Every ``DotenvConfig`` field; ``%kernel.project_dir%`` is resolved by the kernel."""
    return DotenvConfig(
        path="%kernel.project_dir%/.env",
        env_key=ENV_KEY,
        debug_key=DEBUG_KEY,
        test_envs=TEST_ENVS,
        prod_envs=PROD_ENVS,
    )
