from handoff.severity import severity_rank


def test_warning_ranks_above_info() -> None:
    assert severity_rank('warning') > severity_rank('info')
