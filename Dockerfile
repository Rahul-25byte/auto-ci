FROM python:3.11-slim

LABEL maintainer="Auto-CI Team <team@auto-ci.dev>"
LABEL description="Auto-CI: Automated CI/CD Pipeline Generator"

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN groupadd -r autoci && useradd -r -g autoci autoci

WORKDIR /app

COPY requirements.txt .
COPY requirements-dev.txt .

RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN pip install -e .

RUN chown -R autoci:autoci /app

USER autoci

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from auto_ci import AutoCI; AutoCI()" || exit 1

CMD ["auto-ci", "--help"]
