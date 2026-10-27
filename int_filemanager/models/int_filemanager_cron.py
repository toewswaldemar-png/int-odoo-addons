import threading
import time

from odoo import api, models
from odoo.service.server import SLEEP_INTERVAL
from odoo.tools import config

from odoo.addons.base.models.ir_cron import MIN_TIME_PER_JOB

# What a run may take if Odoo has no limit for it.
NO_LIMIT_SECONDS = 300

# Seconds kept free below the limit of Odoo (the setting ``int_filemanager.time_reserve``).
TIME_RESERVE = 15


class IntFilemanagerCron(models.AbstractModel):
    """The time of the scheduled actions of the filemanager.

    A model that runs such an action (the previews of the office files here, the reading of
    the texts in ``int_filemanager_ocr``) inherits it, or asks the model for it.

    ``ir.cron`` calls a scheduled action again and again until at least ``MIN_RUNS_PER_JOB``
    runs and ``MIN_TIME_PER_JOB`` (10 s) are done, and hands out ``cron_end_time`` (what
    ``_commit_progress`` returns): the end of that window, not the limit after which the server
    kills the run (``limit_time_real_cron``, or ``limit_time_real``). A step here can take
    longer (LibreOffice has up to two minutes for one file), so it is started only if it can
    end before the kill, which ``_pass_deadline`` works out. Check it first when Odoo changes
    ``ir.cron``.
    """

    _name = "int.filemanager.cron"
    _description = "Time of the scheduled actions of the filemanager"

    @api.model
    def _time_reserve(self):
        """Return the seconds that a run keeps free below the time limit of Odoo."""
        # sudo: ir.config_parameter: the settings are read for every user and by the scheduled actions
        params = self.env["ir.config_parameter"].sudo()
        return int(params.get_param("int_filemanager.time_reserve", TIME_RESERVE))

    @api.model
    def _limit_seconds(self):
        """Return how long one run of a scheduled action may take at most, from its start.

        Prefork: ``limit_time_real_cron`` is ``-1`` for ``limit_time_real``, ``0`` for no limit.
        Threaded: ``0`` and ``-1`` both mean ``limit_time_real`` (``server.py``).

        :return: ``(seconds, bounded)``; ``bounded`` is false if Odoo has no limit
        """
        real, cron = config["limit_time_real"], config["limit_time_real_cron"]
        if config["workers"]:
            limit = real if cron == -1 else cron
        else:
            limit = cron if cron and cron > 0 else real
        if not limit or limit < 0:
            return NO_LIMIT_SECONDS, False
        return limit, True

    @api.model
    def _budget(self):
        limit, bounded = self._limit_seconds()
        reserve = self._time_reserve()
        prefork = bool(config["workers"])
        sleep = SLEEP_INTERVAL + 10 if prefork and bounded else 0
        return ("prefork" if prefork else "threaded", limit, max(limit - sleep - reserve, 0), bounded)

    @api.model
    def _pass_deadline(self):
        """Return the time (``time.monotonic``) at which this run of the action must end.

        It is the Odoo limit minus a reserve minus what has been used up. The watchdog of a
        prefork worker counts from its last sign of life, before it sleeps 60 to 69 seconds, so
        that time is taken off too. Every call within one run gets the same deadline: the core
        calls the action at least ten times in a row, and a later call must find the budget used up.
        """
        limit, bounded = self._limit_seconds()
        reserve = self._time_reserve()
        now = time.monotonic()
        end_time = self.env.context.get("cron_end_time")
        job_start = end_time - MIN_TIME_PER_JOB if end_time else now
        if config["workers"]:
            sleep = SLEEP_INTERVAL + 10 if bounded else 0
            return job_start + limit - sleep - reserve
        started = getattr(threading.current_thread(), "start_time", None)
        elapsed = time.time() - started if started else now - job_start
        return now + limit - reserve - elapsed
