.PHONY: test
test:
	poetry run python -m pytest tests -s --log-cli-level INFO

dist:
	rm -rf ./dist
	poetry build
	poetry publish