FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY hello_api.py .

EXPOSE 8000

CMD ["python", "hello_api.py"]
