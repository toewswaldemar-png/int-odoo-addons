FROM python:3.12-slim
RUN pip install --no-cache-dir wsgidav==4.3.5 cheroot==11.1.2 requests==2.32.5
COPY dav_service.py /app/dav_service.py
USER 65534
CMD ["python3", "-u", "/app/dav_service.py"]
