# Converter service (tools/fmconverter). Build: docker build -t fmconverter tools/fmconverter
# Run with the blob store mounted READ-ONLY and no route to the internet, e.g.
#   docker run -d --name fmconverter --network <internal net> -v <blobroot>:/blobs:ro fmconverter
#
# The tools are the only code that opens foreign file bytes (LibreOffice, ffmpeg,
# Ghostscript, Pillow with its plugins, libraw, ExifTool, Tesseract): they live here,
# never in the Odoo image.
FROM python:3.12-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ffmpeg ghostscript poppler-utils qpdf \
      tesseract-ocr tesseract-ocr-deu tesseract-ocr-eng \
      libreoffice-writer libreoffice-calc libreoffice-impress \
      fonts-dejavu fonts-liberation libimage-exiftool-perl \
 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir pillow==12.3.0 pillow-heif rawpy mutagen ocrmypdf pdfplumber \
 && useradd --create-home --uid 10001 converter
COPY server.py worker.py /app/
USER converter
WORKDIR /app
EXPOSE 8090
CMD ["python", "server.py"]
