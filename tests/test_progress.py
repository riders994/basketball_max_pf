import io

from max_pf.progress import bar_callback


def test_bar_callback_animates_in_place_and_finishes():
    buf = io.StringIO()
    render = bar_callback(buf, width=10, label="teams")

    render(0, 2)
    render(1, 2)
    render(2, 2)
    out = buf.getvalue()

    # Every update rewinds with a carriage return; only the final one breaks the line.
    assert out.count("\r") == 3
    assert out.count("\n") == 1
    assert out.endswith("[##########] 2/2 teams\n")
    # Half done -> half the bar filled.
    assert "[#####-----] 1/2 teams" in out


def test_bar_callback_handles_zero_total():
    buf = io.StringIO()
    bar_callback(buf, width=4)(0, 0)  # floored to /1 so there's no ZeroDivisionError
    assert buf.getvalue() == "\r[----] 0/1 teams"
