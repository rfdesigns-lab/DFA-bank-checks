"""
Generic Deterministic Finite Automaton (DFA) engine.

A DFA is a 5-tuple (Q, Σ, δ, q0, F) where:
  Q  = finite set of states
  Σ  = input alphabet
  δ  = transition function Q × Σ → Q
  q0 = initial state (q0 ∈ Q)
  F  = set of accept states (F ⊆ Q)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Generic, Hashable, TypeVar

StateT = TypeVar("StateT", bound=Hashable)
SymbolT = TypeVar("SymbolT", bound=Hashable)


@dataclass
class DFAResult:
    """Result of running a DFA over an input string."""

    accepted: bool
    final_state: Any
    error_message: str = ""
    position: int = -1  # position where processing stopped (for diagnostics)

    def __bool__(self) -> bool:
        return self.accepted


class DFA(Generic[StateT, SymbolT]):
    """
    A generic, reusable DFA implementation.

    States and symbols can be any hashable type (enums, strings, ints, etc.).
    The transition function is a dict mapping (state, symbol) → next_state.
    A special REJECT sink state can be used; once entered, it is never left.
    """

    def __init__(
        self,
        *,
        states: set[StateT],
        alphabet: set[SymbolT],
        transitions: dict[tuple[StateT, SymbolT], StateT],
        initial_state: StateT,
        accept_states: set[StateT],
        reject_state: StateT | None = None,
        symbol_mapper: Callable[[str], SymbolT] | None = None,
    ) -> None:
        """
        Parameters
        ----------
        states:        Complete set of states Q.
        alphabet:      Input alphabet Σ.
        transitions:   Transition table δ: (state, symbol) → state.
        initial_state: Start state q0.
        accept_states: Accepting states F.
        reject_state:  Optional explicit dead/sink state.  Any unrecognised
                       symbol or missing transition goes here.
        symbol_mapper: Optional callable that converts a raw character from
                       the input string to a symbol in Σ.  Useful when
                       multiple characters map to the same symbol class.
        """
        self.states = states
        self.alphabet = alphabet
        self.transitions = transitions
        self.initial_state = initial_state
        self.accept_states = accept_states
        self.reject_state = reject_state
        self.symbol_mapper = symbol_mapper

        self._validate_definition()

    # ------------------------------------------------------------------
    # Validation of the DFA definition itself
    # ------------------------------------------------------------------

    def _validate_definition(self) -> None:
        if self.initial_state not in self.states:
            raise ValueError(f"Initial state {self.initial_state!r} not in states")
        for s in self.accept_states:
            if s not in self.states:
                raise ValueError(f"Accept state {s!r} not in states")
        if self.reject_state is not None and self.reject_state not in self.states:
            raise ValueError(f"Reject state {self.reject_state!r} not in states")

    # ------------------------------------------------------------------
    # Core execution
    # ------------------------------------------------------------------

    def _transition(self, state: StateT, symbol: SymbolT) -> StateT:
        """Return next state for (state, symbol), or reject_state on missing entry."""
        key = (state, symbol)
        if key in self.transitions:
            return self.transitions[key]
        # Implicit dead transition
        if self.reject_state is not None:
            return self.reject_state
        raise KeyError(
            f"No transition defined for state={state!r}, symbol={symbol!r} "
            "and no reject_state configured."
        )

    def run(self, input_string: str) -> DFAResult:
        """
        Process *input_string* character by character through the DFA.

        Returns a DFAResult indicating whether the string is accepted,
        the final state reached, and diagnostic information.
        """
        current_state = self.initial_state

        for position, char in enumerate(input_string):
            # Map raw character to an alphabet symbol if a mapper is provided
            if self.symbol_mapper is not None:
                symbol = self.symbol_mapper(char)
            else:
                symbol = char  # type: ignore[assignment]

            current_state = self._transition(current_state, symbol)

            # Short-circuit: once in reject sink there is no way out
            if self.reject_state is not None and current_state == self.reject_state:
                return DFAResult(
                    accepted=False,
                    final_state=current_state,
                    error_message=f"Rejected at position {position}: unexpected character {char!r}",
                    position=position,
                )

        accepted = current_state in self.accept_states
        return DFAResult(
            accepted=accepted,
            final_state=current_state,
            error_message="" if accepted else f"Ended in non-accepting state {current_state!r}",
            position=len(input_string) - 1,
        )

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def accepts(self, input_string: str) -> bool:
        """Return True iff the DFA accepts *input_string*."""
        return self.run(input_string).accepted

    def __repr__(self) -> str:
        return (
            f"DFA(states={len(self.states)}, "
            f"initial={self.initial_state!r}, "
            f"accept={self.accept_states!r})"
        )
