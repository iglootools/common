import threading

from iglootools.workspace import parallel


class TestEach:
    def test_each_returns_results_in_the_items_order(self) -> None:
        assert parallel.each([3, 1, 2], lambda n: n * 10) == [30, 10, 20]

    def test_on_done_is_given_each_item_and_its_result_in_finishing_order(
        self,
    ) -> None:
        first_done = threading.Event()
        reported: list[tuple[str, str]] = []

        def work(name: str) -> str:
            if name == "slow":
                first_done.wait(timeout=5)
            return name.upper()

        def on_done(name: str, result: str) -> None:
            reported.append((name, result))
            first_done.set()

        results = parallel.each(["slow", "fast"], work, on_done=on_done)

        assert results == ["SLOW", "FAST"]
        assert reported == [("fast", "FAST"), ("slow", "SLOW")]
