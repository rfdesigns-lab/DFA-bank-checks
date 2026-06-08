"""
Memo Field Validator (DFA-based).

Rules:
  - Maximum 40 characters.
  - Allowed characters: letters (a-z, A-Z), digits (0-9), spaces, and
    common punctuation: . , : ; ' - _ / ( ) & # @ ! ?
  - Must contain at least 1 character (empty memo is rejected).

DFA design
----------
State encodes the number of valid characters read so far.

  States: C0 (START/empty), C1 … C40 (count of chars read), REJECT
  Alphabet: {VALID, INVALID}

  Ci --VALID--> C(i+1)   for i in 0..39
  C40 --VALID--> REJECT   (too long)
  Ci --INVALID-> REJECT

Accept states: C1 … C40  (1 to 40 valid characters)
"""

from __future__ import annotations

from src.dfa.engine import DFA, DFAResult


_MAX_CHARS = 40
_REJECT = "REJECT"
_VALID = "VALID"
_INVALID = "INVALID"

# Allowed character set
_ALLOWED: frozenset[str] = frozenset(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    " .,;:'-_/()"
    "&# @!?"
)


def _sym(ch: str) -> str:
    return _VALID if ch in _ALLOWED else _INVALID


def _build_memo_dfa() -> DFA:
    # States: "C0" .. "C40" plus "REJECT"
    state_names = [f"C{i}" for i in range(_MAX_CHARS + 1)]
    states: set[str] = set(state_names) | {_REJECT}
    alphabet: set[str] = {_VALID, _INVALID}
    transitions: dict[tuple[str, str], str] = {}

    for i in range(_MAX_CHARS):
        src = state_names[i]
        dst = state_names[i + 1]
        transitions[(src, _VALID)] = dst
        transitions[(src, _INVALID)] = _REJECT

    # At C40 (max length), any additional character → REJECT
    transitions[(state_names[_MAX_CHARS], _VALID)] = _REJECT
    transitions[(state_names[_MAX_CHARS], _INVALID)] = _REJECT

    # REJECT is absorbing
    transitions[(_REJECT, _VALID)] = _REJECT
    transitions[(_REJECT, _INVALID)] = _REJECT

    # Accept C1 .. C40 (at least one character, at most 40)
    accept_states = {state_names[i] for i in range(1, _MAX_CHARS + 1)}

    return DFA(
        states=states,
        alphabet=alphabet,
        transitions=transitions,
        initial_state=state_names[0],
        accept_states=accept_states,
        reject_state=_REJECT,
        symbol_mapper=_sym,
    )


_DFA = _build_memo_dfa()


def validate_memo(memo: str) -> DFAResult:
    """
    Validate a check memo field.

    Accepts 1–40 characters consisting of letters, digits, spaces, and
    common punctuation (. , : ; ' - _ / ( ) & # @ ! ?).

    Returns a DFAResult (truthy on acceptance).
    """
    result = _DFA.run(memo)
    if not result.accepted and not result.error_message:
        result = DFAResult(
            accepted=False,
            final_state=result.final_state,
            error_message=f"Memo must be 1–{_MAX_CHARS} chars of letters, digits, and common punctuation",
            position=result.position,
        )
    return result
