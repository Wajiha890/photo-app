FROM python:3.11-slim

WORKDIR /app

COPY . .

EXPOSE 5500

CMD ["sh", "-c", "echo '🌐 Frontend running at: http://localhost:5500' && python -m http.server 5500"]