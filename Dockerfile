FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    GACASE_TRANSPORT=streamable-http \
    GACASE_HOST=0.0.0.0 \
    GACASE_PORT=8000

WORKDIR /app
COPY requirements.txt pyproject.toml ./
RUN pip install -r requirements.txt
COPY gacaseMCP ./gacaseMCP
COPY main.py ./
RUN pip install --no-deps .

RUN useradd --system --no-create-home gacase
USER gacase

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os,urllib.request as u; u.urlopen('http://127.0.0.1:%s/health' % os.environ.get('GACASE_PORT','8000'), timeout=4)"

CMD ["gacasemcp"]
