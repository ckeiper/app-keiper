"""Bounded HTTP budget for XLSX parsing on the shared Render CPU.

The real 1.9 MB reconciliation report took 23 seconds even with a single pass.
The default 30-second worker timeout left no margin for normal CPU variation.
Application upload/ZIP/row limits remain the primary resource bounds.
"""
timeout = 120


def worker_exit(server, worker):
    # Runs in the retiring worker before Python shuts down thread executors.
    from scheduler_lifecycle import stop_application_scheduler

    stop_application_scheduler()


def on_exit(server):
    # Also covers the master when the application was loaded with --preload.
    from scheduler_lifecycle import stop_application_scheduler

    stop_application_scheduler()
