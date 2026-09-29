FROM python:3.12-slim

# Node (docx-js builds), LibreOffice (render and recalc checks), poppler (pdftotext), fonts close to Cambria/Calibri
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates gnupg unzip git \
        libreoffice-writer-nogui libreoffice-calc-nogui poppler-utils \
        fonts-dejavu fonts-liberation fonts-crosextra-caladea fonts-crosextra-carlito \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g docx@9 @anthropic-ai/claude-code \
    && rm -rf /var/lib/apt/lists/*

ENV NODE_PATH=/usr/lib/node_modules \
    IS_SANDBOX=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/data

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY workspace ./workspace
COPY skill-bundle ./skill-bundle

EXPOSE 8080
CMD ["python", "-m", "app.main"]
