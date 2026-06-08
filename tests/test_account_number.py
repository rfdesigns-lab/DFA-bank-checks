"""Tests for bank account number DFA validator."""
import pytest
from src.dfa.validators.account_number import validate_account_number


class TestAccountNumberValid:
    def test_minimum_8_digits(self):
        assert validate_account_number("12345678")

    def test_maximum_17_digits(self):
        assert validate_account_number("12345678901234567")

    def test_mid_range_12_digits(self):
        assert validate_account_number("123456789012")

    def test_all_zeros_8_digits(self):
        assert validate_account_number("00000000")

    def test_all_nines_17_digits(self):
        assert validate_account_number("99999999999999999")

    def test_returns_dfa_result_truthy(self):
        result = validate_account_number("123456789")
        assert result.accepted is True
        assert bool(result) is True


class TestAccountNumberInvalid:
    def test_too_short_7_digits(self):
        assert not validate_account_number("1234567")

    def test_too_long_18_digits(self):
        assert not validate_account_number("123456789012345678")

    def test_empty(self):
        assert not validate_account_number("")

    def test_contains_letter(self):
        assert not validate_account_number("1234567A")

    def test_contains_hyphen(self):
        assert not validate_account_number("1234-5678")

    def test_contains_space(self):
        assert not validate_account_number("1234 5678")

    def test_contains_dot(self):
        assert not validate_account_number("12345.678")

    def test_error_message_populated(self):
        result = validate_account_number("123")
        assert not result.accepted
        assert len(result.error_message) > 0
