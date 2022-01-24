import logging
import sys
import time
from typing import Callable

import typer
from click import ClickException

from . import logger
from .status import ExitCode, ExitCodes

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"], max_content_width=88)


def run(cli: typer.Typer):
    start = time.time()
    log = logging.getLogger(__name__)
    log.info(f"Invocation started of: {' '.join(sys.argv)}")
    try:
        # prevent Typer from catching and printing (click) exceptions (standalone_mode)
        status = cli(standalone_mode=False)
        if not isinstance(status, ExitCode):
            log.warning(
                f"Invalid exit code {status} ({type(status)}); falling back to"
                f" {ExitCodes.INTERNAL_ERROR}"
            )
            status = ExitCodes.INTERNAL_ERROR

    except ClickException as e:
        log.critical(f"{e.format_message()}")
        status = ExitCodes.CLI_ERROR
    except Exception as e:
        import traceback

        limit = None if logger.level is None or logger.level <= logging.DEBUG else -2
        tb = "".join(traceback.format_exception(e.__class__, e, e.__traceback__, limit))
        log.critical(f"Uncaught exception {e.__class__.__name__}: {e}\n{tb}")
        status = getattr(e, "code", None)
        if not isinstance(status, ExitCode):
            log.warning(
                f"Invalid exit code {status} ({type(status)}); falling back to"
                f" {ExitCodes.INTERNAL_ERROR}"
            )
            status = ExitCodes.INTERNAL_ERROR

    log.info(f"Invocation took {time.time() - start:6f}s")

    if status != ExitCodes.SUCCESS and not logger.initialised:
        from datetime import datetime

        timestamp = datetime.utcnow().strftime("%Y%m%dt%H%M%Sz")
        fallback = logger.fallback_dir() / f"processing_failure_{timestamp}.log"
        log.warning(
            "Logger not initialised; writing debug log to fallback location:"
            f" '{fallback}'"
        )
        logger.init(
            file=fallback,
            stdout=(status == ExitCodes.CLI_ERROR),
            mode="a",
            log_level=logging.DEBUG,
        )

    log.info(f"Exiting with code {status}")
    logging.shutdown()
    sys.exit(status.code)


def version_callback_for(name: str, version: str) -> Callable[[bool], None]:
    def version_callback(value: bool) -> None:
        if value:
            typer.echo(f"{name} v{version}")
            raise typer.Exit()

    return version_callback
