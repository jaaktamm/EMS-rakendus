FROM python:3.11.9-slim@sha256:8fb099199b9f2d70342674bd9dbccd3ed03a258f26bbd1d556822c6dfc60c317

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    NLTK_DATA=/usr/local/share/nltk_data \
    EMS_DATA_DIR=/data \
    EMS_MAX_INPUT_BYTES=5242880
WORKDIR /app
COPY requirements*.txt stage1-requirements-linux.lock.txt ./
RUN pip install --no-cache-dir -r requirements-web.txt -c stage1-requirements-linux.lock.txt \
    && pip check \
    && python -m nltk.downloader -d /usr/local/share/nltk_data punkt_tab
COPY ems ./ems
RUN python -c "from ems.linguistics import signature, analyzer; signature(); analyzer().analyze('See on proov.')" \
    && groupadd --gid 10001 ems \
    && useradd --uid 10001 --gid 10001 --create-home ems \
    && mkdir /data && chown ems:ems /data
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --start-period=15m --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=3).read()"
CMD ["python", "-m", "uvicorn", "ems.web:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log"]

