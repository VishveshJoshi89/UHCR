import uhcr
try:
    import tomllib
except ImportError:
    import tomli as tomllib
from pathlib import Path

def test_version_number():
    assert uhcr.__version__ == "4.1.0"

def test_pyproject_version():
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)
    assert data["project"]["version"] == "4.1.0"
