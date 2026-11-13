SEED ?= 20261022
PY ?= python3

.PHONY: install test starter full reproduce reproduce-full validate dashboard serve docs clean

install:            ## install dependencies
	$(PY) -m pip install -r requirements.txt

test:               ## run the test suite (2k-session dataset, ~20 s)
	$(PY) -m pytest -q

starter:            ## 5k sessions / ~100k events, all formats + SQLite FK check (~15 s)
	$(PY) -m journeylab generate --scale 0.05 --seed $(SEED) --out output/starter --sqlite --force

full:               ## 100k sessions / ~2M events (~3-4 min, ~2.5 GB with JSON+SQL)
	$(PY) -m journeylab generate --scale 1.0 --seed $(SEED) --out output/full --sqlite --force

reproduce:          ## generate starter twice, compare row counts + SHA-256
	$(PY) -m journeylab reproduce --scale 0.05 --seed $(SEED) --out output/repro

reproduce-full:     ## same at full scale (~7 min)
	$(PY) -m journeylab reproduce --scale 1.0 --seed $(SEED) --out output/repro_full

validate:           ## re-validate an exported dataset from its files
	$(PY) -m journeylab validate --data output/starter

dashboard:          ## build web/data/*.json from output/full
	$(PY) -m journeylab dashboard --data output/full --web web

serve:              ## open the dashboard at http://localhost:8000
	$(PY) -m journeylab serve

docs:               ## regenerate docs/data_dictionary.md and sql/schema.sql from schema.py
	$(PY) -m journeylab docs --root .

clean:
	rm -rf output .pytest_cache **/__pycache__
