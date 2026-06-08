"""
Bank Account Number Validator (DFA-based).

Rules:
  - Must be between 8 and 17 digits (inclusive), digits only.
  - No separators, spaces, or non-digit characters allowed.

DFA design
----------
State encodes the number of digits read so far.

  States: D0, D1, …, D17, REJECT
  Alphabet: {'0'-'9', OTHER}

Transitions:
  Di  --digit-->  D(i+1)   for i in 0..16
  D17 --digit-->  REJECT   (too many digits)
  Di  --OTHER-->  REJECT

Accept states: D8, D9, …, D17  (8 to 17 digits consumed)
"""

from __future__ import annotations

from src.dfa.engine import DFA, DFAResult


# ---------------------------------------------------------------------------
# State constants
# ---------------------------------------------------------------------------

_MIN_DIGITS = 8
_MAX_DIGITS = 17
_REJECT = "REJECT"

# States are named "D0" … "D17" and "REJECT"
_STATE_D = [f"D{i}" for i in range(_MAX_DIGITS + 1)]  # D0..D17


# ---------------------------------------------------------------------------
# Build the DFA
# ---------------------------------------------------------------------------

def _build_account_dfa() -> DFA:
    states: set[str] = set(_STATE_D) | {_REJECT}
    alphabet: set[str] = set("0123456789") | {"OTHER"}
    transitions: dict[tuple[str, str], str] = {}

    for i in range(_MAX_DIGITS):
        src = _STATE_D[i]
        dst = _STATE_D[i + 1]
        for d in "0123456789":
            transitions[(src, d)] = dst
        transitions[(src, "OTHER")] = _REJECT

    # At D17, any further digit → REJECT
    for d in "0123456789":
        transitions[(_STATE_D[_MAX_DIGITS], d)] = _REJECT
    transitions[(_STATE_D[_MAX_DIGITS], "OTHER")] = _REJECT

    accept_states = {_STATE_D[i] for i in range(_MIN_DIGITS, _MAX_DIGITS + 1)}

    def symbol_mapper(ch: str) -> str:
        return ch if ch.isdigit() else "OTHER"

    return DFA(
        states=states,
        alphabet=alphabet,
        transitions=transitions,
        initial_state=_STATE_D[0],
        accept_states=accept_states,
        reject_state=_REJECT,
        symbol_mapper=symbol_mapper,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_DFA = _build_account_dfa()


def validate_account_number(account: str) -> DFAResult:
    """
    Validate a bank account number string.

    Accepts strings of 8–17 decimal digits with no other characters.
    Returns a DFAResult (truthy on acceptance).
    """
    result = _DFA.run(account)
    if not result.accepted and not result.error_message:
        result = DFAResult(
            accepted=False,
            final_state=result.final_state,
            error_message=f"Account number must be {_MIN_DIGITS}–{_MAX_DIGITS} digits",
            position=result.position,
        )
    return result
