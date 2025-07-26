# Exosphere

[![Exosphere Test Suite](https://github.com/mrdaemon/exosphere/actions/workflows/exosphere-test.yml/badge.svg)](https://github.com/mrdaemon/exosphere/actions/workflows/exosphere-test.yml)

Exosphere is a CLI and Text UI driven application that offers aggregated patch
and security update reporting as well as basic system status across multiple
Unix-like hosts over SSH.

![example usage](./demo.svg)

It is targeted at small to medium sized networks, and is designed to be simple
to deploy and use, requiring no central server, agents and complex dependencies
on remote hosts.

If you have SSH access to the hosts and your keypairs are loaded in a SSH Agent,
you are good to go!

## Key Features

- Rich interactive command line interface (CLI)
- Text-based User Interface (TUI), offering menus, tables and dashboards
- Consistent view information across different platforms and package managers
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

## Quick Start

Simply follow the [Quickstart Guide](https://exosphere.readthedocs.io/en/latest/quickstart.html).

## Documentation

For installation instructions, configuration and usage examples,
[full documentation](https://exosphere.readthedocs.io/) is available.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
