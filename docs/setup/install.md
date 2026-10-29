# Install the tools

An xtr application needs Python, uv and git. This page shows how to make sure
that each tool is on your computer.

## Procedure

1. Install uv. Use the instructions on the
   [uv installation page](https://docs.astral.sh/uv/getting-started/installation/).
2. Open a new terminal.
3. Make sure that uv is available:

   ```sh
   uv --version
   ```

   The command shows the version of uv.
4. Make sure that Python 3.11 or a later version is available:

   ```sh
   uv python find 3.11
   ```

   If the command does not find a Python, install one with uv:

   ```sh
   uv python install 3.13
   ```

5. Make sure that git is available:

   ```sh
   git --version
   ```

   If git is not available, install it. The `xtr-cli` tool uses git to start a
   repository in each new application.

## Optional: install the xtr command

You can run `xtr-cli` with `uvx` each time, with no installation. To use the
shorter `xtr` command, install the tool one time:

```sh
uv tool install xtr-cli
```

After this, `xtr new shop` and `uvx xtr-cli new shop` do the same thing.

## Next step

[Create an application](new-application.md).
