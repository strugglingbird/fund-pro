ARG PYTHON_IMAGE=python:3.11-slim
FROM ${PYTHON_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/ \
    HOST=0.0.0.0 \
    PORT=5000 \
    DATABASE_ENGINE=mysql

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend ./backend

EXPOSE 5000
WORKDIR /app/backend
CMD ["python", "-u", "run.py"]
