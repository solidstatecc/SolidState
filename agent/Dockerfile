FROM python:3.12-slim

# docker CLI for the fallback runtime; remove if you only ship NemoClaw.
RUN apt-get update && apt-get install -y --no-install-recommends \
    docker.io \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy code into /app/agent so the module path `agent.api.main` resolves.
COPY . /app/agent/

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "agent.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
