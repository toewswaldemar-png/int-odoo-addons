# Converter service (tools/fmconverter). Build: docker build -t fmconverter .
# Run with the blob store mounted READ-ONLY and no route to the internet, e.g.
#   docker run -d --name fmconverter --network <internal net> -v <blobroot>:/blobs:ro fmconverter
FROM python:3.12-slim
RUN pip install --no-cache-dir pillow==12.3.0 \
 && useradd --no-create-home --uid 10001 converter
COPY server.py worker.py /app/
USER converter
WORKDIR /app
EXPOSE 8090
CMD ["python", "server.py"]
