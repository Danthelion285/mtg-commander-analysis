from pathlib import Path


def test_project_configuration_exists():
    root = Path(__file__).resolve().parents[1]
    assert (root / "config" / "settings.yaml").is_file()
    assert (root / "README.md").is_file()
