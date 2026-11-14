FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV GINO_HOST=0.0.0.0 GINO_DATA_DIR=/data
VOLUME /data
EXPOSE 8787
CMD ["python", "run.py"]
