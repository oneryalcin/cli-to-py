"""Help text fixtures mirrored from cli-to-js integration tests.

These are deliberately kept as literal strings (not run against live binaries)
so unit tests are fast, deterministic, and portable.
"""

from __future__ import annotations

REACT_GRAB_HELP = """Usage: grab [options] [command]

add React Grab to your project

Options:
  -v, --version                  display the version number
  -h, --help                     display help for command

Commands:
  init|setup [options]           initialize React Grab in your project
  add|install [options] [agent]  connect React Grab to your agent via MCP
  remove [options] [agent]       disconnect React Grab from your agent
  configure|config [options]     configure React Grab options
  upgrade|update [options]       upgrade react-grab to the latest version
  help [command]                 display help for command
"""

REACT_GRAB_INIT_HELP = """Usage: grab init|setup [options]

initialize React Grab in your project

Options:
  -y, --yes        skip confirmation prompts (default: false)
  -f, --force      force overwrite existing config (default: false)
  -k, --key <key>  activation key (e.g., Meta+K, Ctrl+Shift+G, Space)
  --skip-install   skip package installation (default: false)
  --pkg <pkg>      custom package URL for CLI (e.g., grab)
  -c, --cwd <cwd>  working directory (defaults to current directory)
  -h, --help       display help for command
"""

REACT_DOCTOR_HELP = """Usage: react-doctor [options] [directory]

Diagnose React codebase health

Arguments:
  directory          project directory to scan (default: ".")

Options:
  -v, --version      display the version number
  --lint             enable linting
  --no-lint          skip linting
  --dead-code        enable dead code detection
  --no-dead-code     skip dead code detection
  --verbose          show file details per rule
  --score            output only the score
  -y, --yes          skip prompts, scan all workspace projects
  -n, --no           skip prompts, always run a full scan (decline diff-only)
  --project <name>   select workspace project (comma-separated for multiple)
  --diff [base]      scan only files changed vs base branch
  --offline          skip telemetry (anonymous, not stored, only used to
                     calculate score)
  --staged           scan only staged (git index) files for pre-commit hooks
  --fail-on <level>  exit with error code on diagnostics: error, warning, none
                     (default: "none")
  --annotations      output diagnostics as GitHub Actions annotations
  -h, --help         display help for command
"""

CLAP_STYLE_HELP = """An extremely fast Python package manager.

Usage: uv [OPTIONS] <COMMAND>

Commands:
  auth     Manage authentication
  run      Run a command or script
  init     Create a new project
  add      Add dependencies to the project

Cache options:
  -n, --no-cache               Avoid reading from or writing to the cache
      --cache-dir <CACHE_DIR>  Path to the cache directory

Global options:
  -q, --quiet...               Use quiet output
  -v, --verbose...             Use verbose output
      --color <COLOR_CHOICE>   Control the use of color in output [possible values: auto, always, never]
  -h, --help                   Display the concise help
  -V, --version                Display the uv version
"""
