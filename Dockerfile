FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY cards.json .
COPY bot.py .

CMD ["python", "-u", "bot.py"]
