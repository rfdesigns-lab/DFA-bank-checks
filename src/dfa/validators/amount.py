"""
Dollar Amount Validator (DFA-based).

Accepted formats (examples):
    "5"             integer, no cents
    "5.50"          with cents
    "1,234.56"      comma-separated thousands (1-3 leading digits, then groups of 3)
    "12,345"        two leading digits before comma
    "1,234,567"     chained comma groups
    "1,234,567.89"  full format
    "0.99"          sub-dollar (non-zero fractional part)

Rules enforced by the DFA:
  1. Optional 1-3 leading digits before the first comma; each comma group is
     exactly 3 digits (e.g. "1,234" or "12,345" or "123,456").
  2. At most one decimal point, followed by exactly 2 decimal digits.
  3. Amount must be > 0:
     - Bare "0" is rejected.
     - "0.00" is rejected.
     - "0.01" through "0.99" are accepted.
  4. No leading zeros in the integer part (except bare "0" and "0.XX").
  5. No currency symbol ($) — caller strips it if needed.

DFA states
----------
  START          : nothing read yet
  INT_ZERO       : read leading "0" (only "." allowed next)
  INT_1          : 1 non-zero leading integer digit
  INT_2          : 2 leading integer digits
  INT_3          : 3 leading integer digits
  CGAP           : just read a comma; expecting first digit of group
  CGRP_1         : 1 digit of current comma group read
  CGRP_2         : 2 digits of current comma group read
  CGRP_3         : 3 digits of current comma group read — ACCEPT
  DOT            : read '.' from non-zero integer path
  FRAC_1         : 1 fractional digit read
  FRAC_2         : 2 fractional digits read — ACCEPT
  ZDOT           : read '.' after "0" integer
  ZFRAC_0        : first fractional digit after "0." was '0'
  ZFRAC_NZ       : first fractional digit after "0." was nonzero
  ZFRAC_ACCEPT   : second fractional digit after "0." — ACCEPT (unless both were '0')
  ZFRAC_00       : "0.00" — not an accept state
  REJECT         : dead/sink state
"""

from __future__ import annotations

from enum import Enum, auto

from src.dfa.engine import DFA, DFAResult


class _S(Enum):
    START = auto()
    INT_ZERO = auto()
    INT_1 = auto()
    INT_2 = auto()
    INT_3 = auto()
    CGAP = auto()       # after comma, awaiting 3-digit group
    CGRP_1 = auto()    # 1 digit of current group
    CGRP_2 = auto()    # 2 digits of current group
    CGRP_3 = auto()    # 3 digits of current group (complete) — ACCEPT
    DOT = auto()
    FRAC_1 = auto()
    FRAC_2 = auto()    # ACCEPT
    ZDOT = auto()
    ZFRAC_0 = auto()
    ZFRAC_NZ = auto()
    ZFRAC_ACCEPT = auto()   # "0.XY" where not both X and Y are 0 — ACCEPT
    ZFRAC_00 = auto()       # "0.00" terminal — not an accept state
    REJECT = auto()


_NONZERO = "NONZERO"
_ZERO = "ZERO"
_COMMA = ","
_DOT = "."
_OTHER = "OTHER"


def _sym(ch: str) -> str:
    if ch == "0":
        return _ZERO
    if ch.isdigit():
        return _NONZERO
    if ch == ",":
        return _COMMA
    if ch == ".":
        return _DOT
    return _OTHER


def _build_amount_dfa() -> DFA:
    S = _S

    accept_states = {
        S.INT_1, S.INT_2, S.INT_3,  # integer-only (1-3 digits, no comma)
        S.CGRP_3,                    # comma group complete
        S.FRAC_2,                    # decimal with 2 fractional digits
        S.ZFRAC_ACCEPT,              # "0.XY" non-zero
    }

    transitions: dict[tuple[_S, str], _S] = {}

    def t(src: _S, sym: str, dst: _S) -> None:
        transitions[(src, sym)] = dst

    # REJECT is absorbing
    for sym in (_ZERO, _NONZERO, _COMMA, _DOT, _OTHER):
        t(S.REJECT, sym, S.REJECT)

    # --- START ---
    t(S.START, _NONZERO, S.INT_1)
    t(S.START, _ZERO,    S.INT_ZERO)
    t(S.START, _COMMA,   S.REJECT)
    t(S.START, _DOT,     S.REJECT)
    t(S.START, _OTHER,   S.REJECT)

    # --- INT_ZERO: only decimal allowed ---
    t(S.INT_ZERO, _DOT,     S.ZDOT)
    t(S.INT_ZERO, _ZERO,    S.REJECT)
    t(S.INT_ZERO, _NONZERO, S.REJECT)
    t(S.INT_ZERO, _COMMA,   S.REJECT)
    t(S.INT_ZERO, _OTHER,   S.REJECT)

    # --- INT_1: 1 leading digit ---
    t(S.INT_1, _ZERO,    S.INT_2)
    t(S.INT_1, _NONZERO, S.INT_2)
    t(S.INT_1, _COMMA,   S.CGAP)   # "1,xxx"
    t(S.INT_1, _DOT,     S.DOT)
    t(S.INT_1, _OTHER,   S.REJECT)

    # --- INT_2: 2 leading digits ---
    t(S.INT_2, _ZERO,    S.INT_3)
    t(S.INT_2, _NONZERO, S.INT_3)
    t(S.INT_2, _COMMA,   S.CGAP)   # "12,xxx"
    t(S.INT_2, _DOT,     S.DOT)
    t(S.INT_2, _OTHER,   S.REJECT)

    # --- INT_3: 3 leading digits ---
    t(S.INT_3, _ZERO,    S.REJECT)  # 4th leading digit without comma = invalid
    t(S.INT_3, _NONZERO, S.REJECT)
    t(S.INT_3, _COMMA,   S.CGAP)   # "123,xxx"
    t(S.INT_3, _DOT,     S.DOT)
    t(S.INT_3, _OTHER,   S.REJECT)

    # --- CGAP: just read comma, expecting 3-digit group ---
    t(S.CGAP, _ZERO,    S.CGRP_1)
    t(S.CGAP, _NONZERO, S.CGRP_1)
    t(S.CGAP, _COMMA,   S.REJECT)
    t(S.CGAP, _DOT,     S.REJECT)
    t(S.CGAP, _OTHER,   S.REJECT)

    # --- CGRP_1: 1 digit of group read ---
    t(S.CGRP_1, _ZERO,    S.CGRP_2)
    t(S.CGRP_1, _NONZERO, S.CGRP_2)
    t(S.CGRP_1, _COMMA,   S.REJECT)
    t(S.CGRP_1, _DOT,     S.REJECT)
    t(S.CGRP_1, _OTHER,   S.REJECT)

    # --- CGRP_2: 2 digits of group read ---
    t(S.CGRP_2, _ZERO,    S.CGRP_3)
    t(S.CGRP_2, _NONZERO, S.CGRP_3)
    t(S.CGRP_2, _COMMA,   S.REJECT)
    t(S.CGRP_2, _DOT,     S.REJECT)
    t(S.CGRP_2, _OTHER,   S.REJECT)

    # --- CGRP_3: 3 digits complete — ACCEPT; chain comma or decimal ---
    t(S.CGRP_3, _ZERO,    S.REJECT)  # 4th digit in group
    t(S.CGRP_3, _NONZERO, S.REJECT)
    t(S.CGRP_3, _COMMA,   S.CGAP)    # another group
    t(S.CGRP_3, _DOT,     S.DOT)
    t(S.CGRP_3, _OTHER,   S.REJECT)

    # --- DOT: decimal point from non-zero integer ---
    t(S.DOT, _ZERO,    S.FRAC_1)
    t(S.DOT, _NONZERO, S.FRAC_1)
    t(S.DOT, _COMMA,   S.REJECT)
    t(S.DOT, _DOT,     S.REJECT)
    t(S.DOT, _OTHER,   S.REJECT)

    # --- FRAC_1: 1 fractional digit read ---
    t(S.FRAC_1, _ZERO,    S.FRAC_2)
    t(S.FRAC_1, _NONZERO, S.FRAC_2)
    t(S.FRAC_1, _COMMA,   S.REJECT)
    t(S.FRAC_1, _DOT,     S.REJECT)
    t(S.FRAC_1, _OTHER,   S.REJECT)

    # --- FRAC_2: ACCEPT; terminal ---
    for sym in (_ZERO, _NONZERO, _COMMA, _DOT, _OTHER):
        t(S.FRAC_2, sym, S.REJECT)

    # --- ZDOT: decimal point after "0" ---
    t(S.ZDOT, _ZERO,    S.ZFRAC_0)
    t(S.ZDOT, _NONZERO, S.ZFRAC_NZ)
    t(S.ZDOT, _COMMA,   S.REJECT)
    t(S.ZDOT, _DOT,     S.REJECT)
    t(S.ZDOT, _OTHER,   S.REJECT)

    # --- ZFRAC_0: first frac digit was '0' ---
    t(S.ZFRAC_0, _ZERO,    S.ZFRAC_00)    # "0.00" → reject terminal
    t(S.ZFRAC_0, _NONZERO, S.ZFRAC_ACCEPT)  # "0.0X" (X≠0) → accept
    t(S.ZFRAC_0, _COMMA,   S.REJECT)
    t(S.ZFRAC_0, _DOT,     S.REJECT)
    t(S.ZFRAC_0, _OTHER,   S.REJECT)

    # --- ZFRAC_NZ: first frac digit was nonzero ---
    t(S.ZFRAC_NZ, _ZERO,    S.ZFRAC_ACCEPT)
    t(S.ZFRAC_NZ, _NONZERO, S.ZFRAC_ACCEPT)
    t(S.ZFRAC_NZ, _COMMA,   S.REJECT)
    t(S.ZFRAC_NZ, _DOT,     S.REJECT)
    t(S.ZFRAC_NZ, _OTHER,   S.REJECT)

    # --- ZFRAC_ACCEPT: ACCEPT; terminal ---
    for sym in (_ZERO, _NONZERO, _COMMA, _DOT, _OTHER):
        t(S.ZFRAC_ACCEPT, sym, S.REJECT)

    # --- ZFRAC_00: "0.00" — not an accept state; terminal ---
    for sym in (_ZERO, _NONZERO, _COMMA, _DOT, _OTHER):
        t(S.ZFRAC_00, sym, S.REJECT)

    states = set(S)
    alphabet = {_ZERO, _NONZERO, _COMMA, _DOT, _OTHER}

    return DFA(
        states=states,
        alphabet=alphabet,
        transitions=transitions,
        initial_state=S.START,
        accept_states=accept_states,
        reject_state=S.REJECT,
        symbol_mapper=_sym,
    )


_DFA = _build_amount_dfa()


def validate_amount(amount: str) -> DFAResult:
    """
    Validate a dollar amount string.

    Accepted: non-zero integers and decimals with optional comma grouping.
    Exactly 2 decimal places required if a decimal point is present.
    Leading zeros only allowed for "0.XX" form where XX != "00".
    Zero value ("0", "0.00") is rejected.

    Returns a DFAResult (truthy on acceptance).
    """
    result = _DFA.run(amount)
    if not result.accepted and not result.error_message:
        result = DFAResult(
            accepted=False,
            final_state=result.final_state,
            error_message="Invalid dollar amount format",
            position=result.position,
        )
    return result
