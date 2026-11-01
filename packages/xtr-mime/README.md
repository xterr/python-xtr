<div align="center">

# xtr-mime

**Build email messages — addresses, headers, text and HTML bodies, attachments and inline images — rendered to standard MIME by Python's own email package, signed with DKIM or S/MIME when asked.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

Coming: the package is being built; this page grows with it.

## Install

```sh
uv add xtr-mime
```

## Quick start

Coming with the message classes.

## Use in an application

Coming with the bundle.

## Kernel / bundle

Coming with the bundle.

## Errors

Coming with the package's errors.

## Known limitations

- **An email is rendered whole before its first chunk.** `to_iterable()` yields the message in
  pieces, but only once all of it is in memory: Python's email package writes a message from
  its whole tree, and an attachment's file is read whole into that tree. An email takes about
  its rendered size in memory while it is sent, however large its attachments.
- **A header parameter name is at most 40 characters.** A longer one is refused with
  `RfcComplianceError`: when its value has to be cut into RFC 2231 sections, the name may leave
  no room for them on a line.
- **A DKIM passphrase is for an encrypted key only.** `DkimSigner` refuses a passphrase given
  with a key that is not encrypted (`InvalidArgumentError`), as cryptography, which opens the
  key, refuses it; pass an empty passphrase for such a key.

## Development

```sh
cd packages/xtr-mime
uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run ty check && uv run pytest
```

## License

MIT — see [LICENSE](LICENSE).
