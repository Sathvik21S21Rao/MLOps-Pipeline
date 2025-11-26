FROM python:3.11-slim
ENV MODEL_OUTPUT_DIR=/app/model_output
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY model_inference.py .
EXPOSE 8000
CMD ["uvicorn", "model_inference:app", "--host", "0.0.0.0", "--port", "8000"]