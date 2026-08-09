FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY jyotish_core.py geo.py server.py ./

ENV MCP_TRANSPORT=http
# PaaS platforms inject $PORT; default for local docker run
ENV PORT=8000
EXPOSE 8000

CMD ["python", "server.py"]
