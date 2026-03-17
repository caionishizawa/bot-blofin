.PHONY: help install test test-phase1 test-phase2 test-phase3 test-phase5 run lint clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
	awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies
	pip install -r requirements.txt --break-system-packages

test:  ## Run all tests
	python tests/test_phase1_api.py
	python tests/test_phase2_scanner.py
	python tests/test_phase3_charts.py
	python tests/test_phase5_tracker_db.py

test-phase1:  ## Test BloFin API
	python tests/test_phase1_api.py

test-phase2:  ## Test Scanner + Indicators
	python tests/test_phase2_scanner.py

test-phase3:  ## Test Chart Generator
	python tests/test_phase3_charts.py

test-phase5:  ## Test Tracker + Performance DB
	python tests/test_phase5_tracker_db.py

run:  ## Run the bot
	cd src && python bot.py

lint:  ## Check code style
	python -m py_compile src/bot.py
	python -m py_compile src/modules/scanner.py
	python -m py_compile src/modules/chart_generator.py
	python -m py_compile src/modules/llm_analyst.py
	python -m py_compile src/modules/tracker.py
	python -m py_compile src/modules/performance.py
	python -m py_compile src/utils/blofin_api.py
	python -m py_compile src/utils/indicators.py
	python -m py_compile src/utils/formatters.py
	@echo "✅ All files compile OK"

clean:  ## Clean generated files
	rm -rf tests/output/
	rm -rf data/*.db
	rm -rf logs/
	rm -rf __pycache__
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true

# ─── Git helpers ──────────────────────────────────────────

git-phase1:  ## Commit Phase 1
	git add .
	git commit -m "feat(foundation): BloFin API wrapper + project structure"
	git tag -a v0.1.0 -m "Phase 1: Foundation"

git-phase2:  ## Commit Phase 2
	git add .
	git commit -m "feat(scanner): indicators + signal detection"
	git tag -a v0.2.0 -m "Phase 2: Scanner + Indicators"

git-phase3:  ## Commit Phase 3
	git add .
	git commit -m "feat(charts): TradingView-style chart generator"
	git tag -a v0.3.0 -m "Phase 3: Chart Generator"

git-phase4:  ## Commit Phase 4
	git add .
	git commit -m "feat(llm): Claude analysis integration"
	git tag -a v0.4.0 -m "Phase 4: LLM Analyst"

git-phase5:  ## Commit Phase 5
	git add .
	git commit -m "feat(tracker): real-time trade monitoring"
	git tag -a v0.5.0 -m "Phase 5: Trade Tracker"

git-phase6:  ## Commit Phase 6
	git add .
	git commit -m "feat(telegram): bot + commands + scheduler"
	git tag -a v0.6.0 -m "Phase 6: Telegram Bot"

git-phase7:  ## Commit Phase 7
	git add .
	git commit -m "feat(performance): PNL engine + reports"
	git tag -a v0.7.0 -m "Phase 7: Performance DB"
