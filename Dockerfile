FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PROOFPAGE_HOSTED_HOME=/data
WORKDIR /app
COPY pyproject.toml README.md LICENSE requirements-hosted.lock ./
COPY proofpage ./proofpage
RUN pip install --no-cache-dir -r requirements-hosted.lock && pip install --no-cache-dir --no-deps . && useradd --uid 10001 --create-home proofpage && mkdir /data && chown proofpage:proofpage /data
USER proofpage
VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import os,urllib.request,urllib.parse; u=urllib.parse.urlsplit(os.environ['PROOFPAGE_PUBLIC_URL']); urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8000/healthz',headers={'Host':u.netloc}),timeout=4)"
CMD ["python", "-m", "proofpage", "hosted", "--bind", "0.0.0.0", "--port", "8000"]
