.PHONY: dev-up dev-down dev-reset dev-test dev-browser-smoke dev-status \
	staging-build staging-up staging-down staging-status staging-test

dev-up:
	python scripts/dev_workbench.py dev-up

dev-down:
	python scripts/dev_workbench.py dev-down

dev-reset:
	python scripts/dev_workbench.py dev-reset

dev-test:
	python scripts/dev_workbench.py dev-test

dev-browser-smoke:
	python scripts/dev_workbench.py dev-browser-smoke

dev-status:
	python scripts/dev_workbench.py dev-status

staging-build:
	python scripts/staging_workbench.py staging-build

staging-up:
	python scripts/staging_workbench.py staging-up

staging-down:
	python scripts/staging_workbench.py staging-down

staging-status:
	python scripts/staging_workbench.py staging-status

staging-test:
	python scripts/staging_workbench.py staging-test
