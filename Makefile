.PHONY: dev test lint migrate eval pipeline-cli

dev:
	@echo "make dev: apps/api e apps/web ainda não existem (Fase 4)."

test:
	pytest
	@if [ -f apps/web/package.json ]; then cd apps/web && npm test; fi

lint:
	ruff check .
	@if [ -f apps/web/package.json ]; then cd apps/web && npm run lint && npx tsc --noEmit; fi

migrate:
	@echo "make migrate: sem migrations ainda."

eval:
	@echo "make eval: harness de avaliação ainda não existe."

pipeline-cli:
	@echo "make pipeline-cli: scripts/dub.py ainda não existe."
