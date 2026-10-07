.PHONY: all build inits venv

UI_SOURCE := $(shell find pcdswidgets/ui -name "*.ui")
PY_SOURCE := $(filter-out pcdswidgets/builder/ui/%.py, $(filter-out pcdswidgets/_version.py, $(shell find pcdswidgets -name "*.py")))

PY_FORM := $(UI_SOURCE:pcdswidgets/ui/%.ui=pcdswidgets/generated/%_form.py)
PY_BASE := $(UI_SOURCE:pcdswidgets/ui/%.ui=pcdswidgets/generated/%_base.py)
PY_MAIN := $(UI_SOURCE:pcdswidgets/ui/%.ui=pcdswidgets/%.py)

BIN := .pixi/envs/default/bin
BUILD_CMD := $(BIN)/python -m pcdswidgets.builder.build
CHECK_FIX := $(BIN)/ruff check --exit-zero --fix --quiet
FORMAT := $(BIN)/ruff format --quiet

# We need to update the venv before doing any step and after doing all of them
# The order matters here, except the py files in the build target could be done in any order
all:
	$(MAKE) pixi
	$(MAKE) build
	$(MAKE) inits
	$(MAKE) pyproject.toml
	$(MAKE) generated/path_defs.py
	$(MAKE) pixi

build: $(PY_FORM) $(PY_BASE) $(PY_MAIN)

# Special target for forcing rebuild of generated dir
# make rebuild --always-make
rebuild: $(PY_FORM) $(PY_BASE)

# Need to re-run form and base if the ui file is updated
$(PY_FORM): pcdswidgets/generated/%_form.py: pcdswidgets/ui/%.ui
	$(BUILD_CMD) uic $^
	$(CHECK_FIX) $@
	$(FORMAT) $@

$(PY_BASE): pcdswidgets/generated/%_base.py: pcdswidgets/ui/%.ui
	$(BUILD_CMD) base $^
	$(CHECK_FIX) $@
	$(FORMAT) $@

# Only run if the target is missing: user can edit these
$(PY_MAIN):
	$(BUILD_CMD) main $(@:pcdswidgets/%.py=pcdswidgets/ui/%.ui)
	$(CHECK_FIX) $@
	$(FORMAT) $@

inits:
	$(BIN)/python -m pcdswidgets.builder.inits

# Rerun if any python file is updated
pyproject.toml: $(PY_SOURCE)
	$(BIN)/python -m pcdswidgets.builder.entrypoint_finder

generated/path_defs.py: pyproject.toml $(shell find pcdswidgets/builder -type f) $(shell find pcdswidgets/screens -type f)
	$(BIN)/python -m pcdswidgets.builder.screen_paths

pixi:
	pixi run install

# Documentation
html:
	cd docs && pixi run $(MAKE) html
