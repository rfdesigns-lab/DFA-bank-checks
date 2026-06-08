"""Tests for check memo field DFA validator."""
import pytest
from src.dfa.validators.memo import validate_memo


class TestMemoValid:
    def test_simple_word(self):
        assert validate_memo("Rent")

    def test_with_space(self):
        assert validate_memo("Rent for June")

    def test_with_digits(self):
        assert validate_memo("Invoice 12345")

    def test_with_punctuation(self):
        assert validate_memo("Order #42 - paid!")

    def test_at_symbol(self):
        assert validate_memo("Payment @ 5 rate")

    def test_single_char(self):
        assert validate_memo("X")

    def test_exactly_40_chars(self):
        assert validate_memo("A" * 40)

    def test_all_allowed_punctuation(self):
        assert validate_memo(".,;:'-_/()&#@!?")

    def test_returns_dfa_result_truthy(self):
        result = validate_memo("Test memo")
        assert result.accepted is True
        assert bool(result) is True


class TestMemoInvalid:
    def test_empty(self):
        assert not validate_memo("")

    def test_too_long_41_chars(self):
        assert not validate_memo("A" * 41)

    def test_tab_character(self):
        assert not validate_memo("memo\twith\ttabs")

    def test_newline(self):
        assert not validate_memo("memo\nwith\nnewline")

    def test_backtick(self):
        assert not validate_memo("memo`code`")

    def test_caret(self):
        assert not validate_memo("memo^text")

    def test_tilde(self):
        assert not validate_memo("memo~text")

    def test_null_byte(self):
        assert not validate_memo("memo\x00")

    def test_error_message_populated(self):
        result = validate_memo("")
        assert not result.accepted
        assert len(result.error_message) > 0
