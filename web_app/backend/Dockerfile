FROM python:3.12-slim

WORKDIR /app

# (Removed apt-get since psycopg2-binary has pre-compiled wheels)

COPY web_app/backend/requirements.txt /app/web_app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/web_app/backend/requirements.txt

COPY . /app

# Install all the agent's dependencies from the root pyproject.toml (langgraph, openai, etc.)
RUN pip install --no-cache-dir .

WORKDIR /app/web_app/backend

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
