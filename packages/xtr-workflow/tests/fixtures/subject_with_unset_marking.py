"""Subjects declaring the attribute their getter reads, and never setting it before asked.

Their setter has no room for a context: it takes the place alone.
"""

# The attribute is declared and left unset on purpose — reading it before it
# is set is what these subjects are for — so the check that every declared
# attribute is set is off here.
# pyright: reportUninitializedInstanceVariable=false

from __future__ import annotations

from typing import final


@final
class SubjectWithUnsetMarking:
    marking: str

    def get_marking(self) -> str:
        return self.marking

    def set_marking(self, marking: str) -> None:
        self.marking = marking

    def get_marking2(self) -> str:
        # Reads the attribute of another name, on purpose.
        return self.marking


@final
class AsyncSubjectWithUnsetMarking:
    marking: str

    async def get_marking(self) -> str:
        return self.marking

    async def set_marking(self, marking: str) -> None:
        self.marking = marking

    async def get_marking2(self) -> str:
        # Reads the attribute of another name, on purpose.
        return self.marking
