.PHONY: test
test:
	poetry run python -m pytest tests -s --log-cli-level INFO

.PHONY: dist
dist:
	rm -rf ./dist
	poetry build
	poetry publish