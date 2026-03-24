FROM python:3.11-slim

WORKDIR /app

# Install neural-memory v4.20.0 from GitHub with server extras
RUN pip install --no-cache-dir \
    "neural-memory[server] @ git+https://github.com/nhadaututtheky/neural-memory.git@v4.20.0"

# Create directories for brain storage
RUN mkdir -p /data/brains

# Expose the default nmem serve port
EXPOSE 8000

# Default command: start nmem server
CMD ["nmem", "serve", "--host", "0.0.0.0", "--port", "8000", "--brain-dir", "/data/brains"]
