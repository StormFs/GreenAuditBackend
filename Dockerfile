# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Set work directory
WORKDIR /app

# Install system dependencies (needed for some python packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# We use --no-cache-dir to keep image small
COPY requirements.txt .
# Attempt to install CPU-only torch to save space/memory if possible, 
# but for simplicity we rely on standard pip which might pull cuda versions.
# To force CPU: pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt
    pip install -u ddgs

# Copy project
COPY . .

# Expose port
EXPOSE 8000

# Command to run the application
CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT
