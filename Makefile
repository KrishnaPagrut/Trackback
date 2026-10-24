# Thin wrapper: every target runs tasks.py, which works on macOS and Windows.
PYTHON ?= $(shell command -v python3 || command -v python)

.PHONY: setup world test eval check web demo reset serve

setup world test eval check web demo reset serve:
	$(PYTHON) tasks.py $@
