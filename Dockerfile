FROM python:3.11-slim

WORKDIR /app

# Install git (needed to pip install from GitHub)
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# Install neural-memory v4.20.0 from GitHub with server extras
RUN pip install --no-cache-dir \
    "neural-memory[server] @ git+https://github.com/nhadaututtheky/neural-memory.git@v4.20.0"

# Create brain storage directory
RUN mkdir -p /data/brains

# Set neural memory home to use mounted storage
ENV NMEM_HOME=/data
ENV NEURAL_MEMORY_BRAIN_DIR=/data/brains

# Expose the default nmem serve port
EXPOSE 8000

# Default command: start nmem server
CMD ["nmem", "serve", "--host", "0.0.0.0", "--port", "8000"]
