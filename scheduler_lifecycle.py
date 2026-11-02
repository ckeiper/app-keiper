"""Stop an already loaded application's scheduler before interpreter teardown."""
import logging
import os
import sys

from apscheduler.schedulers import SchedulerNotRunningError


logger = logging.getLogger("gunicorn.error.scheduler_lifecycle")


def stop_application_scheduler():
    """Never import the app here: shutdown must not initialize application jobs."""
    application = sys.modules.get("main")
    scheduler = getattr(application, "scheduler", None)
    if scheduler is None:
        return
    try:
        scheduler.shutdown(wait=False)
    except SchedulerNotRunningError:
        return
    except Exception:
        logger.exception("keiper_scheduler_shutdown_failed pid=%s", os.getpid())
        raise
    logger.info("keiper_scheduler_shutdown_complete pid=%s wait=false", os.getpid())
