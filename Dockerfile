FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/

# Copy config files
COPY .env.example .env
COPY docker-compose.yml .
COPY Dockerfile .

# Create volume for persistent data
VOLUME /app/data

# Run the bot
CMD ["python", "-m", "src.bot"]
