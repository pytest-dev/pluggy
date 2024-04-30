import traceback

from pluggy import Result


def test_exceptions_traceback_doesnt_get_longer_and_longer() -> None:
    def bad() -> None:
        1 / 0

    result = Result.from_call(bad)

    try:
        result.get_result()
    except Exception as exc:
        tb1 = traceback.extract_tb(exc.__traceback__)

    try:
        result.get_result()
    except Exception as exc:
        tb2 = traceback.extract_tb(exc.__traceback__)

    try:
        result.get_result()
    except Exception as exc:
        tb3 = traceback.extract_tb(exc.__traceback__)

    assert len(tb1) == len(tb2) == len(tb3)
