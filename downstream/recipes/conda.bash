#!/usr/bin/env bash
# Bootstrap, install, and test conda against the local pluggy checkout.
# Called from run_downstream.py via the conda recipe.
set -eu

cd "$(dirname "$0")/../conda"

# dev/start needs relaxed error handling during bootstrap.
set +eu
source dev/start
set -eu

# Install pluggy editable from the parent checkout.
pip install -e ../..

# Mirror conda's own CI condarc-defaults so tests that create temporary
# environments can resolve packages.
conda config --add channels defaults

pytest \
    -m 'not integration and not installed' \
    --deselect=tests/cli/test_main_export.py::test_export_from_history_format
