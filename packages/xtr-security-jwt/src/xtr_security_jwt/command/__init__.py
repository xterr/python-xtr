"""The console commands: mint a key pair, mint a token, check the configuration."""

from __future__ import annotations

from .check_config_command import CheckConfigCommand
from .generate_key_pair_command import GenerateKeyPairCommand
from .generate_token_command import GenerateTokenCommand

__all__ = ["CheckConfigCommand", "GenerateKeyPairCommand", "GenerateTokenCommand"]
