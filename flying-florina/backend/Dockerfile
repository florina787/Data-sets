FROM python:3.13-slim
WORKDIR /srv
# Optional: in-process llama.cpp runtime for your EXISTING Qwen .gguf (mounted read-only at /models). No model is downloaded.
ARG INSTALL_LLAMA=false
COPY backend/requirements.txt backend/requirements.txt
COPY backend/requirements-llm.txt backend/requirements-llm.txt
RUN pip install --no-cache-dir -r backend/requirements.txt \
 && if [ "$INSTALL_LLAMA" = "true" ]; then pip install --no-cache-dir -r backend/requirements-llm.txt \
      --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu; fi
COPY backend backend
COPY fixtures fixtures
COPY mcp_servers mcp_servers
COPY generated_adapters/example_part_availability generated_adapters/example_part_availability
ENV DEMO_MODE=true OFFLINE_MODE=true FF_DATA_DIR=/srv/data PYTHONUNBUFFERED=1
WORKDIR /srv/backend
EXPOSE 8000
USER 65534
HEALTHCHECK --interval=20s --timeout=3s --start-period=20s CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"
# --timeout-graceful-shutdown lets in-flight requests finish on SIGTERM (Kubernetes terminationGracePeriodSeconds covers it)
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-graceful-shutdown", "20"]
