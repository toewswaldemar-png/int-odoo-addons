# Spiegelt das auf HM-SRV (Unraid) tatsächlich deployte Image
# (/mnt/user/appdata/odoo/Dockerfile), ergänzt um mutagen für Phase 4
# (Audio-Metadaten) sowie tesseract/poppler für Baustein 1 (Volltextsuche/OCR, siehe
# docs/int_filemanager_paperoffice_recherche.md). Das offizielle odoo:19.0-Image läuft als
# USER odoo - ein pip install direkt nach FROM ohne USER-root-Wechsel scheitert mangels
# Schreibrechten auf die System-Packages (empirisch bestätigt, siehe
# docs/int_filemanager_ausbau.md).
FROM odoo:19.0
USER root
# tesseract-ocr/poppler-utils sind System-Binaries (apt, nicht pip) - pytesseract/pdf2image sind
# nur duenne Python-Wrapper darum, kein separater Dienst/Container noetig, alles laeuft
# in-process in derselben Odoo-Instanz wie mutagen/Pillow/PyPDF2 auch.
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-deu poppler-utils \
    && rm -rf /var/lib/apt/lists/*
RUN pip3 install --break-system-packages --no-cache-dir pyjwt mutagen==1.47.0 pytesseract pdf2image
# Wartet beim Start, bis die drei SMB-Freigaben unter /mnt/hm-daten wirklich als CIFS
# gemountet sind (nicht Unraids leerer tmpfs-Platzhalter) - siehe Kommentar im Skript.
# Muss noch als root kopiert/ausfuehrbar gemacht werden, laeuft danach aber als USER odoo.
COPY scripts/wait_for_smb_mounts.sh /usr/local/bin/wait_for_smb_mounts.sh
RUN chmod +x /usr/local/bin/wait_for_smb_mounts.sh
USER odoo
ENTRYPOINT ["/usr/local/bin/wait_for_smb_mounts.sh"]
# Docker setzt ein von der Basis geerbtes CMD zurueck, sobald ein Dockerfile einen eigenen
# ENTRYPOINT definiert (dokumentiertes Verhalten, hier live bestaetigt: ohne diese Zeile war
# Cmd=[] statt dem geerbten ["odoo"]) - explizit wiederherstellen, da Unraids Docker-Template
# fuer diesen Container kein eigenes PostArgs setzt und sich auf das Image-CMD verlaesst.
CMD ["odoo"]
