from . import models, controllers, dav, dav_inproc


def _fm_dav_post_load():
    """post_load (nur als server-weites Modul): eingebettetes fmdav, Konzept 19.12."""
    from . import dav_embed
    dav_embed.start()
