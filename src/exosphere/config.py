import copy
import errno
import io
import json
import logging
import os
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any, BinaryIO, ClassVar

import yaml
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    field_validator,
    model_validator,
)

from exosphere import fspaths
from exosphere.security import SudoPolicy

# A mapping of the known configuration loaders available out of the box
# for the Exosphere configuration system, keyed by file extension.
# The configuration system technically allows for any loader callable
# to be used, but these are the ones that are wired in by default.
KNOWN_LOADERS: dict[str, Callable[..., Any]] = {
    "yaml": yaml.safe_load,
    "yml": yaml.safe_load,
    "toml": tomllib.load,
    "json": json.load,
}


def _normalize_sudo_policy(value: str) -> str:
    """Validate and normalize a sudo policy name."""
    candidate = value.lower()
    valid_values = {policy.value for policy in SudoPolicy}
    if candidate not in valid_values:
        valid = ", ".join(sorted(valid_values))
        raise ValueError(f"invalid sudo policy {value!r}; must be one of: {valid}")

    return candidate


# Reusable string type that normalizes/validates a sudo policy name.
SudoPolicyName = Annotated[str, AfterValidator(_normalize_sudo_policy)]

# Reusable string type for fields where an empty value is always a mistake
NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class OptionsModel(BaseModel):
    """
    Schema for the Exosphere options (global runtime settings) section.

    This is the authoritative source of truth for option keys and
    defaults within the Exsophere configuration subsystem.

    :attr:`Configuration.DEFAULTS` is derived from this schema.

    Unknown keys are rejected with a ValueError, and all values are
    validated and normalized to canonical form, if applicable.
    """

    model_config = ConfigDict(extra="forbid")

    # Maintained list of Deprecated Options, with a guidance message
    # Deprecated options are tolerated in the schema, but a warning
    # is logged when they are encountered.
    DEPRECATED_OPTIONS: ClassVar[dict[str, str]] = {
        # "old_option": "removed in 3.1; use 'new_option' instead",
    }

    # Valid logging level names accepted by the ``log_level`` option.
    VALID_LOG_LEVELS: ClassVar[frozenset[str]] = frozenset(
        {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    )

    debug: bool = False  # Debug mode, enable verbose on root logger
    log_level: str = "INFO"  # Default log level for the application
    log_file: str = Field(  # Default log file for the application
        default_factory=lambda: str(fspaths.LOG_DIR / "exosphere.log")
    )
    log_max_bytes: int = Field(  # Rotate log file past this size (5 MiB)
        default=5 * 1024 * 1024, ge=0
    )
    log_backup_count: int = Field(default=3, ge=1)  # Rotated log files to keep.
    history_file: str = Field(  # Default history file for the repl
        default_factory=lambda: str(fspaths.STATE_DIR / "repl_history")
    )
    history_max_entries: int = Field(  # Trim repl history to this many entries
        default=1000, ge=0
    )
    cache_autosave: bool = True  # Automatically save cache to disk after changes
    cache_autopurge: bool = True  # Automatically purge hosts removed from inventory
    cache_file: str = Field(  # Default cache file for the application
        default_factory=lambda: str(fspaths.STATE_DIR / "exosphere.db")
    )
    stale_threshold: int = Field(  # How long before a host is considered stale
        default=86400, ge=0
    )
    default_timeout: int = Field(  # Default ssh connection timeout (in seconds)
        default=10, ge=1
    )
    default_username: NonEmptyStr | None = None  # Default global SSH username
    default_sudo_policy: SudoPolicyName = "skip"  # Global sudo policy for pkg ops
    max_threads: int = Field(default=15, ge=1)  # Max threads for parallel ops
    ssh_pipelining: bool = False  # Enable SSH pipelining for SSH connections
    ssh_pipelining_lifetime: int = Field(  # Max lifetime (secs) of SSH connections
        default=300, ge=1
    )
    ssh_pipelining_reap_interval: int = Field(  # Interval (secs) between reaper checks
        default=30, ge=1
    )
    update_checks: bool = True  # Set to false if you want to disable PyPI checks
    no_banner: bool = False  # Disable the REPL banner on startup
    editor: NonEmptyStr | None = None  # Editor command for `config edit`

    @model_validator(mode="before")
    @classmethod
    def drop_deprecated(cls, data: Any) -> Any:
        # Pop intentionally-removed options with a warning before
        # validation runs, so old configs survive upgrades while
        # actual mistakes are still fatal.
        if isinstance(data, dict):
            logger = logging.getLogger(__name__)
            for key in cls.DEPRECATED_OPTIONS.keys() & data.keys():
                logger.warning(
                    "Configuration option '%s' is no longer used (%s), ignoring.",
                    key,
                    cls.DEPRECATED_OPTIONS[key],
                )
                data = {k: v for k, v in data.items() if k != key}
        return data

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        candidate = value.upper()
        if candidate not in cls.VALID_LOG_LEVELS:
            valid = ", ".join(sorted(cls.VALID_LOG_LEVELS))
            raise ValueError(f"invalid log level {value!r}; must be one of: {valid}")
        return candidate

    @model_validator(mode="after")
    def validate_reaper_interval(self) -> "OptionsModel":
        if self.ssh_pipelining_reap_interval > self.ssh_pipelining_lifetime:
            raise ValueError(
                "ssh_pipelining_reap_interval cannot be greater than "
                "ssh_pipelining_lifetime"
            )
        return self


class HostModel(BaseModel):
    """
    Schema for a host entry in the ``hosts`` configuration section.

    Parameters very much line up with :class:`exosphere.objects.Host`,
    and this is on purposes, but unknown keys are ignored (with a
    warning) rather than rejected, to keep this section more forgiving
    of typos and legacy options across upgrades and migrations.
    """

    model_config = ConfigDict(extra="ignore")

    name: NonEmptyStr
    ip: NonEmptyStr
    port: int = Field(default=22, ge=1, le=65535)
    username: NonEmptyStr | None = None
    description: str | None = None
    connect_timeout: int | None = Field(default=None, ge=1)
    sudo_policy: SudoPolicyName | None = None

    @model_validator(mode="before")
    @classmethod
    def warn_unknown_keys(cls, data: Any) -> Any:
        if isinstance(data, dict):
            unknown = set(data) - set(cls.model_fields)
            if unknown:
                name = data.get("name", "(unnamed)")
                logger = logging.getLogger(__name__)
                for key in sorted(unknown):
                    logger.warning(
                        "Unknown host configuration option '%s' for host '%s', "
                        "ignoring.",
                        key,
                        name,
                    )
        return data

    @field_validator("ip")
    @classmethod
    def validate_ip(cls, value: str) -> str:
        # IP field cannot contain '@' character.
        # SSH library will interpret this as a username, which will
        # result in a lot of exciting "undefined behaviors".
        if "@" in value:
            raise ValueError(
                "'@' character is not allowed in hostname or ip. "
                "Use the 'username' option to specify a username"
            )
        return value


class ConfigModel(BaseModel):
    """
    Top-level configuration schema, combining global options and the host
    inventory. Used to validate and normalize the configuration as a whole.
    """

    model_config = ConfigDict(extra="forbid")

    options: OptionsModel = Field(default_factory=OptionsModel)
    hosts: list[HostModel] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_host_names(self) -> "ConfigModel":
        names = [host.name for host in self.hosts]
        dupes = sorted({name for name in names if names.count(name) > 1})
        if dupes:
            raise ValueError(
                f"Duplicate host names found in configuration: {', '.join(dupes)}"
            )
        return self


def validate(file: str | Path) -> None:
    """
    Validate a configuration file on disk, raising on any problem.

    The provided file must be one of the known formats, dictated by the
    KNOWN_LOADERS mapping in the same module.

    :param file: Path to the configuration file to validate.
    :raises ValueError: if the file extension has no known loader.
    :raises Exception: any parsing or validation error raised while loading.
    """
    ext = Path(file).suffix.removeprefix(".").lower()
    loader = KNOWN_LOADERS.get(ext)

    if loader is None:
        raise ValueError(f"Unknown configuration file extension: {ext!r}")

    Configuration().from_file(str(file), loader)


class Configuration(dict):
    """
    Hold configuration values for the application.
    Extends a native dict to store the global options section of the
    inventory toml file.

    Has the following peculiarities vs a native dict:

    - Has many ``from_*`` methods to populate itself from various
      sources such as environment variables, files of various formats
    - Enforces a set of default values for the nested ``options`` dict
    - Enforces unicity for name keys in the ``hosts`` dict.
    - Has a :meth:`deep_update` method to recursively update nested dicts
      without replacing them entirely.
    - Is entirely self-validating and normalizing, using a pydantic
      schema to ensure the configuration is always in a valid state

    This configuration structure is strongly inspired by the one used
    by Flask, because good things are worth replicating.
    """

    #: Default configuration values
    #: This dict contains the default configuration and is always
    #: used as a base for what the configuration object contains.
    #: This can be accessed to get the default values for any config key.
    #: It is derived directly from the :class:`OptionsModel` schema.
    DEFAULTS: dict[str, Any] = {
        "options": OptionsModel().model_dump(),
        "hosts": [],
    }

    def __init__(self) -> None:
        """
        Initialize the Configuration object with default values.

        The default values are a deep copy of the DEFAULTS dict,
        ensuring that the original DEFAULTS remains unchanged.
        """
        dict.__init__(self, copy.deepcopy(self.DEFAULTS))
        self.logger = logging.getLogger(__name__)

    def from_env(
        self,
        prefix: str = "EXOSPHERE_OPTIONS",
        parser: Callable[[str], Any] = json.loads,
    ) -> bool:
        """
        Populate the configuration structure from environment variables.

        Any environment variable that starts with the specified prefix
        (e.g., ``EXOSPHERE_OPTIONS_*``) will be considered for updating
        the configuration.

        Note that this is, currently, limited to the `options` section
        of the configuration. The inventory cannot be updated this way.

        If there are any nested dictionaries in the configuration,
        you can specify them using a double underscore (``__``) to
        separate the keys.

        The values for the keys are parsed as JSON types by default,
        but you can specify a custom loader function to parse the values,
        as long as it operates on strings.

        Invalid keys or values will be be ignored and logged as
        warnings, and nested dictionary keys will have their entire
        subtree dropped if any of the leaves are invalid.

        :param prefix: The prefix to look for in environment variables
        :param parser: A callable that takes a string and returns a parsed value
        :return: True if the configuration was successfully updated
        """
        prefix = prefix.upper() + "_"

        options: dict[str, Any] = {}

        for key in os.environ:
            if not key.startswith(prefix):
                continue

            value = os.environ[key]
            key = key.removeprefix(prefix).lower()

            try:
                value = parser(value)
            except Exception:
                self.logger.debug(
                    "Could not parse environment variable %s: %s, keeping as string",
                    key,
                    value,
                )

            if "__" not in key:
                # Not a nested key, update
                if key in self.DEFAULTS["options"]:
                    self.logger.debug(
                        "Updating configuration key from env %s: %s", key, value
                    )
                    options[key] = value
                else:
                    self.logger.warning(
                        "Configuration key %s is not a valid options key, ignoring", key
                    )
                continue

            # We have a nested key
            current = options
            *parent_keys, leaf_key = key.split("__")

            for parent in parent_keys:
                # Create nested dict if it doesn't exist
                if parent not in current:
                    current[parent] = {}

                current = current[parent]

            current[leaf_key] = value

        # Environment overrides are best effort - unlike a config file
        # they really are just an amalgamation of transient overrides
        # leaking from the ceiling of the building where the app is
        # running.
        #
        # Invalid values are therefore ignored and logged as warnings
        # rather than aborting startup. Try the whole batch first (the common
        # case, one validation); only if that fails do we figure out which
        # overrides are bad and drop them, keeping the rest.
        try:
            return self.update_from_mapping({"options": options})
        except Exception:
            # Fall through to best-effort recovery below. A bad env override
            # must never be fatal, so we deliberately swallow anything here.
            self.logger.debug(
                "Environment overrides failed validation, falling back to best-effort"
            )

        # Drop offending overrides until the remainder validates.
        # Candidate set is validated as a batch for two reasons:
        #
        # 1. Options sharing a joint constraint are checked together,
        #    so an override that is valid only because of another
        #    specified override is not dropped by being checked on
        #    their own.
        # 2. Avoids systematically running the validation on each key
        #
        candidate = dict(options)
        while candidate:
            try:
                OptionsModel.model_validate({**self["options"], **candidate})
                break
            except ValidationError as exc:
                self._drop_invalid_env_overrides(candidate, exc)

        return self.update_from_mapping({"options": candidate})

    def _drop_invalid_env_overrides(
        self, candidate: dict[str, Any], exc: ValidationError
    ) -> None:
        """
        Remove invalid config overrides from candidate based on Exception

        :param candidate: Mapping of pending overrides, mutated in place.
        :param exc: The validation error to attribute and report.
        """
        reasons: dict[str, list[str]] = {}
        unattributable: list[str] = []

        for error in exc.errors():
            loc = error["loc"]

            # Strip pydantic's "Value error, " prefix from custom validators
            message = error["msg"].removeprefix("Value error, ")

            if loc and loc[0] in candidate:
                reasons.setdefault(str(loc[0]), []).append(message)
            else:
                unattributable.append(message)

        culprits = set(reasons) or set(candidate)

        for key in sorted(culprits):
            value = candidate.pop(key)

            subtree = (
                " (entire nested subtree dropped)" if isinstance(value, dict) else ""
            )
            detail = "; ".join(reasons.get(key, unattributable))

            self.logger.warning(
                "Ignoring invalid environment override for '%s'%s: %s",
                key,
                subtree,
                detail,
            )

    def from_toml(self, filepath: str, silent: bool = False) -> bool:
        """
        Populate the configuration structure from a toml file

        This method is a convenience wrapper used for shorthand
        for the from_file method, with `tomllib.load()` as the loader.

        see :meth:`from_file` for details.

        :param filepath: Path to the toml file to load
        :param silent: If True, suppress IOError exceptions for missing files
        :return: True if the configuration was successfully updated,
                 False if the file was not found
        """
        return self.from_file(filepath, tomllib.load, silent=silent)

    def from_yaml(self, filepath: str, silent: bool = False) -> bool:
        """
        Populate the configuration structure from a yaml file

        This method is a convenience wrapper used for shorthand
        for the `from_file` method, with `yaml.safe_load()` as the loader.

        see :meth:`from_file` for details.

        :param filepath: Path to the yaml file to load
        :param silent: If True, suppress IOError exceptions for missing files
        :return: True if the configuration was successfully updated,
                 False if the file was not found
        """
        return self.from_file(filepath, yaml.safe_load, silent=silent)

    def from_json(self, filepath: str, silent: bool = False) -> bool:
        """
        Populate the configuration structure from a json file

        This method is a convenience wrapper used for shorthand
        for the `from_file` method, with `json.load()` as the loader.

        see :meth:`from_file` for details.

        :param filepath: Path to the json file to load
        :param silent: If True, suppress IOError exceptions for missing files
        :return: True if the configuration was successfully updated,
                 False if the file was not found
        """
        return self.from_file(filepath, json.load, silent=silent)

    def from_file(
        self, filepath: str, loader: Callable[[BinaryIO], dict], silent: bool = False
    ) -> bool:
        """
        Populate the configuration structure from a file, with a
        specified loader function callable.

        The loader must be a reference to a callable that takes a
        file handle and returns a mapping of the data contained within.

        For instance, `tomllib.load()` is a valid loader for toml files

        This allows for the format of the configuration file to be
        essentially decoupled from the validation and internal
        representation of the data.

        :param filepath: Path to the file to load
        :param loader: A callable that takes a file handle and returns a dict
        :param silent: If True, suppress IOError exceptions for missing files
        :return: True if the configuration was successfully updated
        """
        try:
            with open(filepath, "rb") as f:
                raw = f.read()
        except IOError as e:
            if silent and e.errno in (errno.ENOENT, errno.EISDIR):
                return False

            e.strerror = f"Unable to load config file {filepath}: {e.strerror}"

            raise

        # An empty file is technically valid (override nothing, keep
        # defaults). Given how not all loaders handle this the same, we
        # handle it explicitly here.
        if not raw.strip():
            self.logger.warning(
                "Configuration file %s is empty, using defaults", filepath
            )
            return True

        data = loader(io.BytesIO(raw))

        # SOME loaders can and will return None for a comments-only file.
        # This is still technically valid, and is an "empty" file.
        if data is None:
            self.logger.warning(
                "Configuration file %s has no values, using defaults", filepath
            )
            return True

        # All loaders should return a mapping, but just in case it's done as
        # a library or at runtime, we check this explicitly here.
        if not isinstance(data, dict):
            raise ValueError(
                f"Configuration file {filepath} must contain a mapping at the "
                f"top level, got {type(data).__name__}"
            )

        return self.update_from_mapping(data)

    def deep_update(self, d: dict, u: dict) -> dict:
        """
        Recursively update a dictionary with another dictionary.
        Ensures nested dicts are updated rather than replaced.

        :param d: The dictionary to update
        :param u: The dictionary with updates
        :return: The updated dictionary
        """
        for k, v in u.items():
            if isinstance(v, dict) and k in d and isinstance(d[k], dict):
                self.deep_update(d[k], v)
            else:
                d[k] = v
        return d

    def update_from_mapping(self, *mapping: dict, **kwargs: dict) -> bool:
        """
        Populate values like the native `dict.update()` method, but
        only if the key is a valid root configuration key.

        This will also deep merge the values from the mapping
        if they are also dicts.

        This method is transactional: validation errors within the
        mapping will roll back any partial changes, guaranteeing that
        the configuration is always in a valid state.

        :param mapping: A single mapping to update the configuration with
        :param kwargs: Additional keyword arguments to update the configuration with
        :return: True if the configuration was successfully updated
        """
        mappings = []

        if len(mapping) == 1:
            if hasattr(mapping[0], "items"):
                mappings.append(mapping[0].items())
            else:
                mappings.append(mapping[0])
        elif len(mapping) > 1:
            raise TypeError(
                f"Config mapping expected at most 1 positional argument, "
                f"got {len(mapping)}"
            )

        mappings.append(kwargs.items())

        # Create a deep copy snapshot of the mutable root sections, so
        # a failed validation can be rolled back.
        snapshot = {key: copy.deepcopy(self[key]) for key in self.DEFAULTS}

        try:
            # Parse and filter mappings
            for mapping in mappings:
                for k, v in mapping:
                    if k in self.DEFAULTS:
                        if isinstance(self[k], dict) and isinstance(v, dict):
                            # deep merge the dicts
                            self.deep_update(self[k], v)
                        else:
                            self[k] = v
                    else:
                        self.logger.warning(
                            "Configuration key %s is not a valid root key, ignoring", k
                        )

            # Perform validation and normalization for the configuration
            # Since everything routes through this method, it will always
            # be in charge of raising validation errors.
            self._validate_and_normalize()
        except Exception:
            # Woops, the validation or slicing failed!
            # Roll back any partial mutation before re-raising
            self.logger.debug("Rolling back config values due to validation error")
            for key, value in snapshot.items():
                self[key] = value
            raise

        return True

    def _validate_and_normalize(self) -> None:
        """
        Validate and normalize the configuration against the schema.

        This method will run the pydantic schema (:class:`ConfigModel`)
        over both the ``options`` and ``hosts`` sections of the
        configuration structure, then write the results back into
        place.

        Unknown option keys are rejected, unknown host keys are dropped
        with a warning, and values are coerced to their legit,
        canonical form (e.g. types fixed, log levels uppercased, etc).

        :raises ValueError: if the configuration fails schema validation
        """
        try:
            model = ConfigModel.model_validate(
                {"options": self["options"], "hosts": self["hosts"]}
            )
        except ValidationError as exc:
            # Turn the Pydantic ValidationError into an API agnostic
            # ValueError with a friendly list of problems as message.
            # I don't love this and optimally we'd raise our own
            # ConfigurationError type, but that refactor would be
            # much bigger than I'd like for the time being.
            hosts = self["hosts"]
            problems = []
            for error in exc.errors():
                loc = list(error["loc"])

                # Identify a host by its name rather than its list index.
                # No one likes counting entries in yaml or toml.
                if len(loc) >= 2 and loc[0] == "hosts" and isinstance(loc[1], int):
                    entry = hosts[loc[1]] if loc[1] < len(hosts) else None
                    if isinstance(entry, dict) and entry.get("name"):
                        loc[1] = entry["name"]
                location = ".".join(str(part) for part in loc)

                # Strip pydantic's prefix on custom validators
                message = error["msg"].removeprefix("Value error, ")

                # Top-level (model) errors have no location, just show
                # the message instead of "(root)" which helps no one.
                problems.append(
                    f"  - {location}: {message}" if location else f"  - {message}"
                )

            raise ValueError("\n".join(problems)) from exc

        self["options"] = model.options.model_dump()
        self["hosts"] = [host.model_dump(exclude_unset=True) for host in model.hosts]
