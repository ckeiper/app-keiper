import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import Mock, patch

from apscheduler.schedulers import SchedulerNotRunningError
from scheduler_lifecycle import stop_application_scheduler


class SchedulerLifecycleTests(unittest.TestCase):
    def test_absent_application_does_not_import_it(self):
        with patch.dict(sys.modules, {"main": None}):
            stop_application_scheduler()
            self.assertIsNone(sys.modules["main"])

    def test_shutdown_is_nonblocking_and_idempotent(self):
        scheduler = Mock()
        scheduler.shutdown.side_effect = [None, SchedulerNotRunningError()]
        with patch.dict(sys.modules, {"main": types.SimpleNamespace(scheduler=scheduler)}):
            with self.assertLogs("gunicorn.error.scheduler_lifecycle", level="INFO") as logs:
                stop_application_scheduler()
                stop_application_scheduler()
        self.assertEqual(scheduler.shutdown.call_count, 2)
        scheduler.shutdown.assert_called_with(wait=False)
        self.assertEqual(len(logs.output), 1)
        self.assertIn("shutdown_complete", logs.output[0])

    def test_unexpected_failure_is_visible(self):
        scheduler = Mock()
        scheduler.shutdown.side_effect = RuntimeError("broken executor")
        with patch.dict(sys.modules, {"main": types.SimpleNamespace(scheduler=scheduler)}):
            with self.assertLogs("gunicorn.error.scheduler_lifecycle", level="ERROR"):
                with self.assertRaisesRegex(RuntimeError, "broken executor"):
                    stop_application_scheduler()

    def test_gunicorn_sigterm_stops_scheduling_and_finishes_active_job(self):
        # An isolated fake application: no customer data, database or ML calls.
        root = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            events = directory / "events"
            (directory / "main.py").write_text('''
import logging
import time
from pathlib import Path
from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler
logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
scheduler = BackgroundScheduler()
def job():
    with Path("events").open("a") as stream:
        stream.write("started\\n")
    time.sleep(1)
    with Path("events").open("a") as stream:
        stream.write("finished\\n")
scheduler.add_job(job, "interval", seconds=0.05, max_instances=1)
scheduler.start()
''')
            env = dict(os.environ, PYTHONPATH=str(root), GUNICORN_CMD_ARGS="")
            with (directory / "server.log").open("w+") as output:
                process = subprocess.Popen(
                    [sys.executable, "-m", "gunicorn", "--config", str(root / "gunicorn.conf.py"),
                     "--bind", "127.0.0.1:0", "--graceful-timeout", "8", "main:app"],
                    cwd=directory, env=env, stdout=output, stderr=subprocess.STDOUT,
                )
                try:
                    deadline = time.monotonic() + 10
                    while time.monotonic() < deadline:
                        if events.exists() and "started" in events.read_text():
                            break
                        if process.poll() is not None:
                            break
                        time.sleep(0.05)
                    self.assertTrue(events.exists(), "scheduled job did not start")
                    process.send_signal(signal.SIGTERM)
                    process.wait(timeout=12)
                    self.assertEqual(process.returncode, 0)
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.wait(timeout=5)
                output.seek(0)
                logs = output.read()
            self.assertIn("keiper_scheduler_shutdown_complete", logs)
            self.assertNotIn("cannot schedule new futures", logs)
            self.assertNotIn("Exception during worker exit", logs)
            self.assertEqual(events.read_text().splitlines(), ["started", "finished"])


if __name__ == "__main__":
    unittest.main()
