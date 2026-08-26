from . import controllers
from . import models
from . import watcher


def post_load():
    watcher.start_watcher()
