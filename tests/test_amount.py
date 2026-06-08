"""Tests for dollar amount DFA validator."""
import pytest
from src.dfa.validators.amount import validate_amount


class TestAmountValid:
    def test_simple_integer(self):
        assert validate_amount("5")

    def test_two_digit_integer(self):
        assert validate_amount("42")

    def test_three_digit_integer(self):
        assert validate_amount("999")

    def test_with_cents(self):
        assert validate_amount("5.50")

    def test_zero_cents(self):
        assert validate_amount("100.00")

    def test_one_comma_group(self):
        assert validate_amount("1,234")

    def test_two_leading_digits_comma_group(self):
        assert validate_amount("12,345")

    def test_one_comma_group_with_cents(self):
        assert validate_amount("1,234.56")

    def test_two_comma_groups(self):
        assert validate_amount("1,234,567")

    def test_two_comma_groups_with_cents(self):
        assert validate_amount("1,234,567.89")

    def test_sub_dollar(self):
        assert validate_amount("0.99")

    def test_one_cent(self):
        assert validate_amount("0.01")

    def test_large_amount(self):
        assert validate_amount("9,999,999.99")

    def test_returns_dfa_result_truthy(self):
        result = validate_amount("100.00")
        assert result.accepted is True
        assert bool(result) is True


class TestAmountInvalid:
    def test_bare_zero(self):
        # Zero-value check is rejected
        assert not validate_amount("0")

    def test_zero_point_zero(self):
        assert not validate_amount("0.00")

    def test_empty(self):
        assert not validate_amount("")

    def test_leading_zero(self):
        assert not validate_amount("01.00")

    def test_three_decimal_places(self):
        assert not validate_amount("1.234")

    def test_one_decimal_place(self):
        assert not validate_amount("1.5")

    def test_bad_comma_placement_four_in_leading_group(self):
        # 4 leading digits before comma — invalid (should be at most 3)
        assert not validate_amount("1234,567")

    def test_bad_comma_placement_four_in_group(self):
        assert not validate_amount("1,2345")

    def test_currency_symbol(self):
        assert not validate_amount("$100.00")

    def test_letters(self):
        assert not validate_amount("one hundred")

    def test_double_decimal(self):
        assert not validate_amount("1..00")

    def test_trailing_dot(self):
        assert not validate_amount("100.")

    def test_error_message_populated(self):
        result = validate_amount("abc")
        assert not result.accepted
        assert len(result.error_message) > 0
