"""
SSH Transport Runners module for Exosphere.

Fabric Runners and related middleware are implemented within this
module, and the Connection object provided by objects.Host is intended
to make use of them.
"""

import shlex

from fabric.runners import Remote


class ExosphereRemote(Remote):
    """
    Fabric Remote runner used by Exosphere for all remote commands.

    The custom runner, intended to be inserted in Fabric Connection
    objects, performs two modifications to the behavior of the default
    Fabric Remote runner:

    1. It wraps every command in ``/bin/sh -c``, so that commands are
       always interpreted by a POSIX shell, independent of platform or
       login shell

    2. It exports a deterministic locale (both ``LC_ALL`` and ``LANG``)
       to ensure consistent human-readable output from remote package
       managers and other tools that may be localized via gettext on
       non-english systems.

    The choice of ``/bin/sh`` is deliberate: it is guaranteed to be
    present by POSIX on every single one of our supported platforms.

    C as a locale, also defaults to English, essentially, making
    the inevitable scraping in some providers deterministic.

    In both cases, these changes serve to transparently normalize the
    remote environment, regardless of user configuration, without
    requiring any changes. If someone, for some ineffable reason,
    has configured the login shell for their remote user to be tcsh
    or fish, on a German localized system, everything will still work
    exactly as expected.

    Sudo commands do not change behavior in regard to SUDOERS_COMMANDS
    allowlist matching, since the sudo binary will be called from the
    inner ``/bin/sh`` shell, and will inherit the locale as long as the
    sudoers configuration allows it (default configuration does).

    If the internal ExosphereRemote locale is not set, it defaults to C.
    """

    # Locale used when the runner context does not carry one. This
    # should not happen in normal operation, but keeps derived
    # connections safe and predictable.
    DEFAULT_LOCALE: str = "C"

    def send_start_message(self, command: str) -> None:
        """
        Wrap the command in a POSIX ``/bin/sh`` invocation that exports the
        configured locale, then hand it off to the channel.

        :param command: The command Fabric will execute remotely.
        """
        locale = getattr(self.context, "exosphere_locale", self.DEFAULT_LOCALE)
        payload = f"export LC_ALL={locale} LANG={locale} && {command}"

        super().send_start_message("/bin/sh -c " + shlex.quote(payload))
