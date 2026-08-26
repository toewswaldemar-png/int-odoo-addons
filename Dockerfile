FROM odoo:latest

# hm_filemanager's watcher.py needs inotify_simple - not bundled in the base
# image, unlike watchdog. Installed here so it survives container recreation.
RUN pip install --break-system-packages --no-cache-dir inotify_simple
