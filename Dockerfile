FROM odoo:latest

# hm_filemanager's watcher.py needs inotify_simple - not bundled in the base
# image, unlike watchdog. Must land in the system dist-packages, not the
# default user-site under /var/lib/odoo/.local - that path is one of the
# container's own runtime bind mounts (odoo18/data) and would be shadowed
# and disappear the moment the real container (with its mounts) starts.
USER root
RUN pip install --break-system-packages --no-cache-dir --target=/usr/lib/python3/dist-packages inotify_simple
USER odoo
