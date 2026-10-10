.PHONY: install dev build deploy

install:
	pip install -r requirements.txt

dev:
	.venv\Scripts\python -m main

dev-inapp:
	.venv\Scripts\python -m main inapp

dev-external:
	.venv\Scripts\python -m main external

build:
	docker compose -f docker/docker-compose.yml build

deploy:
	docker compose -f docker/docker-compose.yml up -d
