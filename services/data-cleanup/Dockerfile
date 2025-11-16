FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy cleanup script
COPY cleanup.py .

# Make script executable
RUN chmod +x cleanup.py

CMD ["python", "-u", "cleanup.py"]
