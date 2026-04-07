FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git texlive-latex-base texlive-fonts-recommended \
    texlive-fonts-extra texlive-latex-extra texlive-science \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/uploads /app/experiments && chown -R user:user /app

USER user
EXPOSE 7860

CMD ["python", "app.py"]
