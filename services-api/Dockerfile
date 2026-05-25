FROM python:3.11-slim

WORKDIR /app

# Install fonts for PDF Korean support
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-nanum \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/generated_files

EXPOSE 8001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
