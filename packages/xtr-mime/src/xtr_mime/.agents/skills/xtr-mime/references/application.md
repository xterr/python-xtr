# MimeBundle in an application

With `xtr-mime` installed and `MimeBundle` listed, the container holds:

| Service | Under | Built |
| --- | --- | --- |
| `MimeTypes` | `MimeTypesInterface`, `MimeTypeGuesserInterface` | when first asked for; it then becomes `MimeTypes.get_default()` for the whole process |
| `DefaultHtmlToTextConverter` | `HtmlToTextConverterInterface` | when first asked for |

Nothing is built at boot.

## Configure

```python
# app/config/packages/mime.py
from xtr_dependency_injection import configure
from xtr_mime.bundle import MimeConfig


@configure
def mime() -> MimeConfig:
    return MimeConfig(extra_map={"application/mbox": ["mbox"]})
```

`extra_map` maps a `type/subtype` to a sequence of extensions without their leading dot; they
rank before the standard table's. Anything else is refused with `InvalidArgumentError`.

## Guessers

The table asks every service tagged `MIME_TYPE_GUESSER_TAG` (`"mime.mime_type_guesser"`, from
`xtr_mime.bundle`) before it answers from the extension: the highest `priority` first, then in
registration order. The tag's `priority` wins over the definition's own; without either it is 0.

```python
# app/services/upload_guesser.py
from typing_extensions import override
from xtr_dependency_injection import as_service
from xtr_mime import MimeTypeGuesserInterface


@as_service
class UploadGuesser(MimeTypeGuesserInterface):
    @override
    def is_guesser_supported(self) -> bool:
        return True

    @override
    def guess_mime_type(self, path: str) -> str | None:
        return "application/x-upload" if path.endswith(".upl") else None
```

Subclassing `MimeTypeGuesserInterface` tags it. A class with only the methods joins once a bundle
tags it: `services.set(UploadGuesser).add_tag(MIME_TYPE_GUESSER_TAG, priority=10)`.

- A tag `priority` that is not an `int` fails the build with `LogicError`.
- A tagged service that is not a guesser fails building the table with `LogicError` (wrapped by
  the container's `ServiceResolutionError`).
- `MagicMimeTypeGuesser` is already inside every `MimeTypes`; do not tag it again.

## Inject

```python
# app/services/attachments.py
from xtr_dependency_injection import as_service
from xtr_mime import HtmlToTextConverterInterface, MimeTypesInterface


@as_service
class Attachments:
    def __init__(
        self, mime_types: MimeTypesInterface, converter: HtmlToTextConverterInterface
    ) -> None:
        self.mime_types = mime_types
        self.converter = converter
```

## Test

```python
from xtr_dependency_injection.testing import assert_zero_config
from xtr_mime.bundle import MimeBundle


async def test_the_mime_bundle_works_unconfigured() -> None:
    await assert_zero_config(MimeBundle)
```

Building the table makes it the process's default: a test that builds it puts
`MimeTypes.set_default(...)` back afterwards if other tests read the default.
