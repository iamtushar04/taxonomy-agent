FROM python:3.12-slim

WORKDIR /app

# (Removed apt-get since psycopg2-binary has pre-compiled wheels)

COPY web_app/backend/requirements.txt /app/web_app/backend/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip pip install -r /app/web_app/backend/requirements.txt

COPY . /app

# Force the lightweight CPU-only version of PyTorch to save 2.5GB and massive download times
RUN --mount=type=cache,target=/root/.cache/pip pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# Install all the agent's dependencies from the root pyproject.toml (langgraph, openai, etc.)
RUN --mount=type=cache,target=/root/.cache/pip pip install .

WORKDIR /app/web_app/backend

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
