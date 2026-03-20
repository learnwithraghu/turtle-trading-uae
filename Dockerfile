# UAE Turtle Trader
# Multi-stage: builder installs deps + Playwright; runner is lean.

FROM python:3.11-slim AS builder

WORKDIR /app

# System deps needed by Playwright / Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
        wget curl gnupg ca-certificates \
        libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
        libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
        libxfixes3 libxrandr2 libgbm1 libasound2 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium browser
RUN playwright install chromium \
    && playwright install-deps chromium

# ── Runner stage ──────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runner

WORKDIR /app

# Copy Chromium and its system libs from builder
COPY --from=builder /root/.cache/ms-playwright /root/.cache/ms-playwright
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Re-install only the runtime system libraries (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
        libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
        libxfixes3 libxrandr2 libgbm1 libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Copy project source
COPY . .

# Create persistent volume mount points
RUN mkdir -p data/history output

# Playwright must run headless inside Docker (no display)
ENV PLAYWRIGHT_HEADLESS=1

# Default: run the scanner
CMD ["python", "scan.py", "--no-browser"]
