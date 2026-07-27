.PHONY: install test lint check deploy clean

install:
	pip install -r functions/requirements.txt
	pip install pytest flake8

test:
	pytest tests/

lint:
	flake8 functions/ tests/

check:
	python scripts/pre_deploy_check.py

deploy: check
	firebase deploy --only functions,hosting

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
