FROM python:3.13-slim
WORKDIR /srv
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend backend
COPY fixtures fixtures
COPY mcp_servers mcp_servers
COPY generated_adapters/example_part_availability generated_adapters/example_part_availability
ENV DEMO_MODE=true OFFLINE_MODE=true FF_DATA_DIR=/srv/data
WORKDIR /srv/backend
EXPOSE 8000
USER 65534
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
