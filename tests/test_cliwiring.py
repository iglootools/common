import pytest

from iglootools.cliwiring import Mark, marked, progress, spinning, styled, tally


class TestMarked:
    @pytest.mark.parametrize(
        ("mark", "symbol", "style"),
        [
            (Mark.OK, "✓", "green"),
            (Mark.WARNING, "⚠", "dark_orange"),
            (Mark.FAILED, "✗", "red"),
            (Mark.SKIPPED, "\N{EN DASH}", "dim"),
        ],
    )
    def test_marked_puts_the_coloured_symbol_first(
        self,
        mark: Mark,
        symbol: str,
        style: str,
    ) -> None:
        line = marked(mark, "nbkp: cloned")

        assert line.plain == f"{symbol} nbkp: cloned"
        assert [(s.start, s.end, s.style) for s in line.spans] == [(0, 1, style)]

    def test_marked_keeps_square_brackets_as_text(self) -> None:
        assert marked(Mark.FAILED, "pip install x[extra]").plain == (
            "✗ pip install x[extra]"
        )

    def test_marked_indents_by_two_spaces_a_level(self) -> None:
        assert marked(Mark.OK, "done", indent=2).plain == "    ✓ done"


class TestStyled:
    def test_styled_colours_the_text_without_a_symbol(self) -> None:
        cell = styled("2 behind", Mark.WARNING)

        assert (cell.plain, cell.style) == ("2 behind", "dark_orange")


class TestTally:
    def test_tally_colours_only_the_counts_above_zero(self) -> None:
        summary = tally([(3, "passed", Mark.OK), (0, "failed", Mark.FAILED)])

        assert summary.plain == "3 passed, 0 failed"
        assert [(s.start, s.end, s.style) for s in summary.spans] == [
            (0, 8, "green"),
        ]


class TestProgress:
    def test_progress_off_a_terminal_draws_nothing_and_accepts_any_name(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        with progress("Fetching", ["nbkp", "photree"]) as done:
            done("nbkp")
            done("unknown")

        assert capsys.readouterr() == ("", "")

    def test_spinning_off_a_terminal_draws_nothing(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        with spinning("Listing the repositories"):
            pass

        assert capsys.readouterr() == ("", "")
