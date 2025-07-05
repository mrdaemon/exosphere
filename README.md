# Exosphere

[![Exosphere Test Suite](https://github.com/mrdaemon/exosphere/actions/workflows/exosphere-test.yml/badge.svg)](https://github.com/mrdaemon/exosphere/actions/workflows/exosphere-test.yml)

Exosphere is a command line and Text User Interface driven utility to query and
get ad-hoc reports from server infrastructure.

It can, so far, be used to:

- Get an overview of pending package and security updates
- Aggregate host online status and basic information

It is meant to be simple and foregoes any rich features that could otherwise be
serviced by other, better written tools.

It is meant to give a high level view of your infrastructure and how it's going,
as well as query information about state that is otherwise difficult
to aggregate or obtain ad-hoc.

Because reporting sucks, and things could be better.

  > ## Pre-release Version
  > This is a pre-release version of Exosphere
  > It can be used but is under-documented, and still changing rapidly
  > You may not want to use this this just yet, and wait for 1.0

## Development Quick Start

tl;dr, use [uv](https://docs.astral.sh/uv/getting-started/installation/)

```bash
uv sync
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

A quickstart of running the UI with live editing and reloading, with debug
console is as follows:

```bash
# Ensure you have the dev dependencies
uv sync --dev
# In a separate terminal, run the console
uv run textual console
# In another terminal, run the UI
uv run textual run --dev -c exosphere ui start
```

Congratulations, editing any of the tcss files in the `ui/` directory will
reflect changes immediately.

Make sure you run the exosphere ui with 'exosphere ui start' otherwise the
configuration will not be loaded correctly, and the inventory will not be
populated.
