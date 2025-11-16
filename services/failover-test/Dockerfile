FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy failover test script
COPY failover_test.py .

# Make script executable
RUN chmod +x failover_test.py

# Expose port for API
EXPOSE 8002

CMD ["python", "-u", "failover_test.py"]
