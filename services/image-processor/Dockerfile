FROM python:3.11-slim

WORKDIR /app

# Install dependencies and compile packages in one layer to reduce memory usage
COPY requirements.txt .
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y gcc g++ \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

COPY . .

CMD ["python", "processor.py"]
