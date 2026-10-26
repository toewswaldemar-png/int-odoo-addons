import threading
import time

from odoo import api, models
from odoo.service.server import SLEEP_INTERVAL
from odoo.tools import config

from odoo.addons.base.models.ir_cron import MIN_TIME_PER_JOB

# What a run may take if Odoo has no limit for it.
NO_LIMIT_SECONDS = 300

SETTINGS = {
    # name: (default, least)
    "time_reserve": (15, 0),  # seconds kept free below the limit of Odoo
    "preview_seconds": (120, 5),  # time LibreOffice has for one office file
    "preview_max_size_mib": (500, 1),  # the biggest office file that gets a preview
}


class IntFilemanagerCron(models.AbstractModel):
    """The settings and the time of the scheduled actions of the filemanager.

    A model that runs such an action (the previews of the office files here, the reading of the
    texts in ``int_filemanager_ocr``) inherits it, or asks the model for them.
    """

    _name = "int.filemanager.cron"
    _description = "Settings and time of the scheduled actions of the filemanager"

    @api.model
    def _setting_defaults(self):
        """The numbers of the settings: ``{name: (default, least)}``. A module adds its own."""
        return SETTINGS

    @api.model
    def _setting(self, name):
        """A number from the system parameters, ``int_filemanager.<name>`` (else its default)."""
        default, least = self._setting_defaults()[name]
        value = self.env["ir.config_parameter"].sudo().get_param(f"int_filemanager.{name}")
        try:
            return max(int(value), least) if value else default
        except ValueError:
            return default

    @api.model
    def _flag(self, name, default):
        """A yes or no from the system parameters, ``int_filemanager.<name>`` (else ``default``)."""
        value = self.env["ir.config_parameter"].sudo().get_param(f"int_filemanager.{name}")
        if not value:
            return default
        return value.strip().lower() not in ("0", "false", "no", "off")

    @api.model
    def _limit_seconds(self):
        """How long one run of a scheduled action may take at most, from its start.

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
        """How long one run lasts: ``(mode, limit, seconds, bounded)``; see ``_pass_deadline``."""
        limit, bounded = self._limit_seconds()
        reserve = self._setting("time_reserve")
        prefork = bool(config["workers"])
        sleep = SLEEP_INTERVAL + 10 if prefork and bounded else 0
        return ("prefork" if prefork else "threaded", limit, max(limit - sleep - reserve, 0), bounded)

    @api.model
    def _pass_deadline(self):
        """The time (``time.monotonic``) at which this run of the action must end.

        The Odoo limit minus a reserve minus what has been used up. The watchdog of a prefork
        worker counts from its last sign of life, before it sleeps 60 to 69 seconds, so that
        time is taken off too. Every call within one run gets the same deadline: the core calls
        the method up to ten times in a row, and a later call must find the budget used up.
        """
        limit, bounded = self._limit_seconds()
        reserve = self._setting("time_reserve")
        now = time.monotonic()
        end_time = self.env.context.get("cron_end_time")
        job_start = end_time - MIN_TIME_PER_JOB if end_time else now
        if config["workers"]:
            sleep = SLEEP_INTERVAL + 10 if bounded else 0
            return job_start + limit - sleep - reserve
        started = getattr(threading.current_thread(), "start_time", None)
        elapsed = time.time() - started if started else now - job_start
        return now + limit - reserve - elapsed
