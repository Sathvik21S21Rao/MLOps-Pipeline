# Use Python 3.9 Slim (matches your requirements)
FROM python:3.9-slim

# Set working directory to the ROOT of the app inside the container
WORKDIR /app

# 1. Install Build Dependencies
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# 2. Install Python Dependencies
# We copy requirements first to leverage Docker caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Copy YOUR ENTIRE PROJECT into the container
# This copies 'DataLoading' folder AND 'ModelLoading' folder into /app/
COPY . .

# (Optional) verify structure during build
RUN ls -R /app