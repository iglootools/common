from pathlib import Path

from iglootools.demo import record
from iglootools.project import DemoSettings

SETTINGS = DemoSettings(
    script=Path("/p/demo/demo.sh"),
    recording=Path("/p/demo/demo.cast"),
    window_size="160x45",
    workflow="demo.yml",
    artifact="demo-recording",
    cast="demo.cast",
    readme=Path("/p/README.md"),
    poster=Path("/p/demo/demo.svg"),
)


def test_title_names_the_version_when_known() -> None:
    assert record.title("nbkp", "1.4.1") == "nbkp v1.4.1 demo"
    assert record.title("nbkp", None) == "nbkp demo"


def test_installed_version_of_a_missing_distribution_is_none() -> None:
    assert record.installed_version("no-such-distribution-here") is None
    assert record.installed_version("iglootools") is not None


def test_recording_fails_when_the_demo_fails() -> None:
    command = record.recording_command(SETTINGS, "nbkp demo")
    assert command[:3] == ["asciinema", "rec", "--return"]
    assert command[-3:] == ["--command", "/p/demo/demo.sh", "/p/demo/demo.cast"]


def test_the_environments_bin_comes_first_on_path() -> None:
    env = record.recording_environment(
        {"PATH": "/usr/bin", "HOME": "/h"},
        python="/p/.venv/bin/python",
    )
    assert env == {"PATH": "/p/.venv/bin:/usr/bin", "HOME": "/h"}
