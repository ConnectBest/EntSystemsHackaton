FROM python:3.11-slim

WORKDIR /app

# Install system dependencies first (cached layer)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (cached if requirements.txt unchanged)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Clean up build dependencies (separate layer for flexibility)
RUN apt-get purge -y gcc g++ \
    && apt-get autoremove -y \
    && apt-get clean

# Copy application code (changes frequently, stays at end)
COPY . .

EXPOSE 8001

CMD ["uvicorn", "rag_server:app", "--host", "0.0.0.0", "--port", "8001"]
