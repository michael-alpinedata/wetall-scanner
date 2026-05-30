.PHONY: docker-build docker-run serve

docker-build:
	docker build -t wetall-links-checker .

docker-run:
	docker run -p 8000:8000 --env-file .env wetall-links-checker

serve:
	uv run python src/main.py
