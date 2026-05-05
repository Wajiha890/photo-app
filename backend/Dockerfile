FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements first (better caching)
COPY requirements.txt .

# Normalize requirements encoding to UTF-8 (handles UTF-16 + UTF-8 BOM)
RUN python -c "from pathlib import Path; p=Path('requirements.txt'); b=p.read_bytes(); t=b.decode('utf-16') if b'\\x00' in b else b.decode('utf-8-sig'); p.write_text('\\n'.join([ln.strip() for ln in t.splitlines() if ln.strip()]) + '\\n', encoding='utf-8', newline='\\n')"

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Azure App Service sets PORT (often 8080). Default matches typical Linux container apps.
ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 2 --threads 4 --timeout 120 app:app"]