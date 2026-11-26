SHELL := /bin/bash
PY := .venv/bin/python
PIP := .venv/bin/pip
BACKEND_MODULES := reasoning-orchestrator memory-graph persona-state async-consolidator
FRONTEND_MODULES := conversation-web admin-web

.PHONY: help bootstrap install validate lint test test-module build contracts contracts-check catalog check run-% web-install web-build web-test web-smoke demo

help:
	@echo "HLA-MEM development targets"
	@echo "  make install          create .venv and install shared packages + backend modules (editable)"
	@echo "  make validate         validate all module manifests, contracts and naming"
	@echo "  make lint             ruff static checks"
	@echo "  make test             run all Python tests"
	@echo "  make test-module M=x  run one module's tests, e.g. M=memory-graph"
	@echo "  make build            byte-compile and wheel-build every backend module"
	@echo "  make contracts        regenerate contracts/openapi.yaml from FastAPI apps"
	@echo "  make contracts-check  fail if committed OpenAPI drifts from implementation"
	@echo "  make catalog          regenerate docs/module-catalog.md from module.yaml files"
	@echo "  make check            validate + contracts-check + test"
	@echo "  make run-MODULE       run one backend module, e.g. make run-memory-graph"
	@echo "  make web-install      npm install for both frontends"
	@echo "  make web-build        production build for both frontends"
	@echo "  make web-test         vitest for both frontends"
	@echo "  make demo             launch the minimal demo (requires make web-build)"

.venv/bin/python:
	python3 -m venv .venv
	$(PIP) install -U pip setuptools wheel
	$(PIP) install "fastapi>=0.115" "uvicorn[standard]>=0.30" "pydantic>=2.8" \
		"pytest>=8" "httpx>=0.27" "pyyaml>=6" "jsonschema>=4.22" "ruff>=0.6"

bootstrap: .venv/bin/python

install: .venv/bin/python
	$(PIP) install -e packages/contract-kit -e packages/host
	for m in $(BACKEND_MODULES); do $(PIP) install -e modules/$$m || exit 1; done

validate: .venv/bin/python
	$(PY) -m hla_contract_kit check-all .

lint: .venv/bin/python
	$(PY) -m ruff check packages modules tools

test: .venv/bin/python
	$(PY) -m pytest -q

test-module: .venv/bin/python
	@test -n "$(M)" || (echo "usage: make test-module M=<module-id>" && exit 2)
	$(PY) -m pytest -q modules/$(M)/tests

build: .venv/bin/python
	for m in $(BACKEND_MODULES); do \
		$(PY) -m compileall -q modules/$$m/src || exit 1; \
		$(PIP) wheel --no-deps --no-build-isolation -w modules/$$m/dist modules/$$m || exit 1; \
	done

contracts: .venv/bin/python
	$(PY) tools/export_openapi.py --all

contracts-check: .venv/bin/python
	$(PY) tools/export_openapi.py --all --check

catalog: .venv/bin/python
	$(PY) tools/render_catalog.py

check: validate contracts-check test lint

run-%: .venv/bin/python
	$(PY) tools/run_module.py $*

web-install:
	for m in $(FRONTEND_MODULES); do (cd modules/$$m/web && npm install --no-audit --no-fund --cache $(CURDIR)/.npm-cache) || exit 1; done

web-build:
	for m in $(FRONTEND_MODULES); do (cd modules/$$m/web && npm run build) || exit 1; done

web-test:
	for m in $(FRONTEND_MODULES); do (cd modules/$$m/web && npm test) || exit 1; done

web-smoke: web-build
	@echo "Frontend builds completed; start with: make demo"

demo: .venv/bin/python
	$(PY) tools/run_demo.py
