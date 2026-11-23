from pathlib import Path

import pytest

from iglootools.github import actions
from iglootools.github.actions import AnnotationLevel


def test_outputs_are_name_value_lines_in_order() -> None:
    assert actions.format_outputs({"skip": "false", "tag": "v1.0.0"}) == (
        "skip=false\ntag=v1.0.0\n"
    )


def test_an_output_spanning_lines_is_refused() -> None:
    with pytest.raises(actions.MultilineOutputError) as raised:
        actions.format_outputs({"tag": "v1\nskip=true"})
    assert raised.value.name == "tag"


def test_outputs_are_appended_to_what_earlier_steps_wrote(tmp_path: Path) -> None:
    path = tmp_path / "output"
    path.write_text("earlier=1\n", encoding="utf-8")
    actions.append_outputs(path, {"skip": "true"})
    assert path.read_text(encoding="utf-8") == "earlier=1\nskip=true\n"


def test_an_annotation_cannot_start_another_command() -> None:
    assert (
        actions.format_annotation(
            AnnotationLevel.ERROR,
            "v1\n::add-mask::x 100%",
        )
        == "::error::v1%0A::add-mask::x 100%25"
    )
