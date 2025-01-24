FROM python:3.13-slim

WORKDIR /app

COPY ./requirements.txt /app/requirements.txt

RUN pip install --upgrade --no-cache-dir -r /app/requirements.txt

COPY ./src /app/src

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]



