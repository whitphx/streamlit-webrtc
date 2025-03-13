FROM python:3.9

RUN apt-get update && apt-get install -y \
    ffmpeg \
    libgl1 \
 && rm -rf /var/lib/apt/lists/*

RUN pip install -U uv

ADD pyproject.toml /srv/pyproject.toml
ADD requirements.txt /srv/requirements.txt

WORKDIR /srv

RUN uv pip install -r requirements.txt
