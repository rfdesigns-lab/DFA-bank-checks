"""
CLI interface for the DFA bank check validation system.

Usage
-----
Interactive mode (prompts for each field):
    python -m src.cli

JSON input from a file:
    python -m src.cli --json check.json

JSON input from stdin:
    echo '{"routing_number": "122105155", "amount": "100.00"}' | python -m src.cli --json -

Single-field validation:
    python -m src.cli --routing 122105155
    python -m src.cli --account 123456789
    python -m src.cli --amount "1,234.56"
    python -m src.cli --date 06/08/2026
    python -m src.cli --memo "Rent June"
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from src.check_processor import CheckProcessor


# ---------------------------------------------------------------------------
# ANSI colour helpers (graceful fallback on non-TTY)
# ---------------------------------------------------------------------------

def _green(text: str) -> str:
    return f"\033[92m{text}\033[0m" if sys.stdout.isatty() else text


def _red(text: str) -> str:
    return f"\033[91m{text}\033[0m" if sys.stdout.isatty() else text


def _bold(text: str) -> str:
    return f"\033[1m{text}\033[0m" if sys.stdout.isatty() else text


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _print_result(result: Any) -> int:
    """Print a CheckValidationResult and return an exit code (0=valid, 1=invalid)."""
    print()
    print(_bold("=== Check Validation Result ==="))
    for field_name, fr in result.fields.items():
        status = _green("PASS") if fr.valid else _red("FAIL")
        print(f"  {field_name:<20} [{status}]  {fr.value!r}")
        if not fr.valid:
            print(f"    {_red(fr.error_message)}")
    print()
    if result.valid:
        print(_green(_bold("Overall: VALID")) + " — check passed all validations.")
        return 0
    else:
        print(_red(_bold("Overall: INVALID")) + f" — {len(result.errors)} error(s) found.")
        return 1


# ---------------------------------------------------------------------------
# Interactive mode
# ---------------------------------------------------------------------------

def _interactive_mode(processor: CheckProcessor) -> int:
    print(_bold("DFA Bank Check Validator — Interactive Mode"))
    print("(Press Enter to skip any field)\n")

    def prompt(label: str, key: str) -> tuple[str, str | None]:
        val = input(f"  {label}: ").strip()
        return key, val if val else None

    fields = dict([
        prompt("Routing Number (9 digits)", "routing_number"),
        prompt("Account Number (8-17 digits)", "account_number"),
        prompt("Amount (e.g. 1,234.56)", "amount"),
        prompt("Date (MM/DD/YYYY)", "date"),
        prompt("Memo (up to 40 chars)", "memo"),
    ])

    result = processor.validate_from_dict(fields)
    return _print_result(result)


# ---------------------------------------------------------------------------
# JSON mode
# ---------------------------------------------------------------------------

def _json_mode(processor: CheckProcessor, source: str) -> int:
    try:
        if source == "-":
            raw = sys.stdin.read()
        else:
            with open(source, encoding="utf-8") as fh:
                raw = fh.read()
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        print(_red(f"Error reading JSON input: {exc}"), file=sys.stderr)
        return 2

    if not isinstance(data, dict):
        print(_red("JSON input must be an object/dict."), file=sys.stderr)
        return 2

    result = processor.validate_from_dict(data)
    return _print_result(result)


# ---------------------------------------------------------------------------
# Argument parsing & main
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="check-validator",
        description="Validate bank check fields using DFA-based validators.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--json",
        metavar="FILE",
        help="Path to JSON file with check fields (use '-' for stdin).",
    )
    mode.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run interactive prompt (default when no flags given).",
    )

    single = parser.add_argument_group("single-field shortcuts")
    single.add_argument("--routing",  metavar="NUM",    help="Validate one routing number.")
    single.add_argument("--account",  metavar="NUM",    help="Validate one account number.")
    single.add_argument("--amount",   metavar="AMOUNT", help="Validate one dollar amount.")
    single.add_argument("--date",     metavar="DATE",   help="Validate one date (MM/DD/YYYY).")
    single.add_argument("--memo",     metavar="TEXT",   help="Validate one memo field.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    processor = CheckProcessor()

    # Check if any single-field flag was provided
    single_fields = {
        "routing_number": args.routing,
        "account_number": args.account,
        "amount":         args.amount,
        "date":           args.date,
        "memo":           args.memo,
    }
    has_single = any(v is not None for v in single_fields.values())

    if has_single:
        result = processor.validate_from_dict(single_fields)
        return _print_result(result)
    elif args.json:
        return _json_mode(processor, args.json)
    else:
        # Default: interactive
        return _interactive_mode(processor)


if __name__ == "__main__":
    sys.exit(main())
