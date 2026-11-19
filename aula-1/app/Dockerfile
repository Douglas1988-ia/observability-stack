FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV OTEL_SEMCONV_STABILITY_OPT_IN=http
EXPOSE 8000 9464
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
