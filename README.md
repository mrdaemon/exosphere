# Exosphere

<p>
  <a href="https://github.com/mrdaemon/exosphere/releases"><img src="https://img.shields.io/github/v/release/mrdaemon/exosphere" alt="GitHub release"></a>
  <a href="https://pypi.org/project/exosphere-cli/"><img src="https://img.shields.io/pypi/v/exosphere-cli" alt="PyPI"></a>
  <a href="https://github.com/mrdaemon/exosphere/tree/main"><img src="https://img.shields.io/badge/dynamic/toml?url=https%3A%2F%2Fraw.githubusercontent.com%2Fmrdaemon%2Fexosphere%2Frefs%2Fheads%2Fmain%2Fpyproject.toml&query=%24.project.version&label=dev&color=purple" alt="Current Dev Version"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/python/required-version-toml?tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2Fmrdaemon%2Fexosphere%2Frefs%2Fheads%2Fmain%2Fpyproject.toml" alt="Python Version"></a>
  <a href="https://github.com/mrdaemon/exosphere/actions/workflows/test-suite.yml"><img src="https://img.shields.io/github/actions/workflow/status/mrdaemon/exosphere/test-suite.yml?label=test%20suite" alt="Test Suite"></a>
  <a href="https://github.com/mrdaemon/exosphere/blob/main/LICENSE"><img src="https://img.shields.io/github/license/mrdaemon/exosphere" alt="License"></a>
</p>

Exosphere is a CLI and Text UI driven application that offers aggregated patch
and security update reporting as well as basic system status across multiple
Unix-like hosts over SSH.

![exosphere demo](./demo.gif)

It is targeted at small to medium sized networks, and is designed to be simple
to deploy and use, requiring no central server, agents and complex dependencies
on remote hosts.

If you have SSH access to the hosts and your keypairs are loaded in a SSH Agent,
you are good to go!

Simply follow the [Quickstart Guide](https://exosphere.readthedocs.io/en/stable/quickstart.html),
or see [the documentation](https://exosphere.readthedocs.io/en/stable/) to get started.

## Key Features

- Rich interactive command line interface (CLI)
- Text-based User Interface (TUI), offering menus, tables and dashboards
- Consistent view of information across different platforms and package managers
- See everything in one spot, at a glance, without complex automation or enterprise
  solutions
- Does not require Python (or anything else) to be installed on remote systems
- Parallel operations across hosts with optional SSH pipelining
- Document based reporting in HTML, text or markdown format
- JSON output for integration with other tools

## Compatibility

Exosphere itself is written in Python and is compatible with Python 3.13 or later.
It can run nearly anywhere where Python is available, including Linux, MacOS,
and Windows (natively).

Supported platforms for remote hosts include:

- Debian/Ubuntu and derivatives (using APT)
- Red Hat/CentOS and derivatives (using YUM/DNF)
- FreeBSD (using pkg)
- OpenBSD (using pkg_add)

Unsupported platforms with SSH connectivity checks only:

- Other Linux distributions (e.g., Arch Linux, Gentoo, NixOS, etc.)
- Other BSD systems (NetBSD)
- Other Unix-like systems (e.g., Solaris, AIX, IRIX, Mac OS)

Exosphere **does not support** other platforms where SSH is available.
This includes network equipment with proprietary operating systems, etc.

## Documentation

For installation instructions, configuration and usage examples,
[full documentation](https://exosphere.readthedocs.io/) is available.

## Development

### Development Quick Start

TL;DR, use [uv](https://docs.astral.sh/uv/getting-started/installation/)

```bash
uv sync --dev
uv run exosphere
```

Linting, formatting and testing can be done with poe tasks:

```bash
uv run poe format
uv run poe check
uv run poe test
```

For more details, and available tasks, run:

```bash
uv run poe --help
```

### UI Development Quick Start

The UI is built with [Textual](https://textual.textualize.io/).

A quick start for running the UI with live editing and reloading, plus debug
console, is as follows:

```bash
# Ensure you have the dev dependencies
uv sync --dev
# In a separate terminal, run the console
uv run textual console
# In another terminal, run the UI
uv run textual run --dev -c exosphere ui start
```

Congratulations! Editing any of the `.tcss` files in the `ui/` directory will
reflect changes immediately.

Make sure you run Exosphere UI with `exosphere ui start`.

### Documentation Editing Quick Start

To edit the documentation, you can use the following commands:

```bash
uv sync --dev
uv run poe docs-serve
```

This will start a local server at `http://localhost:8000` where you can view the
documentation. You can edit the files in the `docs/source` directory, and the changes
will be reflected in real-time.

To check the documentation for spelling errors, you can run:

```bash
uv run poe docs-spellcheck
```

Linting is performed as part of the `poe docs` task, which also builds the
documentation, but can also be invoked separately:

```bash
uv run poe docs-lint
```

### Project Structure

The project is managed via uv and `pyproject.toml`, which contains all dependencies,
scripts, and metadata for the application.

Exosphere uses [Poe the Poet](https://poethepoet.natn.io/) as a task runner, and all
tasks are defined in the `pyproject.toml` file under the `[tool.poe.tasks]` table.

#### Root Directory

| path | description |
| ---- | ----------- |
| `docs/` | Sphinx documentation source tree |
| `docs/source/_ext/` | Custom Sphinx extensions for the project |
| `examples/` | Example configuration files and reports |
| `scripts/` | Utilitarian scripts for dev and maintenance |
| `src/` | Main source code for the application |
| `tests/` | Test suite for the application |

#### Source Tree

| path | description |
| ---- | ----------- |
| `src/exosphere/` | Main application source code |
| `src/exosphere/commands/` | CLI command implementations |
| `src/exosphere/providers/` | Package Manager Provider implementations (e.g. debian, freebsd, redhat, etc) |
| `src/exosphere/schema/` | Reporting JSON schema definitions |
| `src/exosphere/setup/` | Discovery and platform detection module |
| `src/exosphere/templates/` | Jinja2 templates for reporting |
| `src/exosphere/ui/` | Textual UI source code |
| `src/exosphere/ui/style.tcss` | Textual CSS for styling the UI |

The rest of the source tree should be fairly self-explanatory.

#### Core Modules

Paths below are relative to `src/exosphere/` unless otherwise noted.

| module | description |
| ------ | ----------- |
| `main.py` | Main entry point for the application |
| `providers/api.py` | Package manager provider API and base classes |
| `providers/factory.py` | Concrete provider factory for creation of Package Managers |
| `cli.py` | CLI interface entry point |
| `config.py` | Configuration subsystem, including defaults |
| `context.py` | Context management for shared state across commands and UI |
| `data.py` | Data models and structures for serialization and exchange |
| `database.py` | Cache system for serialization |
| `errors.py` | Exception classes and general error messages |
| `inventory.py` | Inventory management subsystem |
| `migrations.py` | Cache format migration processes |
| `objects.py` | Main objects for representing Hosts, and most of the relevant logic |
| `pipelining.py` | SSH pipelining implementation, including reaper thread |
| `repl.py` | REPL module for interactive CLI usage |
| `reporting.py` | Reporting subsystem, including templates and formatters |
| `security.py` | Sudo management subsystem, including policy and utilities |

Generally, most of the things Exosphere does to hosts (including connection management
and operations) are going to be found in `objects.py`.

#### UI Modules

Paths below are relative to `src/exosphere/` unless otherwise noted.

| module | description |
| ------ | ----------- |
| `ui/app.py` | Main Textual application class and entry point for the UI |
| `ui/context.py` | UI Context management for shared state across UI components |
| `ui/elements.py` | Shared UI elements, including task runners |
| `ui/dashboard.py` | Dashboard view implementation |
| `ui/inventory.py` | Inventory view implementation |
| `ui/logs.py` | Logs view implementation |
| `ui/messages.py` | Screen refresh and message passing system |

The TCSS for all of it is in a single file under `ui/style.tcss`.

### Using Exosphere as a Library

This use case is not currently well supported, but it is possible to use Exosphere as a library.
The documentation for this (alongside actual examples) is still a WIP, but you can
refer to the [Online API Documentation](https://exosphere.readthedocs.io/en/stable/api/index.html)
for the core functionality and objects that are considered public.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
