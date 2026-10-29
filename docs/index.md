# xtr

xtr is a set of Python packages for applications. Each package does one job, for
example a cache, a message bus, a console or a security layer. All the packages
have type annotations. Each package that does input and output has an async API.

You can use one package alone, in any Python project. You can also use the
packages together in an xtr application. In an application, a container
connects the packages, and each package gives a bundle that configures it.

## Where to start

| You want to | Read |
|---|---|
| Make a new application | [Create an application](setup/new-application.md) |
| Add a package to an application | [Add a package](setup/add-a-package.md) |
| Learn the parts of an application | [The application layout](setup/application-layout.md) |
| Do a specific task | [Guides](guides/index.md) |
| Find a package for a job | [Components](components/index.md) |
| Learn how the packages connect | [Architecture](architecture/index.md) |
| Find a console command | [Console commands](reference/console-commands.md) |

## What xtr gives you

- **Packages that work alone.** Each package installs with its own
  dependencies. A package does not need the container.
- **A container that connects the packages.** The `xtr-dependency-injection`
  package builds the container from the bundles that the application lists.
- **Configuration with types.** A bundle reads its configuration from a frozen
  dataclass. The type checker finds a wrong option before the application starts.
- **Recipes.** When you add a package with `xtr-recipes`, its recipe writes the
  configuration files, the environment variables and the `.gitignore` lines.
- **One version for all packages.** All the packages have the same version
  number. Two packages with the same version work together.

## Requirements

- Python 3.11 or a later version.
- [uv](https://docs.astral.sh/uv/), to install the packages and to run the
  commands.

## Source and license

The source of all the packages is in
[the repository](https://github.com/xterr/python-xtr). Each package has a
README with its full description. The packages have the MIT license.
