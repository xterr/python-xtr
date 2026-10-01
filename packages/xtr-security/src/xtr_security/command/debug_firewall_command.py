"""``debug:firewall``: the firewalls an application configured, and how they run."""

from __future__ import annotations

from typing import Annotated, final

from xtr_console import Argument, ConsoleStyle, ExitCode, as_command, escape

# The console reads the command's signature at runtime to inject the firewall map.
from xtr_dependency_injection import Injected  # noqa: TC002

from xtr_security.firewall_map import FirewallMap  # noqa: TC001

__all__ = ["DebugFirewallCommand"]


@as_command("debug:firewall")
@final
class DebugFirewallCommand:
    """Lists an application's firewalls, or one firewall's pieces in detail."""

    __slots__ = ()

    async def __call__(
        self,
        io: ConsoleStyle,
        firewall_map: Injected[FirewallMap],
        name: Annotated[str | None, Argument(name="name")] = None,
    ) -> int:
        """List the firewalls, or the one named.

        Args:
            io: Where the command writes.
            firewall_map: The application's firewalls, from the container.
            name: A firewall to describe in detail, or every firewall when
                left out.
        """
        if name is not None:
            return self._describe(io, firewall_map, name)
        return self._list(io, firewall_map)

    def _list(self, io: ConsoleStyle, firewall_map: FirewallMap) -> int:
        """List every firewall, its scheme and whether it secures its requests."""
        names = firewall_map.names()
        io.section(f"Firewalls ({len(names)})")
        io.table(
            ("Name", "Secured", "Scheme"),
            [
                (
                    escape(fw_name),
                    "yes" if firewall_map.get(fw_name).security else "no",
                    escape(type(firewall_map.get(fw_name).scheme).__name__),
                )
                for fw_name in names
            ],
        )
        return ExitCode.SUCCESS

    def _describe(self, io: ConsoleStyle, firewall_map: FirewallMap, name: str) -> int:
        """Describe one firewall, or report it is not configured."""
        if not firewall_map.has(name):
            io.error(f'No firewall named "{escape(name)}"; known are {list(firewall_map.names())}.')
            return ExitCode.INVALID
        context = firewall_map.get(name)
        io.title(f'Firewall "{escape(name)}"')
        io.text(f"Secured: {'yes' if context.security else 'no'}")
        io.text(f"Scheme: {escape(type(context.scheme).__name__)}")
        io.text(f"Entry point: {escape(_name_of(context.entry_point))}")
        io.text(f"Access-denied handler: {escape(_name_of(context.access_denied_handler))}")
        io.text(f"Scope-denied handler: {escape(_name_of(context.scope_denied_handler))}")
        return ExitCode.SUCCESS


def _name_of(value: object) -> str:
    """Name a handler for the report, or ``"none"`` when there is none."""
    return type(value).__name__ if value is not None else "none"
