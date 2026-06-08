"""
Check Date Validator (DFA-based).

Accepted format: MM/DD/YYYY

Rules enforced by the DFA:
  1. Exactly MM/DD/YYYY — two digit month, two digit day, four digit year.
  2. Month: 01–12
  3. Day: 01–31
  4. Year: 1900–2099  (reasonable range for bank checks)
  5. No extra characters before or after.

DFA design
----------
The DFA processes the date character by character, tracking position and
partial field values so it can enforce range constraints inline.

States (in order of the format string):
  START
  M1            : read first digit of month
  M2            : read second digit of month  — month field complete
  SEP1          : read first '/'
  D1            : read first digit of day
  D2            : read second digit of day   — day field complete
  SEP2          : read second '/'
  Y1            : read first digit of year
  Y2            : read second digit of year
  Y3            : read third digit of year
  Y4            : read fourth digit of year  [ACCEPT]
  REJECT        : dead state

Month range (01–12) is enforced by remembering the first month digit:
  - M1 digit 0  → M1_ZERO  (second digit must be 1–9)
  - M1 digit 1  → M1_ONE   (second digit must be 0–2)
  - M1 digit 2–9 → REJECT

Day range (01–31) is enforced similarly:
  - D1 digit 0  → D1_ZERO  (second digit 1–9)
  - D1 digit 1,2 → D1_LOW  (second digit 0–9)
  - D1 digit 3  → D1_THREE (second digit 0–1)
  - D1 digit 4–9 → REJECT

Year: first digit must be 1 or 2 (for 1900–2099).
  - Y1 = '1' → Y1_ONE  (next digit 9)
  - Y1 = '2' → Y1_TWO  (next digit 0)
  - others → REJECT
  Then Y2 constrains Y3 range:
  - After "19": Y3 any digit 0–9 → Y3_19X
  - After "20": Y3 any digit 0–9 → Y3_20X
  Y4 any digit completes.
"""

from __future__ import annotations

from enum import Enum, auto

from src.dfa.engine import DFA, DFAResult


class _S(Enum):
    START = auto()
    # Month
    M1_ZERO = auto()    # first month digit was '0'
    M1_ONE = auto()     # first month digit was '1'
    M2 = auto()         # month complete
    # Separator
    SEP1 = auto()
    # Day
    D1_ZERO = auto()    # first day digit was '0'
    D1_LOW = auto()     # first day digit was '1' or '2'
    D1_THREE = auto()   # first day digit was '3'
    D2 = auto()         # day complete
    # Separator
    SEP2 = auto()
    # Year
    Y1_ONE = auto()     # year starts with '1'
    Y1_TWO = auto()     # year starts with '2'
    Y2_19 = auto()      # year so far "19"
    Y2_20 = auto()      # year so far "20"
    Y3 = auto()         # three year digits read
    Y4 = auto()         # year complete [ACCEPT]
    REJECT = auto()


def _build_date_dfa() -> DFA:
    S = _S
    transitions: dict[tuple[_S, str], _S] = {}
    alphabet = set("0123456789/")

    def t(src: _S, sym: str, dst: _S) -> None:
        transitions[(src, sym)] = dst

    def reject_all(src: _S, chars: str = "0123456789/") -> None:
        for c in chars:
            if (src, c) not in transitions:
                t(src, c, S.REJECT)

    # REJECT is absorbing
    for c in "0123456789/":
        t(S.REJECT, c, S.REJECT)

    # --- START: read first digit of month ---
    t(S.START, "0", S.M1_ZERO)
    t(S.START, "1", S.M1_ONE)
    for c in "23456789":
        t(S.START, c, S.REJECT)
    t(S.START, "/", S.REJECT)

    # --- Month first digit '0': second digit must be 1–9 ---
    t(S.M1_ZERO, "0", S.REJECT)
    for c in "123456789":
        t(S.M1_ZERO, c, S.M2)
    t(S.M1_ZERO, "/", S.REJECT)

    # --- Month first digit '1': second digit must be 0–2 ---
    for c in "012":
        t(S.M1_ONE, c, S.M2)
    for c in "3456789":
        t(S.M1_ONE, c, S.REJECT)
    t(S.M1_ONE, "/", S.REJECT)

    # --- M2: month complete, expect '/' ---
    t(S.M2, "/", S.SEP1)
    for c in "0123456789":
        t(S.M2, c, S.REJECT)

    # --- SEP1: expect first digit of day ---
    t(S.SEP1, "0", S.D1_ZERO)
    t(S.SEP1, "1", S.D1_LOW)
    t(S.SEP1, "2", S.D1_LOW)
    t(S.SEP1, "3", S.D1_THREE)
    for c in "456789":
        t(S.SEP1, c, S.REJECT)
    t(S.SEP1, "/", S.REJECT)

    # --- Day first digit '0': second digit 1–9 ---
    t(S.D1_ZERO, "0", S.REJECT)
    for c in "123456789":
        t(S.D1_ZERO, c, S.D2)
    t(S.D1_ZERO, "/", S.REJECT)

    # --- Day first digit '1' or '2': second digit 0–9 ---
    for c in "0123456789":
        t(S.D1_LOW, c, S.D2)
    t(S.D1_LOW, "/", S.REJECT)

    # --- Day first digit '3': second digit 0–1 ---
    for c in "01":
        t(S.D1_THREE, c, S.D2)
    for c in "23456789":
        t(S.D1_THREE, c, S.REJECT)
    t(S.D1_THREE, "/", S.REJECT)

    # --- D2: day complete, expect '/' ---
    t(S.D2, "/", S.SEP2)
    for c in "0123456789":
        t(S.D2, c, S.REJECT)

    # --- SEP2: expect first digit of year ---
    t(S.SEP2, "1", S.Y1_ONE)
    t(S.SEP2, "2", S.Y1_TWO)
    for c in "034567890":
        if (S.SEP2, c) not in transitions:
            t(S.SEP2, c, S.REJECT)
    t(S.SEP2, "/", S.REJECT)

    # --- Year first digit '1': next must be '9' (1900s) ---
    t(S.Y1_ONE, "9", S.Y2_19)
    for c in "01234578":
        t(S.Y1_ONE, c, S.REJECT)
    t(S.Y1_ONE, "/", S.REJECT)

    # --- Year first digit '2': next must be '0' (2000s) ---
    t(S.Y1_TWO, "0", S.Y2_20)
    for c in "123456789":
        t(S.Y1_TWO, c, S.REJECT)
    t(S.Y1_TWO, "/", S.REJECT)

    # --- Y2_19 / Y2_20: third year digit 0–9 ---
    for c in "0123456789":
        t(S.Y2_19, c, S.Y3)
        t(S.Y2_20, c, S.Y3)
    t(S.Y2_19, "/", S.REJECT)
    t(S.Y2_20, "/", S.REJECT)

    # --- Y3: fourth year digit 0–9 → Y4 (accept) ---
    for c in "0123456789":
        t(S.Y3, c, S.Y4)
    t(S.Y3, "/", S.REJECT)

    # --- Y4: accept state, any further character → REJECT ---
    for c in "0123456789/":
        t(S.Y4, c, S.REJECT)

    states = set(S)
    accept_states = {S.Y4}

    return DFA(
        states=states,
        alphabet=alphabet,
        transitions=transitions,
        initial_state=S.START,
        accept_states=accept_states,
        reject_state=S.REJECT,
    )


_DFA = _build_date_dfa()


def validate_date(date: str) -> DFAResult:
    """
    Validate a check date string in MM/DD/YYYY format.

    Accepts dates with:
      - Month 01–12
      - Day 01–31
      - Year 1900–2099

    Returns a DFAResult (truthy on acceptance).
    """
    result = _DFA.run(date)
    if not result.accepted and not result.error_message:
        result = DFAResult(
            accepted=False,
            final_state=result.final_state,
            error_message="Date must be in MM/DD/YYYY format (year 1900-2099)",
            position=result.position,
        )
    return result
