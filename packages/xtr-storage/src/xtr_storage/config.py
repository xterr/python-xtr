"""The options one operation runs with."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from typing_extensions import override

from xtr_storage.exception import InvalidArgumentError
from xtr_storage.identical_path_policy import IdenticalPathPolicy
from xtr_storage.visibility import Visibility

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["Config"]


@final
class Config:  # noqa: PLW1641 -- option values are arbitrary, mappings included, so there is nothing to hash; equality is for comparing what two operations ran with
    """The options one operation runs with, layered rather than changed.

    Options reach an adapter from two places: the ones a storage was built
    with, and the ones a single call passes. Both are open mappings — an
    adapter reads the keys below, and forwards the rest to its backend — so
    the layering, not a fixed field list, is what this class is for.

    Nothing is ever changed in place. ``extend`` and ``with_defaults`` answer
    the only two questions there are — who wins, the newcomer or the incumbent
    — and each returns a new configuration, so a storage can hand its own
    options to one call without that call's options leaking into the next.

    ```python
    defaults = Config({Config.VISIBILITY: "private"})
    for_this_call = defaults.extend({Config.VISIBILITY: "public"})  # public wins
    ```

    The typed accessors are the reading half: a value arriving from a
    configuration file is text, and every caller would otherwise parse it
    again, differently.
    """

    __slots__ = ("_options",)

    VISIBILITY: Final[str] = "visibility"
    """Who may read what is written: a :class:`~xtr_storage.Visibility` or its name."""

    DIRECTORY_VISIBILITY: Final[str] = "directory_visibility"
    """The same, for directories a write or a create has to make on the way."""

    RETAIN_VISIBILITY: Final[str] = "retain_visibility"
    """Whether a copy or a move keeps what the source had. True unless said otherwise."""

    MOVE_IDENTICAL_PATH: Final[str] = "move_identical_path"
    """What a move from a path to itself does: an :class:`~xtr_storage.IdenticalPathPolicy`.

    Nothing, unless said otherwise.
    """

    COPY_IDENTICAL_PATH: Final[str] = "copy_identical_path"
    """The same, for a copy."""

    CHECKSUM_ALGORITHM: Final[str] = "checksum_algorithm"
    """Which digest a checksum is taken with. ``"md5"`` unless said otherwise."""

    PUBLIC_URL: Final[str] = "public_url"
    """Where files are reachable from: one prefix, or several to spread them over."""

    ALLOW_RELATIVE_PATH_TRAVERSAL: Final[str] = "allow_relative_path_traversal"
    """Whether ``..`` in a path may climb. True unless said otherwise."""

    _options: dict[str, object]

    def __init__(self, options: Mapping[str, object] | None = None) -> None:
        """Take a copy of ``options``, so a caller's dictionary stays the caller's.

        Args:
            options: What this configuration holds; nothing when left out.
        """
        self._options = dict(options) if options is not None else {}

    def get(self, key: str, default: object = None) -> object:
        """Return the option ``key`` holds, or ``default`` when it holds none.

        Args:
            key: The option's name.
            default: What to answer when the option was never set.

        Returns:
            The value, untouched and unparsed.
        """
        return self._options.get(key, default)

    def extend(self, options: Mapping[str, object]) -> Config:
        """Return these options with ``options`` laid over them — the newcomer wins.

        Args:
            options: What a single call asked for.

        Returns:
            A new configuration; this one is unchanged.
        """
        return Config({**self._options, **options})

    def with_defaults(self, defaults: Mapping[str, object]) -> Config:
        """Return these options over ``defaults`` — what is already set wins.

        Args:
            defaults: What to fall back on for options nobody set.

        Returns:
            A new configuration; this one is unchanged.
        """
        return Config({**defaults, **self._options})

    def with_setting(self, key: str, value: object) -> Config:
        """Return these options with ``key`` set to ``value``.

        Args:
            key: The option's name.
            value: What it is worth from now on.

        Returns:
            A new configuration; this one is unchanged.
        """
        return Config({**self._options, key: value})

    def without_settings(self, *keys: str) -> Config:
        """Return these options with ``keys`` dropped, ignoring any that is not set.

        Dropping rather than overwriting matters where absence means something
        of its own: a storage's default visibility must be gone, not ``None``,
        for a copy that is asked to keep the source's.

        Args:
            *keys: The options to leave out.

        Returns:
            A new configuration; this one is unchanged.
        """
        dropped = frozenset(keys)

        return Config({name: value for name, value in self._options.items() if name not in dropped})

    def to_dict(self) -> dict[str, object]:
        """Return the options as a plain dictionary, copied so callers may keep it."""
        return dict(self._options)

    def visibility_option(self, key: str) -> Visibility | None:
        """Return the visibility ``key`` holds, or ``None`` when it holds none.

        ``None`` is an answer, not a failure: it says the caller made no
        demand, and the adapter is free to use the backend's default.

        Args:
            key: The option's name, usually :attr:`VISIBILITY`.

        Returns:
            The visibility asked for, or ``None``.

        Raises:
            InvalidArgumentError: When the option holds something that is not text.
            InvalidVisibilityError: When the text names no visibility.
        """
        value = self._options.get(key)

        if value is None:
            return None

        if isinstance(value, str):
            return Visibility.parse(value)

        raise InvalidArgumentError(
            f'The "{key}" option must be a visibility or its name, not {type(value).__name__}.',
        )

    def bool_option(self, key: str, default: bool) -> bool:
        """Return the flag ``key`` holds, or ``default`` when it holds none.

        Args:
            key: The option's name.
            default: What the flag is worth where nobody set it.

        Returns:
            The flag.

        Raises:
            InvalidArgumentError: When the option holds anything but true or false.
        """
        value = self._options.get(key, default)

        if isinstance(value, bool):
            return value

        raise InvalidArgumentError(
            f'The "{key}" option must be true or false, not {type(value).__name__}.',
        )

    def identical_path_policy(self, key: str) -> IdenticalPathPolicy:
        """Return the policy ``key`` holds, ignoring the operation when it holds none.

        Args:
            key: :attr:`COPY_IDENTICAL_PATH` or :attr:`MOVE_IDENTICAL_PATH`.

        Returns:
            The policy asked for, or :attr:`IdenticalPathPolicy.IGNORE`.

        Raises:
            InvalidArgumentError: When the option names no policy, or is not text.
        """
        value = self._options.get(key)

        if value is None:
            return IdenticalPathPolicy.IGNORE

        if isinstance(value, str):
            try:
                return IdenticalPathPolicy(value)
            except ValueError as error:
                known = ", ".join(policy.value for policy in IdenticalPathPolicy)

                raise InvalidArgumentError(
                    f'The "{key}" option must be one of {known}, not {value!r}.',
                ) from error

        raise InvalidArgumentError(
            f'The "{key}" option must name a policy, not {type(value).__name__}.',
        )

    def str_option(self, key: str, default: str) -> str:
        """Return the text ``key`` holds, or ``default`` when it holds none.

        Args:
            key: The option's name.
            default: What to answer where nobody set it.

        Returns:
            The text.

        Raises:
            InvalidArgumentError: When the option holds something that is not text.
        """
        value = self._options.get(key, default)

        if isinstance(value, str):
            return value

        raise InvalidArgumentError(
            f'The "{key}" option must be text, not {type(value).__name__}.',
        )

    @override
    def __eq__(self, other: object) -> bool:
        """Two configurations are equal when they hold the same options."""
        if not isinstance(other, Config):
            return NotImplemented

        return self._options == other._options

    @override
    def __repr__(self) -> str:
        """Name the options, so a failed assertion says which ones were in force."""
        return f"{type(self).__name__}({self._options!r})"
