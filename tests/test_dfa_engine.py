"""Tests for the core DFA engine."""
import pytest
from src.dfa.engine import DFA, DFAResult


def _make_binary_even_dfa():
    """DFA that accepts binary strings with an even number of '1's."""
    states = {"EVEN", "ODD", "REJECT"}
    alphabet = {"0", "1", "X"}

    transitions = {
        ("EVEN", "0"): "EVEN",
        ("EVEN", "1"): "ODD",
        ("ODD", "0"):  "ODD",
        ("ODD", "1"):  "EVEN",
        ("EVEN", "X"): "REJECT",
        ("ODD", "X"):  "REJECT",
    }

    return DFA(
        states=states,
        alphabet=alphabet,
        transitions=transitions,
        initial_state="EVEN",
        accept_states={"EVEN"},
        reject_state="REJECT",
    )


class TestDFAEngine:
    def test_empty_string_accepted_when_initial_is_accept(self):
        dfa = _make_binary_even_dfa()
        result = dfa.run("")
        assert result.accepted  # 0 ones is even

    def test_single_one_rejected(self):
        dfa = _make_binary_even_dfa()
        assert not dfa.accepts("1")

    def test_two_ones_accepted(self):
        dfa = _make_binary_even_dfa()
        assert dfa.accepts("11")

    def test_zeros_accepted(self):
        dfa = _make_binary_even_dfa()
        assert dfa.accepts("000")

    def test_mixed_string_even_ones(self):
        dfa = _make_binary_even_dfa()
        assert dfa.accepts("1010110")  # four 1s

    def test_mixed_string_odd_ones(self):
        dfa = _make_binary_even_dfa()
        # "101" has 2 ones (even) → accepted
        assert dfa.accepts("101")
        # "1001" has 2 ones (even) → accepted
        assert dfa.accepts("1001")
        # "100" has 1 one (odd) → rejected
        assert not dfa.accepts("100")

    def test_invalid_symbol_goes_to_reject(self):
        dfa = _make_binary_even_dfa()
        result = dfa.run("1X0")
        assert not result.accepted
        assert result.final_state == "REJECT"

    def test_reject_state_is_absorbing(self):
        dfa = _make_binary_even_dfa()
        result = dfa.run("X11")  # reject at pos 0, then 11 can't recover
        assert not result.accepted

    def test_result_position_on_reject(self):
        dfa = _make_binary_even_dfa()
        result = dfa.run("0X1")
        assert result.position == 1  # 'X' is at index 1

    def test_dfa_result_bool(self):
        r1 = DFAResult(accepted=True, final_state="EVEN")
        r2 = DFAResult(accepted=False, final_state="ODD", error_message="fail")
        assert bool(r1) is True
        assert bool(r2) is False

    def test_invalid_initial_state_raises(self):
        with pytest.raises(ValueError, match="Initial state"):
            DFA(
                states={"A"},
                alphabet={"x"},
                transitions={},
                initial_state="Z",
                accept_states={"A"},
            )

    def test_invalid_accept_state_raises(self):
        with pytest.raises(ValueError, match="Accept state"):
            DFA(
                states={"A"},
                alphabet={"x"},
                transitions={},
                initial_state="A",
                accept_states={"B"},
            )

    def test_symbol_mapper(self):
        """DFA with a symbol mapper that maps all digits to 'D'."""
        dfa = DFA(
            states={"S", "D1", "REJECT"},
            alphabet={"D", "OTHER"},
            transitions={
                ("S",  "D"):     "D1",
                ("S",  "OTHER"): "REJECT",
                ("D1", "D"):     "REJECT",  # only one digit accepted
                ("D1", "OTHER"): "REJECT",
            },
            initial_state="S",
            accept_states={"D1"},
            reject_state="REJECT",
            symbol_mapper=lambda ch: "D" if ch.isdigit() else "OTHER",
        )
        assert dfa.accepts("5")
        assert not dfa.accepts("55")
        assert not dfa.accepts("a")

    def test_no_reject_state_raises_on_missing_transition(self):
        dfa = DFA(
            states={"A"},
            alphabet={"x"},
            transitions={},
            initial_state="A",
            accept_states={"A"},
            # no reject_state
        )
        with pytest.raises(KeyError):
            dfa.run("x")

    def test_repr(self):
        dfa = _make_binary_even_dfa()
        r = repr(dfa)
        assert "DFA(" in r
