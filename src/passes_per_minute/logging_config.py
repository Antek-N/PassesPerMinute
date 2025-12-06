"""
Unified configuration of color-aware UTC logging for console and file.

Global logging configuration in Python: colorful logs in the console (ANSI, if supported),
timestamps in UTC format, and optional file output. The module automatically detects the
environment (VS Code, PyCharm, Jupyter, CI, Windows/Unix) and decides whether to enable
colors. This ensures consistent, readable logs with a unified format across the entire project.

Usage (once at startup):
    from logging_config import configure_logging, add_file_logging
    configure_logging()          # colorful logs to stderr (MUST be called first)
    add_file_logging("app.log")  # optional: log to file (UTC, no colors)

Then:
    import logging
    log = logging.getLogger(__name__)
    log.info("Sample info")
    log.error("Sample error")

Parameters:
- configure_logging(
      level=logging.DEBUG,    # minimum log level
      stream=sys.stderr,      # where to write logs (e.g., sys.stdout)
      format_string="...",    # message format (default: ISO-8601 UTC)
      date_format="...",      # date format
      replace_handlers=False, # True → removes old handlers and sets new ones
      capture_warnings=True   # redirects warnings module output to logs
  )

- add_file_logging(
      path,                   # path to log file
      level=logging.DEBUG,    # minimum log level for file
      format_string="...",    # message format (UTC)
      date_format="...",      # date format
      encoding="utf-8"        # file encoding
  )

Important:
- Always call configure_logging() first, then optionally add_file_logging().
- Call both functions only once. Afterward, use log = logging.getLogger(__name__).
- Colors: `FORCE_COLOR=1` enforces colors, `NO_COLOR=1` disables them
  (set as environment variables before running the program).
"""

import logging
import os
import sys
import time
from dataclasses import dataclass
from typing import IO

__all__ = ["configure_logging", "add_file_logging"]


COLORS = {
    "DEBUG": "\033[90m",
    "INFO": "\033[32m",
    "WARNING": "\033[93m",
    "ERROR": "\033[91m",
    "CRITICAL": "\033[97;41m",
    "RESET": "\033[0m",
}


@dataclass(frozen=True)
class ColorSupport:
    """
    Represents whether ANSI color output is supported in the current environment.

    Attributes:
        supported (bool): True if ANSI colors are supported, False otherwise.
        reason (Optional[str]): Explanation why colors are not supported (if applicable).
        env_hint (Optional[str]): Environment hint to provide user-specific tips (e.g. 'vscode', 'pycharm').
    """

    supported: bool
    reason: str | None = None
    env_hint: str | None = None


class ColorEnv:
    """
    Detects environment characteristics related to color/ANSI support
    and provides methods to enable or disable ANSI colors in different terminals.
    """

    _WINDOWS_ANSI_ENABLED = False
    _COLOR_HINT_SHOWN = False

    @staticmethod
    def is_ci() -> bool:
        """
        Detects if the current process is running inside a CI environment.

        :return: True if running in a known CI system, False otherwise.
        """
        return os.environ.get("CI") == "1" or any(
            os.environ.get(env_var)
            for env_var in (
                "GITHUB_ACTIONS",
                "GITLAB_CI",
                "TF_BUILD",
                "TEAMCITY_VERSION",
                "BUILDKITE",
                "TRAVIS",
                "CIRCLECI",
                "APPVEYOR",
                "DRONE",
                "JENKINS_URL",
            )
        )

    @staticmethod
    def is_vscode() -> bool:
        """
        Detects if the process is running inside VS Code's Integrated Terminal or Debug Console.

        :return: True if running in VS Code, False otherwise.
        """
        return bool(os.environ.get("TERM_PROGRAM") == "vscode" or os.environ.get("VSCODE_PID"))

    @staticmethod
    def is_pycharm() -> bool:
        """
        Detects if the process is running inside the PyCharm IDE.

        :return: True if running in PyCharm, False otherwise.
        """
        return bool(os.environ.get("PYCHARM_HOSTED"))

    @staticmethod
    def is_windows_terminal() -> bool:
        """
        Detects if the process is running in Windows Terminal or ConEmu.

        :return: True if running in Windows Terminal or ConEmu, False otherwise.
        """
        return bool(os.environ.get("WT_SESSION") or os.environ.get("ConEmuPID"))

    @staticmethod
    def is_jupyter() -> bool:
        """
        Detects if the process is running inside a Jupyter or Spyder kernel.

        :return: True if in Jupyter, False otherwise.
        """
        try:
            import ipykernel  # noqa: F401

            return True
        except ImportError:
            return False

    @classmethod
    def ensure_windows_ansi(cls) -> None:
        """
        Ensures that ANSI escape sequences are enabled in Windows consoles.
        Requires the `colorama` package.

        :return: None
        """
        if cls._WINDOWS_ANSI_ENABLED or os.name != "nt":
            return

        try:
            import colorama  # noqa E402
        except ImportError:
            return

        colorama.just_fix_windows_console()
        cls._WINDOWS_ANSI_ENABLED = True

    @staticmethod
    def stream_isatty(stream: IO[str]) -> bool:
        """
        Checks whether a given stream is connected to a TTY (interactive terminal).

        :param stream: The stream to check.
        :return: True if the stream is a TTY, False otherwise.
        """
        try:
            return hasattr(stream, "isatty") and callable(stream.isatty) and stream.isatty()
        except (OSError, ValueError):
            return False

    @classmethod
    def color_support_with_reason(cls, stream: IO[str]) -> ColorSupport:
        """
        Determines whether colors are supported in the current environment,
        including reasons and environment hints if disabled.

        :param stream: The output stream (e.g. sys.stderr).
        :return: A ColorSupport instance with the decision and explanation.
        """
        if os.environ.get("FORCE_COLOR"):
            cls.ensure_windows_ansi()
            return ColorSupport(True)

        if os.environ.get("NO_COLOR"):
            return ColorSupport(False, "NO_COLOR is set.", None)

        if cls.is_pycharm():
            cls.ensure_windows_ansi()
            return ColorSupport(True, env_hint="pycharm")

        if cls.is_vscode():
            cls.ensure_windows_ansi()
            return ColorSupport(True, env_hint="vscode")

        if cls.is_windows_terminal():
            cls.ensure_windows_ansi()

        if cls.is_jupyter():
            return ColorSupport(True, env_hint="jupyter")

        if not cls.stream_isatty(stream):
            return ColorSupport(False, "Output is not a TTY (file/pipe/IDE wo/ emulation).", None)

        if os.name == "nt":
            cls.ensure_windows_ansi()
            return (
                ColorSupport(True)
                if cls._WINDOWS_ANSI_ENABLED
                else ColorSupport(False, "Windows without 'colorama'.", "windows")
            )

        terminal_type = os.environ.get("TERM", "")
        if terminal_type in ("", "dumb"):
            return ColorSupport(False, f"TERM={terminal_type!r} does not support ANSI.", "unix")

        return ColorSupport(True)

    @classmethod
    def maybe_show_color_hint(cls, reason: str | None, env_hint: str | None) -> None:
        """
        Optionally prints a hint to stderr explaining why colors are disabled
        and how to enable them, depending on the environment.

        :param reason: Reason why colors are disabled.
        :param env_hint: Environment hint (if available).
        :return: None
        """
        if cls._COLOR_HINT_SHOWN or cls.is_ci() or os.environ.get("LOG_COLOR_HINT") != "1":
            return

        if not reason:
            return

        cls._COLOR_HINT_SHOWN = True

        base_tips = [
            "- If redirecting to a file/pipeline: colors are intentionally disabled.",
            "- Remove the `NO_COLOR` variable if it's set.",
            "- You can force colors: `FORCE_COLOR=1`.",
        ]

        env_tips = {
            "pycharm": ["- PyCharm: enable **Run → Emulate terminal in output console**."],
            "vscode": [
                "- VS Code: use the **Integrated Terminal** (View → Terminal),",
                "  or set `FORCE_COLOR=1` in your Debug Configuration.",
            ],
            "windows": ["- Windows: `pip install colorama` or run in Windows Terminal."],
            "unix": [
                "- Linux/macOS: ensure `TERM` is something like `xterm-256color`.",
                "- In Docker, run with a TTY: `docker run -it ...`.",
            ],
            "jupyter": ["- Jupyter: colors usually work; to disable set `NO_COLOR=1`."],
            None: [
                "- Windows: consider **Windows Terminal** or `pip install colorama`.",
                "- VS Code/PyCharm: run via the **Integrated/Emulated Terminal**.",
                "- Docker: add `-t` (pseudo-TTY).",
            ],
        }

        tips = env_tips.get(env_hint, env_tips[None])

        message = (
            "[log-color] Colors are disabled: "
            f"{reason}  How to enable them:\n  "
            + "\n  ".join(tips + base_tips)
            + "\n  (Silence tips: LOG_COLOR_HINT=0 / off by default)"
        )

        try:
            print(message, file=sys.stderr)
        except (OSError, ValueError):
            pass


class UtcFormatter(logging.Formatter):
    """
    Formatter that enforces UTC timestamps for log records.
    """

    @staticmethod
    def _converter(secs: float | None) -> time.struct_time:
        return time.gmtime(0 if secs is None else secs)

    converter = _converter


class ColoredFormatter(UtcFormatter):
    """
    A log formatter that applies ANSI color codes to messages based on log level.

    Extends UtcFormatter to add colorization when enabled.
    """

    def __init__(self, format_string: str, date_format: str | None, use_color: bool) -> None:
        super().__init__(fmt=format_string, datefmt=date_format)
        self.use_color = use_color

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)

        if not self.use_color:
            return message

        color = COLORS.get(record.levelname, COLORS["RESET"])
        return f"{color}{message}{COLORS['RESET']}"


class HandlerFactory:
    """
    Factory for creating logging handlers with appropriate formatters
    (stream handlers with optional colors, or file handlers without colors).
    """

    @staticmethod
    def stream_handler(stream: IO[str], fmt: str, date_format: str) -> logging.Handler:
        handler = logging.StreamHandler(stream)
        handler.setLevel(logging.NOTSET)

        support = ColorEnv.color_support_with_reason(stream)
        if not support.supported:
            ColorEnv.maybe_show_color_hint(support.reason, support.env_hint)

        handler.setFormatter(ColoredFormatter(format_string=fmt, date_format=date_format, use_color=support.supported))
        return handler

    @staticmethod
    def file_handler(path: str, fmt: str, date_format: str, encoding: str = "utf-8") -> logging.Handler:
        absolute_path = os.path.abspath(path)
        handler = logging.FileHandler(absolute_path, encoding=encoding)
        handler.setLevel(logging.NOTSET)
        handler.setFormatter(UtcFormatter(fmt=fmt, datefmt=date_format))
        return handler


class LoggingConfigurator:
    """
    Provides high-level configuration methods for setting up logging
    with optional color support for console and file handlers.
    """

    @staticmethod
    def configure(
        level: int = logging.DEBUG,
        stream: IO[str] = sys.stderr,
        format_string: str = "%(asctime)s.%(msecs)03dZ [%(levelname)s] %(name)s: %(message)s",
        date_format: str = "%Y-%m-%dT%H:%M:%S",
        *,
        replace_handlers: bool = False,
        capture_warnings: bool = True,
    ) -> None:
        """
        Configures global logging with colorized console output.

        :param level: Minimum logging level (default DEBUG).
        :param stream: Stream to log to (default sys.stderr).
        :param format_string: Log message format string.
        :param date_format: Date/time format string.
        :param replace_handlers: If True, removes existing handlers first.
        :param capture_warnings: If True, redirects warnings to logging.
        :return: None
        """
        root = logging.getLogger()

        if replace_handlers:
            for handler in root.handlers[:]:
                root.removeHandler(handler)
            if hasattr(root, "_colored_logging_configured"):
                delattr(root, "_colored_logging_configured")

        if getattr(root, "_colored_logging_configured", False) and not replace_handlers:
            if capture_warnings:
                logging.captureWarnings(True)
            return

        root.setLevel(level)
        root.addHandler(HandlerFactory.stream_handler(stream, format_string, date_format))
        root._colored_logging_configured = True  # type: ignore[attr-defined]

        if capture_warnings:
            logging.captureWarnings(True)

    @staticmethod
    def add_file_logging(
        path: str,
        level: int = logging.DEBUG,
        format_string: str = "%(asctime)s.%(msecs)03dZ [%(levelname)s] %(name)s: %(message)s",
        date_format: str = "%Y-%m-%dT%H:%M:%S",
        encoding: str = "utf-8",
    ) -> None:
        """
        Adds a file handler to the global logger, writing logs in UTC.

        :param path: Path to the log file.
        :param level: Minimum logging level (default DEBUG).
        :param format_string: Log message format string.
        :param date_format: Date/time format string.
        :param encoding: File encoding (default UTF-8).
        :return: None
        """
        root = logging.getLogger()
        absolute_path = os.path.abspath(path)

        for handler in root.handlers:
            if isinstance(handler, logging.FileHandler) and getattr(handler, "baseFilename", None) == absolute_path:
                if root.level > level:
                    root.setLevel(level)
                return

        root.addHandler(HandlerFactory.file_handler(absolute_path, format_string, date_format, encoding))

        if root.level > level:
            root.setLevel(level)


def configure_logging(
    level: int = logging.DEBUG,
    stream: IO[str] = sys.stderr,
    format_string: str = "%(asctime)s.%(msecs)03dZ [%(levelname)s] %(name)s: %(message)s",
    date_format: str = "%Y-%m-%dT%H:%M:%S",
    *,
    replace_handlers: bool = False,
    capture_warnings: bool = True,
) -> None:
    """
    Public API to configure global logging with colorized console output.

    :param level: Minimum logging level (default DEBUG).
    :param stream: Stream to log to (default sys.stderr).
    :param format_string: Log message format string.
    :param date_format: Date/time format string.
    :param replace_handlers: If True, removes existing handlers first.
    :param capture_warnings: If True, redirects warnings to logging.
    :return: None
    """
    LoggingConfigurator.configure(
        level=level,
        stream=stream,
        format_string=format_string,
        date_format=date_format,
        replace_handlers=replace_handlers,
        capture_warnings=capture_warnings,
    )


def add_file_logging(
    path: str,
    level: int = logging.DEBUG,
    format_string: str = "%(asctime)s.%(msecs)03dZ [%(levelname)s] %(name)s: %(message)s",  # Default - ISO-8601
    date_format: str = "%Y-%m-%dT%H:%M:%S",
    encoding: str = "utf-8",
) -> None:
    """
    Public API to add file logging to the global logger.

    :param path: Path to the log file.
    :param level: Minimum logging level (default DEBUG).
    :param format_string: Log message format string.
    :param date_format: Date/time format string.
    :param encoding: File encoding (default UTF-8).
    :return: None
    """
    LoggingConfigurator.add_file_logging(
        path=path,
        level=level,
        format_string=format_string,
        date_format=date_format,
        encoding=encoding,
    )
