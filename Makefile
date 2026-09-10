# MIT License
# Copyright (c) 2026 SimBricks
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

CXX               ?= c++
PYTHON            ?= python
PREFIX            ?= $(CURDIR)/out
SIMBRICKS_INC_DIR ?= $(PREFIX)/include
SIMBRICKS_LIB_DIR ?= $(PREFIX)/lib
ENSO_PY_SIM       := enso_sim_bm_py
ENSO_PY_SYS       := enso_sys_py
OUTPUT_FOLDER     ?=
OUTPUT_FLAG       := $(if $(OUTPUT_FOLDER),--output-folder $(OUTPUT_FOLDER))
SIMB_CONDA_CHANNEL:= -c https://conda.simbricks.io/stable
GUEST_SCRIPT      := $(ENSO_PY_SYS)/simbricks/components/enso/system/data/install-enso.sh
BASE_BUILD_CMD    := conda build $(SIMB_CONDA_CHANNEL) -m conda-recipes/conda_build_config.yaml $(OUTPUT_FLAG)

.PHONY: all enso-build enso-install enso-python-develop guest-install \
        enso-sys-py-conda enso-sim-bm-py-conda enso-sim-bm-bin-conda \
        conda-packages pypi-build pypi-publish clean

## --- Ensō behavioral model (vendored C++ sources in enso_bm/) --------------
enso-build:
	$(MAKE) -C enso_bm all CXX="$(CXX)" \
	    SIMBRICKS_INC_DIR="$(SIMBRICKS_INC_DIR)" \
	    SIMBRICKS_LIB_DIR="$(SIMBRICKS_LIB_DIR)"

enso-install: enso-build
	$(MAKE) -C enso_bm install-enso PREFIX="$(PREFIX)"

## --- Guest-side software ---------------------------------------------------
guest-install:
	bash $(GUEST_SCRIPT)

## --- Python packages -------------------------------------------------------
enso-python-develop:
	$(PYTHON) -m pip install -e ./$(ENSO_PY_SYS) --no-deps
	$(PYTHON) -m pip install -e ./$(ENSO_PY_SIM) --no-deps

## --- Conda packages --------------------------------------------------------
enso-sys-py-conda:
	$(BASE_BUILD_CMD) conda-recipes/simbricks-enso-sys-py

enso-sim-bm-py-conda: enso-sys-py-conda
	$(BASE_BUILD_CMD) conda-recipes/simbricks-enso-sim-bm-py

enso-sim-bm-bin-conda:
	$(BASE_BUILD_CMD) conda-recipes/simbricks-enso-sim-bm-bin

conda-packages: enso-sim-bm-py-conda enso-sys-py-conda enso-sim-bm-bin-conda

## --- PyPI packages ---------------------------------------------------------
pypi-build:
	poetry build -C $(ENSO_PY_SYS)
	poetry build -C $(ENSO_PY_SIM)

pypi-publish: pypi-build
	poetry publish -C $(ENSO_PY_SYS)
	poetry publish -C $(ENSO_PY_SIM)

all: conda-packages
.DEFAULT_GOAL := all

clean:
	-$(MAKE) -C enso_bm clean
	rm -rf out
	rm -rf $(ENSO_PY_SIM)/dist $(ENSO_PY_SYS)/dist
