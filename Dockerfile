FROM python:3.9

RUN apt-get update && apt-get install -y \
    ffmpeg \
    libgl1 \
 && rm -rf /var/lib/apt/lists/*

ENV POETRY_VIRTUALENVS_IN_PROJECT=false

RUN pip install -U poetry

ADD pyproject.toml /srv/pyproject.toml
ADD poetry.lock /srv/poetry.lock

WORKDIR /srv

RUN poetry install
