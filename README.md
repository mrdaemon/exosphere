# Exosphere

[![Exosphere Test Suite](https://github.com/mrdaemon/exosphere/actions/workflows/exosphere-test.yml/badge.svg)](https://github.com/mrdaemon/exosphere/actions/workflows/exosphere-test.yml)

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

## Compatibility

Exosphere itself is written in Python and is compatible with Python 3.13 or later.
It can run nearly anywhere where Python is available, including Linux, MacOS,
and Windows (natively).

Supported platforms for remote hosts include:

- Debian/Ubuntu and derivatives (using APT)
- Red Hat/CentOS and derivatives (using YUM/DNF)
- FreeBSD (using pkg)

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

You can also run the spellchecker with:

```bash
uv run poe docs-spellcheck
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
