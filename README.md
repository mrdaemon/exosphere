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
to deploy and use, requiring no central server, agents, or complex dependencies
on remote hosts.

If you have SSH access to the hosts and your keypairs are loaded in an SSH Agent,
you are good to go!

Simply follow the [Quickstart Guide](https://docs.exosphere.tools/en/stable/quickstart.html),
or see [the documentation](https://docs.exosphere.tools/en/stable/) to get started.

## Key Features

- Rich interactive command line interface (CLI)
- Text-based User Interface (TUI), offering menus, tables and dashboards
- Consistent view of information across different platforms and package managers
- See everything in one spot, at a glance, without complex automation or enterprise
  solutions
- Does not require Python (or anything else) to be installed on remote systems
- Parallel operations across hosts with optional SSH pipelining
- Document-based reporting in HTML, text or markdown format
- JSON output for integration with other tools

## Compatibility

Exosphere itself is written in Python and is compatible with Python 3.13 or later.
It can run nearly anywhere where Python is available, including Linux, macOS,
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
[full documentation](https://docs.exosphere.tools/) is available.

## Contributing Guidelines and Project Policies

See the [CONTRIBUTING.md](https://github.com/mrdaemon/exosphere/blob/main/CONTRIBUTING.md)
file in the code repository for details.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

The documentation prose is licensed under CC BY 4.0, and the docs bundle a few
third-party assets (fonts under the SIL OFL 1.1, a CSS file derived from the
Renku Sphinx Theme under Apache-2.0). The exact per-path licensing is recorded
in machine-readable form in the [COPYRIGHT](COPYRIGHT) file, with full license
texts under [LICENSES/](LICENSES/).

The bundled fonts under `docs/source/_static/fonts/` are cosmetic and safe to
remove for distribution in contexts where SIL OFL 1.1's awkward clauses are a
problem. The documentation CSS falls back to DejaVu Sans and DejaVu Sans Mono,
so the docs still build and render sensibly without them.
