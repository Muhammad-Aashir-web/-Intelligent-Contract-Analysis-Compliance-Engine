FROM python:3.11.9-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1

RUN apt-get update \
	&& apt-get install -y --no-install-recommends \
		gcc \
		libpq-dev \
		tesseract-ocr \
		libgl1-mesa-glx \
		libglib2.0-0 \
	&& rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
