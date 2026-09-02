# Spiegelt das auf HM-SRV (Unraid) tatsächlich deployte Image
# (/mnt/user/appdata/odoo/Dockerfile), ergänzt um mutagen für Phase 4
# (Audio-Metadaten). Das offizielle odoo:19.0-Image läuft als USER odoo -
# ein pip install direkt nach FROM ohne USER-root-Wechsel scheitert mangels
# Schreibrechten auf die System-Packages (empirisch bestätigt, siehe
# docs/int_filemanager_ausbau.md).
FROM odoo:19.0
USER root
RUN pip3 install --break-system-packages --no-cache-dir pyjwt mutagen==1.47.0
USER odoo
