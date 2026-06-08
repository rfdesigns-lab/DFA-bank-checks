"""
Check Processor — orchestrates all DFA-based validators.

Validates every field of a bank check and returns a structured result
that details which fields passed or failed, along with error messages.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.dfa.engine import DFAResult
from src.dfa.validators.routing_number import validate_routing_number
from src.dfa.validators.account_number import validate_account_number
from src.dfa.validators.amount import validate_amount
from src.dfa.validators.date import validate_date
from src.dfa.validators.memo import validate_memo


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class FieldResult:
    """Validation result for a single check field."""
    field_name: str
    value: str
    valid: bool
    error_message: str = ""

    def __bool__(self) -> bool:
        return self.valid


@dataclass
class CheckValidationResult:
    """Aggregated result for an entire bank check."""
    fields: dict[str, FieldResult] = field(default_factory=dict)

    @property
    def valid(self) -> bool:
        """True only if every field passed validation."""
        return all(f.valid for f in self.fields.values())

    @property
    def errors(self) -> list[str]:
        """Return list of human-readable error strings for failed fields."""
        return [
            f"{r.field_name}: {r.error_message}"
            for r in self.fields.values()
            if not r.valid
        ]

    def __bool__(self) -> bool:
        return self.valid

    def __repr__(self) -> str:
        status = "VALID" if self.valid else "INVALID"
        return f"CheckValidationResult({status}, errors={self.errors})"


# ---------------------------------------------------------------------------
# Processor
# ---------------------------------------------------------------------------

class CheckProcessor:
    """
    Validate a bank check by running each field through its DFA validator.

    All fields are optional at the API level; pass None (or omit) to skip
    validation for that field.  A skipped field is not included in the
    result and does not affect the overall validity.

    Example usage::

        processor = CheckProcessor()
        result = processor.validate(
            routing_number="122105155",
            account_number="123456789",
            amount="1,234.56",
            date="06/08/2026",
            memo="Rent for June",
        )
        if result.valid:
            print("Check is valid")
        else:
            for err in result.errors:
                print(err)
    """

    def validate(
        self,
        *,
        routing_number: str | None = None,
        account_number: str | None = None,
        amount: str | None = None,
        date: str | None = None,
        memo: str | None = None,
    ) -> CheckValidationResult:
        """
        Validate the provided check fields.

        Parameters
        ----------
        routing_number : ABA routing number (9-digit string).
        account_number : Bank account number (8–17 digit string).
        amount         : Dollar amount string (e.g. "1,234.56").
        date           : Check date string (MM/DD/YYYY).
        memo           : Memo/description field (up to 40 chars).

        Returns
        -------
        CheckValidationResult with per-field results and overall validity.
        """
        result = CheckValidationResult()

        checks: list[tuple[str, str | None, object]] = [
            ("routing_number", routing_number, validate_routing_number),
            ("account_number", account_number, validate_account_number),
            ("amount",         amount,         validate_amount),
            ("date",           date,           validate_date),
            ("memo",           memo,           validate_memo),
        ]

        for field_name, value, validator in checks:
            if value is None:
                continue
            dfa_result: DFAResult = validator(value)  # type: ignore[operator]
            result.fields[field_name] = FieldResult(
                field_name=field_name,
                value=value,
                valid=dfa_result.accepted,
                error_message=dfa_result.error_message,
            )

        return result

    def validate_from_dict(self, check_data: dict) -> CheckValidationResult:
        """
        Convenience method: accepts a dict with check field keys.

        Recognised keys: routing_number, account_number, amount, date, memo.
        Unknown keys are silently ignored.
        """
        return self.validate(
            routing_number=check_data.get("routing_number"),
            account_number=check_data.get("account_number"),
            amount=check_data.get("amount"),
            date=check_data.get("date"),
            memo=check_data.get("memo"),
        )
