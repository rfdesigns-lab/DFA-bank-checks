"""Tests for ABA routing number DFA validator."""
import pytest
from src.dfa.validators.routing_number import validate_routing_number


class TestRoutingNumberValid:
    """Known-good ABA routing numbers."""

    def test_well_known_chase(self):
        # Chase Bank routing number
        assert validate_routing_number("021000021")

    def test_well_known_bank_of_america(self):
        # Bank of America (California)
        assert validate_routing_number("121000358")

    def test_well_known_wells_fargo(self):
        assert validate_routing_number("121042882")

    def test_well_known_citibank(self):
        assert validate_routing_number("021000089")

    def test_checksum_zero(self):
        # Manually crafted: 3*1+7*2+1*2+3*0+7*0+1*5+3*5+7*1+1*5
        # = 3+14+2+0+0+5+15+7+5 = 51 — not 0 mod 10, use a verified number
        # 122105155: 3*1+7*2+2+3*1+7*0+5+3*1+7*5+5
        # = 3+14+2+3+0+5+3+35+5 = 70 → 0 mod 10
        assert validate_routing_number("122105155")

    def test_returns_dfa_result_truthy(self):
        result = validate_routing_number("021000021")
        assert result.accepted is True
        assert bool(result) is True


class TestRoutingNumberInvalid:
    """Strings that must be rejected."""

    def test_wrong_checksum(self):
        # Change last digit of a valid number
        assert not validate_routing_number("021000022")

    def test_too_short(self):
        assert not validate_routing_number("12345678")

    def test_too_long(self):
        assert not validate_routing_number("1234567890")

    def test_empty(self):
        assert not validate_routing_number("")

    def test_contains_letters(self):
        assert not validate_routing_number("12345678A")

    def test_contains_hyphen(self):
        assert not validate_routing_number("1234-5678")

    def test_contains_space(self):
        assert not validate_routing_number("1234 5678")

    def test_all_zeros(self):
        # "000000000" checksum: all zeros → 0 mod 10, but leading zeros
        # are technically valid structurally; checksum: 3*0+...= 0 → accepted
        # This IS a valid checksum (trivially), so we just confirm DFA logic:
        result = validate_routing_number("000000000")
        # checksum = 0 mod 10 → accepted by checksum rule
        assert result.accepted is True

    def test_error_message_populated(self):
        result = validate_routing_number("bad")
        assert not result.accepted
        assert len(result.error_message) > 0
