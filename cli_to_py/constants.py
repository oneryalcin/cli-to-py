"""Magic numbers and defaults for cli_to_py."""

import os


HELP_TIMEOUT_S: float = 10.0
COMMAND_TIMEOUT_S: float = 30.0
DESCRIPTION_CONTINUATION_INDENT_MIN: int = 6
COLUMN_SEPARATOR_MIN_SPACES: int = 2
SHORT_FLAG_MAX_LENGTH: int = 1
MAX_SUGGESTION_CUTOFF: float = 0.6

CACHE_DIR_ENV: str = "CLI_TO_PY_CACHE_DIR"
CACHE_DEFAULT_SUBDIR: str = "cli-to-py"
CACHE_SCHEMA_VERSION: int = 1


# binaries whose long flags render --flag=value by default. git's revision
# options (--format, --pretty, --color, --abbrev) accept ONLY the inline
# form, and its other value flags accept both. The default stays the space
# form because hand-rolled parsers reject inline: curl ("option
# --max-time=1: is unknown") and jq ("Unknown option --indent=2") (#10).
INLINE_VALUE_BINARIES = frozenset({"git"})


def default_inline_values(binary_name: str) -> bool:
    """Policy by executable name, so /usr/bin/git and git.exe count too."""
    name = os.path.basename(binary_name)
    return name.removesuffix(".exe") in INLINE_VALUE_BINARIES
