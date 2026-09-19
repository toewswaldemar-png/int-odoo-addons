# Spiegelt das auf HM-SRV (Unraid) tatsächlich deployte Image
# (/mnt/user/appdata/odoo/Dockerfile), ergänzt um mutagen für Phase 4
# (Audio-Metadaten) sowie tesseract/OCRmyPDF für Baustein 1 (Volltextsuche/OCR, siehe
# docs/int_filemanager_paperoffice_recherche.md, docs/int_filemanager_ocr_selbstdefinierte_felder.md
# Phase B). Das offizielle odoo:19.0-Image läuft als USER odoo - ein pip install direkt nach FROM
# ohne USER-root-Wechsel scheitert mangels Schreibrechten auf die System-Packages (empirisch
# bestätigt, siehe docs/int_filemanager_ausbau.md).
FROM odoo:19.0
USER root
# tesseract-ocr (+ deutsches Sprachpaket) bleibt bestehen, laeuft aber seit Phase B nicht mehr
# direkt ueber pytesseract, sondern intern durch OCRmyPDF (pip-Paket "ocrmypdf") - das braucht
# zusaetzlich ghostscript+qpdf als System-Binaries (offizielle OCRmyPDF-Voraussetzungen).
# poppler-utils raus: war nur fuer pdf2image (Rendern von PDF-Seiten zu Bildern vor dem rohen
# pytesseract-Aufruf) noetig, das mit dem Wechsel auf OCRmyPDF komplett entfaellt.
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-deu ghostscript qpdf \
    && rm -rf /var/lib/apt/lists/*
# pdfplumber ersetzt PyPDF2/odoo.tools.pdf.PdfReader als PDF-Textextraktion (liefert zusaetzlich
# Wort-Positionen fuer das Highlighting, siehe fulltext.py); ocrmypdf ersetzt den rohen
# pytesseract/pdf2image-Aufruf. --ignore-installed: ocrmypdf zieht ueber pydantic eine neuere
# typing_extensions als die vom Debian-Basisimage per apt vorinstallierte - pip kann diese apt-
# verwaltete Version nicht sauber deinstallieren (fehlende RECORD-Metadaten, live am Image
# bestaetigt: "Cannot uninstall typing_extensions ... installed by debian"). --ignore-installed
# ueberschreibt sie einfach mit einer eigenen pip-Kopie statt sie zu deinstallieren.
# pyopenssl explizit mitgezogen: ocrmypdf/pikepdf ziehen ueber ihre eigenen Abhaengigkeiten ein
# neueres "cryptography" (50.x) als das per apt vorinstallierte pyOpenSSL (23.2.0) unterstuetzt -
# live bestaetigt: Odoos "web"-Modul (importiert OpenSSL fuer ir_mail_server) scheiterte danach
# mit "AttributeError: module 'lib' has no attribute 'GEN_EMAIL'", die komplette Oberflaeche war
# nicht mehr erreichbar. pyopenssl>=24 ist mit cryptography 50.x kompatibel.
RUN pip3 install --break-system-packages --ignore-installed --no-cache-dir pyjwt mutagen==1.47.0 "pyopenssl>=24" pdfplumber ocrmypdf
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
