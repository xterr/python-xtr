"""What the scan sets aside does not depend on the order it finds modules in.

Each scenario is scanned twice, its modules named so that the scan — which
walks them sorted by name — meets them in opposite orders. Both scans must
make the same of every module, by role, and leave nothing behind that a
truthful import would not have.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import pytest

from tests.support.set_aside import APP, scan_as

if TYPE_CHECKING:
    from pathlib import Path

FORWARD: Final = {"fx": "aa_fx", "other": "mm_other", "third": "zz_third"}
BACKWARD: Final = {"fx": "zz_fx", "other": "mm_other", "third": "aa_third"}
ROTATED: Final = {"fx": "mm_fx", "other": "aa_other", "third": "zz_third"}

FIXTURE: Final = (
    "from __future__ import annotations\n\n"
    "from acme_tools.fixtures import Fixture\nimport acme_faker\n\n"
    "fake = acme_faker.Faker()\n\n\n"
    "class UserFixtures(Fixture):\n    name = fake.name()\n"
)
PROBE: Final = "try:\n    import acme_faker\nexcept ImportError:\n    acme_faker = None\n\n"
REGISTER: Final = (
    "import acme_registry\n\nacme_registry.register(__name__.rpartition('.')[2][3:])\n\n"
)

_READING: Final[dict[str, dict[str, str]]] = {
    "a module importing a fixture": {
        f"{APP}.{{fx}}": FIXTURE,
        f"{APP}.{{other}}": f"from {APP}.{{fx}} import UserFixtures\n\n\nclass Seeder:\n    pass\n",
        f"{APP}.{{third}}": "class Plain:\n    pass\n",
    },
    "a module reading from a fixture that imports it": {
        f"{APP}.{{fx}}": (
            f"import acme_faker\n\nfake = acme_faker.Faker()\n\nimport {APP}.{{other}}\n"
        ),
        f"{APP}.{{other}}": (
            f"from {APP}.{{fx}} import fake\n\n\nclass Reader:\n    name = fake.name()\n"
        ),
    },
    "a module importing a fixture optionally": {
        f"{APP}.{{fx}}": FIXTURE,
        f"{APP}.{{other}}": (
            f"try:\n    from {APP}.{{fx}} import UserFixtures\n"
            "except ImportError:\n    UserFixtures = None\n\n\nclass Service:\n    pass\n"
        ),
    },
    "a module probing for the missing package, imported by a fixture": {
        f"{APP}.{{fx}}": f"import acme_faker\nfrom {APP}.{{other}} import Slugger\n",
        f"{APP}.{{other}}": f"{REGISTER}{PROBE}\nclass Slugger:\n    FAKER = acme_faker\n",
    },
    "a module asking whether the missing package exists, imported by a fixture": {
        f"{APP}.{{fx}}": f"import acme_faker\nfrom {APP}.{{other}} import Report\n",
        f"{APP}.{{other}}": (
            f"import importlib.util\n{REGISTER}"
            "HAS = importlib.util.find_spec('acme_faker') is not None\n\n\n"
            "class Report:\n    pass\n"
        ),
    },
    "a module asking whether a fixture exists": {
        f"{APP}.{{fx}}": FIXTURE,
        f"{APP}.{{other}}": (
            "import importlib.util\n\n"
            f"HAS = importlib.util.find_spec('{APP}.{{fx}}') is not None\n\n\n"
            "class Report:\n    pass\n"
        ),
        f"{APP}.{{third}}": f"import {APP}.{{fx}}\nimport {APP}.{{other}}\n",
    },
}

_SHAPES: Final[dict[str, dict[str, str]]] = {
    "an import cycle, the fixture failing on its first line": {
        f"{APP}.{{fx}}": (
            f"import acme_faker\n\n\nclass F:\n    pass\n\n\nfrom {APP} import {{other}}\n"
        ),
        f"{APP}.{{other}}": f"from {APP}.{{fx}} import F\n\n\nclass Loader(F):\n    pass\n",
    },
    "an import cycle, both halves needing the missing package": {
        f"{APP}.{{fx}}": f"import acme_faker\nimport {APP}.{{other}}\n\n\nclass One:\n    pass\n",
        f"{APP}.{{other}}": f"import {APP}.{{fx}}\nimport acme_faker\n\n\nclass Two:\n    pass\n",
    },
    "a healthy module registering once, imported by a fixture before its failing line": {
        f"{APP}.{{fx}}": f"from {APP}.{{other}} import User\nimport acme_faker\n",
        f"{APP}.{{other}}": f"{REGISTER}\nclass User:\n    pass\n",
        f"{APP}.{{third}}": f"from {APP}.{{other}} import User\n\n\nclass Uses:\n    user = User\n",
    },
    "a chain of modules failing through one another": {
        f"{APP}.{{fx}}": f"import {APP}.{{other}}\n\n\nclass Top:\n    pass\n",
        f"{APP}.{{other}}": f"import {APP}.{{third}}\n\n\nclass Middle:\n    pass\n",
        f"{APP}.{{third}}": "import acme_faker\n\n\nclass Bottom:\n    pass\n",
    },
    "a fixtures package re-exporting, with a healthy module, imported by another module": {
        f"{APP}.{{fx}}.__init__": "from .load import load\nfrom .users import UserFixtures\n",
        f"{APP}.{{fx}}.load": f"{REGISTER}\ndef load():\n    pass\n",
        f"{APP}.{{fx}}.users": FIXTURE,
        f"{APP}.{{fx}}.orders": (
            f"from {APP}.{{fx}} import UserFixtures\n\n\n"
            "class OrderFixtures:\n    after = UserFixtures\n"
        ),
        f"{APP}.{{other}}": f"from {APP}.{{fx}} import UserFixtures\n\n\nclass Seeder:\n    pass\n",
        f"{APP}.{{third}}": (
            f"try:\n    import {APP}.{{fx}}\nexcept ImportError:\n    pass\n\n\n"
            "class Kept:\n    pass\n"
        ),
    },
    "a set-aside module reached by its dotted name": {
        f"{APP}.{{fx}}": "import acme_faker\n\n\nclass Base:\n    pass\n",
        f"{APP}.{{other}}": (
            f"import {APP}.{{fx}}\n\n\nclass Derived({APP}.{{fx}}.Base):\n    pass\n"
        ),
        f"{APP}.{{third}}": f"import {APP}.{{fx}} as fx\nfrom {APP} import {{fx}}\n",
    },
    "an installed library needing the missing package": {
        "acme_lib.__init__": "import acme_faker\n\n\nclass Client:\n    pass\n",
        f"{APP}.{{fx}}": "import acme_lib\n\n\nclass Uses:\n    pass\n",
        f"{APP}.{{other}}": (
            "try:\n    import acme_lib\nexcept ImportError:\n    acme_lib = None\n\n\n"
            "class Optional:\n    pass\n"
        ),
    },
}

SCENARIOS: Final = _READING | _SHAPES


@pytest.mark.parametrize("scenario", sorted(SCENARIOS))
@pytest.mark.parametrize("naming", [BACKWARD, ROTATED], ids=["backward", "rotated"])
def test_a_scan_makes_the_same_of_every_module_whatever_order_it_finds_them_in(
    tmp_path: Path, scenario: str, naming: dict[str, str]
) -> None:
    forward = scan_as(tmp_path / "forward", SCENARIOS[scenario], FORWARD)
    other = scan_as(tmp_path / "other", SCENARIOS[scenario], naming)

    assert forward["violations"] == []
    assert other["violations"] == []
    assert other == forward


CYCLE_BEFORE_THE_FAILING_LINE: Final = {
    f"{APP}.{{fx}}": f"import {APP}.{{other}}\nimport acme_faker\n\n\nclass F:\n    pass\n",
    f"{APP}.{{other}}": f"from {APP} import {{fx}}\n\n\nclass Helper:\n    pass\n",
}


@pytest.mark.xfail(
    strict=True,
    reason=(
        "the other half of an import cycle, loaded by the truthful import that failed after it, "
        "is kept as that import left it; scanned first, it fails with it and is set aside"
    ),
)
def test_the_other_half_of_a_cycle_imported_before_the_failing_line_is_order_dependent(
    tmp_path: Path,
) -> None:
    fixture_first = scan_as(tmp_path / "forward", CYCLE_BEFORE_THE_FAILING_LINE, FORWARD)
    other_first = scan_as(tmp_path / "other", CYCLE_BEFORE_THE_FAILING_LINE, ROTATED)

    assert fixture_first["violations"] == other_first["violations"] == []
    assert other_first == fixture_first
