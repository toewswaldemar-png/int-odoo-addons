# Odoo-19-Image mit den Bibliotheken für int_filemanager: mutagen (Audio-Metadaten), tesseract/OCRmyPDF
# (Volltextsuche/OCR), pdfplumber, pyjwt (ONLYOFFICE). Basis war das auf HM-SRV (Unraid) deployte Image
# (/mnt/user/appdata/odoo/Dockerfile); der Start-Wrapper für die SMB-Freigaben ist entfernt. Das offizielle
# odoo:19.0-Image läuft als USER odoo - ein pip install direkt nach FROM ohne USER-root-Wechsel
# scheitert mangels Schreibrechten auf die System-Packages (empirisch bestätigt).
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
USER odoo
