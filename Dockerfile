ARG BASE_IMAGE=python:3.13-slim
FROM ${BASE_IMAGE}
WORKDIR /app
COPY . .
ENV HOST=0.0.0.0 PORT=8080 PYTHONDONTWRITEBYTECODE=1
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD ["python3", "-c", "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:'+os.environ['PORT']+'/healthz',timeout=2)"]
CMD ["python3", "server.py"]
