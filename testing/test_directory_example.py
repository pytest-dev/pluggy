from pathlib import Path
import shutil
import subprocess
import sys


EXAMPLE = Path(__file__).resolve().parents[1] / "docs/examples/directory_plugins"


def test_directory_example(tmp_path):
    result = subprocess.run(
        [sys.executable, str(EXAMPLE / "host.py")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    assert result.stdout == "Bonjour Ada!\nHello Ada!\n"
    assert result.stderr == ""


def test_directory_example_discovers_new_modules_and_skips_packages(tmp_path):
    example = tmp_path / "directory_plugins"
    shutil.copytree(EXAMPLE, example)
    (example / "plugins/spanish.py").write_text(
        "import pluggy\n"
        'hookimpl = pluggy.HookimplMarker("greetings")\n'
        "@hookimpl\n"
        "def greeting(name):\n"
        '    return f"Hola {name}!"\n',
        encoding="utf-8",
    )
    subpackage = example / "plugins/subpackage"
    subpackage.mkdir()
    (subpackage / "__init__.py").write_text(
        'raise RuntimeError("Subpackages should not be imported")\n',
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(example / "host.py")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    assert result.stdout == "Hola Ada!\nBonjour Ada!\nHello Ada!\n"
    assert result.stderr == ""
