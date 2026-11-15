import uuid

from app.modules.agents.hierarchy import would_create_cycle

A, B, C, D = (uuid.uuid4() for _ in range(4))


def test_no_supervisor_never_cycles():
    assert not would_create_cycle(A, None, {})


def test_self_supervision():
    assert would_create_cycle(A, A, {})


def test_direct_and_transitive_cycle():
    parents = {B: A, C: B}  # C -> B -> A
    assert would_create_cycle(A, B, parents)
    assert would_create_cycle(A, C, parents)


def test_valid_assignment():
    parents = {B: A, C: B}
    assert not would_create_cycle(D, C, parents)
    assert not would_create_cycle(C, A, parents)


def test_preexisting_loop_is_rejected():
    parents = {B: C, C: B}
    assert would_create_cycle(A, B, parents)
