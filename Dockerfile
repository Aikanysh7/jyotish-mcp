FROM python:3.12-slim

WORKDIR /app

# build tools for pyswisseph (C extension)
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY jyotish_core.py geo.py server.py ./

ENV MCP_TRANSPORT=http
ENV PORT=8000
EXPOSE 8000

CMD ["python", "server.py"]
