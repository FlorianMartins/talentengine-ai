# Disposable test runner: no secrets, no data, no network (see docker-compose.yml, service "runner").
FROM python:3.12.7-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r /srv/requirements.txt \
 && useradd --uid 10002 --no-create-home --shell /usr/sbin/nologin runner
COPY server.py /srv/server.py
USER 10002
EXPOSE 8090
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/health')"
CMD ["python", "/srv/server.py"]
