# Exosphere

<p>
  <a href="https://github.com/mrdaemon/exosphere/releases"><img src="https://img.shields.io/github/v/release/mrdaemon/exosphere" alt="GitHub release"></a>
  <a href="https://pypi.org/project/exosphere-cli/"><img src="https://img.shields.io/pypi/v/exosphere-cli" alt="PyPI"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.13+-purple.svg" alt="Python Version"></a>
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

Unsupported platform with with SSH connectivity checks only:

- Other Linux distributions (e.g., Arch Linux, Gentoo, NixOS, etc.)
- Other BSD systems (NetBSD)
- Other Unix-like systems (e.g., Solaris, AIX, IRIX, Mac OS)

Exosphere **does not support** other platforms where SSH is available.
This includes network equipment with proprietary operating systems, etc.

## Documentation

For installation instructions, configuration and usage examples,
[full documentation](https://exosphere.readthedocs.io/) is available.

## Development Quick Start

tl;dr, use [uv](https://docs.astral.sh/uv/getting-started/installation/)

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

## UI Development Quick Start

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

## Documentation Editing Quick Start

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

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
