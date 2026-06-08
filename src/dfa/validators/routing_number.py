"""
ABA Routing Number Validator (DFA-based).

An ABA routing number is exactly 9 decimal digits and must satisfy:

    3*d1 + 7*d2 + d3 + 3*d4 + 7*d5 + d6 + 3*d7 + 7*d8 + d9 ≡ 0  (mod 10)

DFA design
----------
The DFA first checks structural validity (exactly 9 digits) character by
character, accumulating the weighted checksum as it goes.  Because the
checksum depends on digit *values* (not just the count of digits), the
state encodes both position and running checksum mod 10.

States: (position, checksum_mod_10)
  position ∈ {0, 1, …, 8, DONE}
  checksum_mod_10 ∈ {0, 1, …, 9}

That gives 9 × 10 = 90 intermediate states plus 10 potential final states
(position=DONE, checksum ∈ 0-9) plus one REJECT sink.

Accept states: (DONE, 0)  — exactly 9 digits AND checksum ≡ 0 mod 10.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import NamedTuple

from src.dfa.engine import DFA, DFAResult


# ---------------------------------------------------------------------------
# State definition
# ---------------------------------------------------------------------------

_WEIGHTS = [3, 7, 1, 3, 7, 1, 3, 7, 1]  # weights for positions 0-8
_NUM_POSITIONS = 9
_DONE = _NUM_POSITIONS  # sentinel for "all 9 digits consumed"
_REJECT = -1             # sink state


class _State(NamedTuple):
    """DFA state encodes (digit position consumed so far, running checksum mod 10)."""
    position: int   # 0 means "no digit read yet"; 9 means all digits read
    checksum: int   # running weighted sum mod 10


# ---------------------------------------------------------------------------
# Build the transition table
# ---------------------------------------------------------------------------

def _build_routing_dfa() -> DFA:
    states: set = set()
    transitions: dict = {}

    # Generate all reachable (position, checksum) pairs
    for pos in range(_NUM_POSITIONS + 1):
        for cs in range(10):
            states.add(_State(pos, cs))

    reject_state = _State(_REJECT, 0)
    states.add(reject_state)

    initial_state = _State(0, 0)
    accept_states = {_State(_DONE, 0)}

    weight_at = _WEIGHTS  # weight for each digit position (0-indexed)

    # Build transitions for positions 0..8 (consuming one digit each)
    for pos in range(_NUM_POSITIONS):
        w = weight_at[pos]
        for cs in range(10):
            src = _State(pos, cs)
            for digit_char in "0123456789":
                d = int(digit_char)
                new_cs = (cs + w * d) % 10
                dst = _State(pos + 1, new_cs)
                transitions[(src, digit_char)] = dst
            # Any non-digit character → reject
            # (handled by reject_state fallback in DFA engine)

    # From DONE states, any additional character → reject
    # (handled implicitly by missing transition + reject_state)

    alphabet = set("0123456789")

    return DFA(
        states=states,
        alphabet=alphabet,
        transitions=transitions,
        initial_state=initial_state,
        accept_states=accept_states,
        reject_state=reject_state,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_DFA = _build_routing_dfa()


def validate_routing_number(routing: str) -> DFAResult:
    """
    Validate an ABA routing number string.

    Accepts exactly 9-digit strings whose weighted checksum is 0 mod 10.
    Returns a DFAResult (truthy on acceptance).
    """
    result = _DFA.run(routing)
    if not result.accepted and not result.error_message:
        result = DFAResult(
            accepted=False,
            final_state=result.final_state,
            error_message="Routing number must be exactly 9 digits with valid checksum",
            position=result.position,
        )
    return result
