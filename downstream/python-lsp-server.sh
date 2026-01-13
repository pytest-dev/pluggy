set -eux -o pipefail
if [[ ! -d python-lsp-server ]]; then
	git clone https://github.com/python-lsp/python-lsp-server.git
fi

pushd python-lsp-server
trap popd EXIT

git pull

python -m venv venv

if [[ "$OS" == "Windows_NT" ]]; then
    VENV_PYTHON="venv/Scripts/python"
    VENV_PYTEST="venv/Scripts/pytest"
else
    VENV_PYTHON="venv/bin/python"
    VENV_PYTEST="venv/bin/pytest"
fi

# upgrade pip safely
"$VENV_PYTHON" -m pip install -U pip

# install python-lsp-server test deps
"$VENV_PYTHON" -m pip install -e .[test]

# install local pluggy
"$VENV_PYTHON" -m pip install -e ..

# run tests
"$VENV_PYTEST" || true
