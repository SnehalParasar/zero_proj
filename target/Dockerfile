FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install flask

COPY app.py .

EXPOSE 5001

CMD ["python", "app.py"]
