"""ProjectQuestions: what the command line left out, asked of whoever is at the terminal."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Final, final

from xtr_console import escape

from .exception import UnknownAddOnError

if TYPE_CHECKING:
    from xtr_console import ConsoleStyle

    from .add_on import AddOn
    from .add_on_catalog import AddOnCatalog
    from .add_on_choice import AddOnChoice
    from .template_catalog import TemplateCatalog

__all__ = ["DEFAULT_TEMPLATE", "ProjectQuestions"]

DEFAULT_TEMPLATE: Final = "cli"
"""The template a project gets when none is asked for and no question may be asked."""


@final
class ProjectQuestions:
    """Asks only for what was not given, and never when questions are off.

    Every question has an option that answers it, and an option given is never
    asked again. With ``-n`` every question takes its default unasked — the
    ``cli`` template and no add-ons — so a script or a CI job never waits on a
    prompt. A wrong answer is reported and the question asked again.
    """

    __slots__ = ("_add_ons", "_io", "_templates")

    def __init__(self, io: ConsoleStyle, templates: TemplateCatalog, add_ons: AddOnCatalog) -> None:
        """Ask through ``io``, offering what ``templates`` and ``add_ons`` hold."""
        self._io = io
        self._templates = templates
        self._add_ons = add_ons

    def directory(self, given: Path | None) -> Path | None:
        """Return the directory given, or the one answered; ``None`` when there is neither."""
        if given is not None:
            return given
        answer = self._io.ask("Project directory").strip()
        return Path(answer) if answer else None

    def template(self, given: str | None) -> str:
        """Return the template given, or the shipped one chosen."""
        if given is not None:
            return given
        names = self._templates.names()
        if self._io.interactive:
            self._io.listing(
                escape(f"{name} — {self._templates.load(name).summary}") for name in names
            )
        default = DEFAULT_TEMPLATE if DEFAULT_TEMPLATE in names else names[0]
        return self._io.ask("Template", default, choices=names)

    def add_ons(self, given: str | None, template: str) -> tuple[AddOnChoice, ...]:
        """Return the add-ons given, or the ones chosen, variants asked for each that has them.

        Raises:
            UnknownAddOnError: When ``given`` names an add-on that cannot be
                added; a wrong answer is asked again instead.
        """
        if given is not None:
            return self._add_ons.parse(given, template)
        available = self._add_ons.available(template)
        if not self._io.interactive or not available:
            return ()
        self._io.listing(escape(f"{add_on.name} — {add_on.summary}") for add_on in available)
        while True:
            answer = self._io.ask("Add-ons, comma-separated (empty for none)")
            try:
                chosen = self._add_ons.parse(answer, template)
            except UnknownAddOnError as error:
                self._io.error(escape(str(error)))
                continue
            spelled = {
                token.partition(":")[0].strip() for token in answer.split(",") if ":" in token
            }
            return tuple(
                choice
                if not choice.add_on.variants or choice.add_on.name in spelled
                else self._variants(choice.add_on)
                for choice in chosen
            )

    def confirm(self) -> bool:
        """Ask whether to go ahead; yes when questions are off."""
        return self._io.confirm("Create it?", default=True)

    def _variants(self, add_on: AddOn) -> AddOnChoice:
        """Ask which of ``add_on``'s variants to install, until the answer is one it offers."""
        question = (
            f"{add_on.variant_label.capitalize()} for {add_on.name} — "
            f"{', '.join(add_on.variants)}, joined with +"
        )
        while True:
            answer = self._io.ask(question, "+".join(add_on.default_variants))
            try:
                return self._add_ons.choose(add_on, answer)
            except UnknownAddOnError as error:
                self._io.error(escape(str(error)))
