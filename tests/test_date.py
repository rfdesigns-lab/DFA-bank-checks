"""Tests for check date DFA validator."""
import pytest
from src.dfa.validators.date import validate_date


class TestDateValid:
    def test_typical_date(self):
        assert validate_date("06/08/2026")

    def test_start_of_year(self):
        assert validate_date("01/01/2000")

    def test_end_of_year(self):
        assert validate_date("12/31/1999")

    def test_1900_boundary(self):
        assert validate_date("01/01/1900")

    def test_2099_boundary(self):
        assert validate_date("12/31/2099")

    def test_feb_date(self):
        assert validate_date("02/28/2023")

    def test_mid_century(self):
        assert validate_date("07/04/1976")

    def test_returns_dfa_result_truthy(self):
        result = validate_date("06/08/2026")
        assert result.accepted is True
        assert bool(result) is True


class TestDateInvalid:
    def test_empty(self):
        assert not validate_date("")

    def test_wrong_separator(self):
        assert not validate_date("06-08-2026")

    def test_month_zero(self):
        assert not validate_date("00/08/2026")

    def test_month_13(self):
        assert not validate_date("13/08/2026")

    def test_day_zero(self):
        assert not validate_date("06/00/2026")

    def test_day_32(self):
        assert not validate_date("06/32/2026")

    def test_year_too_early(self):
        assert not validate_date("06/08/1899")

    def test_year_too_late(self):
        assert not validate_date("06/08/2100")

    def test_two_digit_year(self):
        assert not validate_date("06/08/26")

    def test_missing_leading_zero_month(self):
        # "6/08/2026" — single digit month not allowed
        assert not validate_date("6/08/2026")

    def test_extra_characters(self):
        assert not validate_date("06/08/2026X")

    def test_slash_only(self):
        assert not validate_date("//")

    def test_letters(self):
        assert not validate_date("JUN/08/2026")

    def test_error_message_populated(self):
        result = validate_date("bad-date")
        assert not result.accepted
        assert len(result.error_message) > 0
