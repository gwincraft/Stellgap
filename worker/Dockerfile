FROM python:3.9-slim

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY ./worker/app /app/app

# Run the worker process
CMD ["python", "-m", "app.main"]
