"""Tests for CheckProcessor orchestration."""
import pytest
from src.check_processor import CheckProcessor, CheckValidationResult, FieldResult


@pytest.fixture
def processor():
    return CheckProcessor()


class TestCheckProcessorAllValid:
    def test_all_fields_valid(self, processor):
        result = processor.validate(
            routing_number="122105155",
            account_number="123456789",
            amount="1,234.56",
            date="06/08/2026",
            memo="Rent for June",
        )
        assert result.valid
        assert len(result.errors) == 0
        assert bool(result) is True

    def test_result_contains_all_fields(self, processor):
        result = processor.validate(
            routing_number="122105155",
            account_number="123456789",
            amount="100.00",
            date="01/01/2024",
            memo="Test",
        )
        assert "routing_number" in result.fields
        assert "account_number" in result.fields
        assert "amount" in result.fields
        assert "date" in result.fields
        assert "memo" in result.fields


class TestCheckProcessorPartialFields:
    def test_skip_none_fields(self, processor):
        result = processor.validate(
            routing_number="122105155",
            amount="500.00",
        )
        assert result.valid
        assert "routing_number" in result.fields
        assert "amount" in result.fields
        assert "account_number" not in result.fields
        assert "date" not in result.fields

    def test_empty_validate_call(self, processor):
        result = processor.validate()
        assert result.valid  # no fields = vacuously valid
        assert len(result.fields) == 0


class TestCheckProcessorInvalidFields:
    def test_invalid_routing_number(self, processor):
        result = processor.validate(
            routing_number="000000001",  # bad checksum
            account_number="123456789",
            amount="100.00",
            date="06/08/2026",
        )
        assert not result.valid
        assert "routing_number" in result.errors[0]

    def test_multiple_invalid_fields(self, processor):
        result = processor.validate(
            routing_number="bad",
            amount="not-money",
            date="32/99/9999",
        )
        assert not result.valid
        assert len(result.errors) == 3

    def test_error_messages_present(self, processor):
        result = processor.validate(routing_number="123456789")
        assert not result.fields["routing_number"].valid
        assert len(result.fields["routing_number"].error_message) > 0

    def test_field_result_value_preserved(self, processor):
        result = processor.validate(amount="bad")
        assert result.fields["amount"].value == "bad"


class TestCheckProcessorFromDict:
    def test_validate_from_dict_valid(self, processor):
        data = {
            "routing_number": "021000021",
            "account_number": "987654321",
            "amount": "250.00",
            "date": "12/25/2025",
            "memo": "Holiday gift",
        }
        result = processor.validate_from_dict(data)
        assert result.valid

    def test_validate_from_dict_unknown_keys_ignored(self, processor):
        data = {
            "routing_number": "021000021",
            "extra_key": "should be ignored",
        }
        result = processor.validate_from_dict(data)
        assert "routing_number" in result.fields
        assert "extra_key" not in result.fields

    def test_validate_from_dict_missing_fields_skipped(self, processor):
        result = processor.validate_from_dict({"amount": "50.00"})
        assert result.valid
        assert len(result.fields) == 1


class TestFieldResult:
    def test_bool_true_when_valid(self):
        fr = FieldResult("amount", "100.00", valid=True)
        assert bool(fr) is True

    def test_bool_false_when_invalid(self):
        fr = FieldResult("amount", "bad", valid=False, error_message="Invalid")
        assert bool(fr) is False
