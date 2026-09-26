"""Every environment variable processor, injected with ``Autowire(env=...)``.

``Annotated[T, Autowire(env="prefix:NAME")]`` reads the variable when the service is built,
through the container's processors — never while the kernel builds. Prefixes chain right to
left: ``key:api_token:json:file:resolve:SHOP_SECRETS_FILE`` resolves ``%...%`` references in
``SHOP_SECRETS_FILE``, reads the file it names, decodes it as JSON and takes ``api_token``.

``bookshop env:show`` prints every value below; the ``.env`` file documents each variable.
"""

from __future__ import annotations

from typing import Annotated, final

from xtr_dependency_injection import Autowire, as_service

from .tier import Tier

__all__ = ["EnvShowcase"]


@final
@as_service
class EnvShowcase:
    """One attribute per processor, in the order of the processor table."""

    def __init__(  # noqa: PLR0913 — one parameter per processor, on purpose.
        self,
        *,
        raw: Annotated[str, Autowire(env="SHOP_NAME")],
        string: Annotated[str, Autowire(env="string:SHOP_NAME")],
        maintenance: Annotated[bool, Autowire(env="bool:SHOP_MAINTENANCE")],
        open_for_business: Annotated[bool, Autowire(env="not:SHOP_MAINTENANCE")],
        page_size: Annotated[int, Autowire(env="int:SHOP_PAGE_SIZE")],
        member_discount: Annotated[float, Autowire(env="float:SHOP_MEMBER_DISCOUNT")],
        motto: Annotated[str, Autowire(env="trim:SHOP_MOTTO")],
        search_hint: Annotated[str, Autowire(env="urlencode:SHOP_SEARCH_HINT")],
        api_key: Annotated[str, Autowire(env="base64:SHOP_API_KEY_B64")],
        features: Annotated[dict[str, object], Autowire(env="json:SHOP_FEATURES")],
        currencies: Annotated[list[str], Autowire(env="csv:SHOP_CURRENCIES")],
        database: Annotated[dict[str, object], Autowire(env="url:DATABASE_URL")],
        database_options: Annotated[
            dict[str, str], Autowire(env="query_string:key:query:url:DATABASE_URL")
        ],
        banner: Annotated[str, Autowire(env="file:resolve:SHOP_BANNER_FILE")],
        database_host: Annotated[str, Autowire(env="key:host:url:DATABASE_URL")],
        api_token: Annotated[
            str, Autowire(env="key:api_token:json:file:resolve:SHOP_SECRETS_FILE")
        ],
        tier: Annotated[Tier, Autowire(env="enum:bookshop.env.tier.Tier:SHOP_TIER")],
        rounding: Annotated[str, Autowire(env="const:SHOP_ROUNDING")],
        nickname: Annotated[str, Autowire(env="default:shop.fallback_name:SHOP_NICKNAME")],
        nickname_or_none: Annotated[str | None, Autowire(env="default::SHOP_NICKNAME")],
        has_nickname: Annotated[bool, Autowire(env="defined:SHOP_NICKNAME")],
        log_pattern: Annotated[str, Autowire(env="resolve:SHOP_LOG_PATTERN")],
        mirrors: Annotated[list[str], Autowire(env="shuffle:csv:SHOP_MIRRORS")],
        hidden: Annotated[str, Autowire(env="rot13:SHOP_HIDDEN_MESSAGE")],
        vault_token: Annotated[str, Autowire(env="SHOP_VAULT_TOKEN")],
    ) -> None:
        """Keep every value, to print them."""
        self.values: dict[str, tuple[str, object]] = {
            "raw": ("SHOP_NAME", raw),
            "string": ("string:SHOP_NAME", string),
            "bool": ("bool:SHOP_MAINTENANCE", maintenance),
            "not": ("not:SHOP_MAINTENANCE", open_for_business),
            "int": ("int:SHOP_PAGE_SIZE", page_size),
            "float": ("float:SHOP_MEMBER_DISCOUNT", member_discount),
            "trim": ("trim:SHOP_MOTTO", motto),
            "urlencode": ("urlencode:SHOP_SEARCH_HINT", search_hint),
            "base64": ("base64:SHOP_API_KEY_B64", api_key),
            "json": ("json:SHOP_FEATURES", features),
            "csv": ("csv:SHOP_CURRENCIES", currencies),
            "url": ("url:DATABASE_URL", database),
            "query_string": ("query_string:key:query:url:DATABASE_URL", database_options),
            "file": ("file:resolve:SHOP_BANNER_FILE", banner),
            "key": ("key:host:url:DATABASE_URL", database_host),
            "key (chained)": ("key:api_token:json:file:resolve:SHOP_SECRETS_FILE", api_token),
            "enum": ("enum:bookshop.env.tier.Tier:SHOP_TIER", tier),
            "const": ("const:SHOP_ROUNDING", rounding),
            "default": ("default:shop.fallback_name:SHOP_NICKNAME", nickname),
            "default (none)": ("default::SHOP_NICKNAME", nickname_or_none),
            "defined": ("defined:SHOP_NICKNAME", has_nickname),
            "resolve": ("resolve:SHOP_LOG_PATTERN", log_pattern),
            "shuffle": ("shuffle:csv:SHOP_MIRRORS", mirrors),
            "rot13 (custom)": ("rot13:SHOP_HIDDEN_MESSAGE", hidden),
            "loader": ("SHOP_VAULT_TOKEN", vault_token),
        }
