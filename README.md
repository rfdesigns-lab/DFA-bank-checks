# DFA Bank Check Validation System

A bank check validation system built on **Deterministic Finite Automata (DFA)** principles. Every field of a check — routing number, account number, dollar amount, date, and memo — is validated by a dedicated DFA that processes the input character by character with no regular-expression shortcuts.

## What Is a DFA?

A **Deterministic Finite Automaton** is a 5-tuple **(Q, Σ, δ, q₀, F)** where:

| Component | Description |
|-----------|-------------|
| **Q** | Finite set of states |
| **Σ** | Input alphabet (set of symbols) |
| **δ** | Transition function: Q × Σ → Q |
| **q₀** | Initial state (q₀ ∈ Q) |
| **F** | Set of accept states (F ⊆ Q) |

The machine starts in q₀ and reads one symbol at a time. Each symbol causes a deterministic transition to a new state. After consuming all input the machine **accepts** if the current state is in F, otherwise it **rejects**.

## Project Structure

```
DFA-bank-checks/
├── src/
│   ├── dfa/
│   │   ├── engine.py               # Generic DFA implementation
│   │   └── validators/
│   │       ├── routing_number.py   # ABA routing number DFA
│   │       ├── account_number.py   # Account number DFA
│   │       ├── amount.py           # Dollar amount DFA
│   │       ├── date.py             # MM/DD/YYYY date DFA
│   │       └── memo.py             # Memo field DFA
│   ├── check_processor.py          # Orchestrates all validators
│   └── cli.py                      # Command-line interface
├── tests/
│   ├── test_dfa_engine.py
│   ├── test_routing_number.py
│   ├── test_account_number.py
│   ├── test_amount.py
│   ├── test_date.py
│   ├── test_memo.py
│   └── test_check_processor.py
├── pyproject.toml
└── README.md
```

## DFA Design for Each Validator

### Routing Number (`routing_number.py`)

**Rule:** 9 decimal digits satisfying the ABA checksum:  
`3d₁ + 7d₂ + d₃ + 3d₄ + 7d₅ + d₆ + 3d₇ + 7d₈ + d₉ ≡ 0 (mod 10)`

**State encoding:** `(position, running_checksum_mod_10)`
- 9 positions × 10 checksum values = 90 intermediate states
- Accept state: `(9, 0)` — all 9 digits consumed and checksum is 0 mod 10
- The running checksum is updated on each digit transition

### Account Number (`account_number.py`)

**Rule:** 8 to 17 decimal digits, no other characters.

**States:** `D0, D1, …, D17, REJECT`
- `Di --digit--> D(i+1)` for i in 0..16
- Any non-digit → REJECT immediately
- Accept states: D8 through D17

### Dollar Amount (`amount.py`)

**Rules:**
- Optional comma grouping (groups of 3 digits after the first 1–3)
- Optional decimal point followed by exactly 2 fractional digits
- No leading zeros except for `0.XX` form
- Non-zero value required

**Symbol classes:** `ZERO`, `NONZERO`, `,`, `.`, `OTHER`

**Key states:** `START → INT_1/INT_2/INT_3 → [COMMA_D1→COMMA_D2→COMMA_D3]* → [DOT→FRAC_1→FRAC_2]`

### Date (`date.py`)

**Rule:** `MM/DD/YYYY` where month is 01–12, day is 01–31, year is 1900–2099.

**States encode partial field values** so range constraints can be enforced inline:
- Month: `M1_ZERO` (first digit 0, second must be 1–9) vs `M1_ONE` (first digit 1, second must be 0–2)
- Day: `D1_ZERO`, `D1_LOW` (1 or 2), `D1_THREE` each constrain the second digit
- Year: `Y1_ONE` requires next digit `9`; `Y1_TWO` requires next digit `0`

### Memo (`memo.py`)

**Rule:** 1–40 characters from: letters, digits, spaces, and `. , : ; ' - _ / ( ) & # @ ! ?`

**State encoding:** count of valid characters consumed (`C0…C40`)
- Symbol mapper classifies each character as `VALID` or `INVALID`
- Accept states: C1–C40

## Installation

```bash
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest
# with coverage:
pytest --cov=src --cov-report=term-missing
```

## CLI Usage

### Interactive mode

```bash
python -m src.cli
```

Prompts for each field and shows a pass/fail summary.

### JSON input

```bash
# from file
python -m src.cli --json check.json

# from stdin
echo '{"routing_number": "122105155", "amount": "1,234.56", "date": "06/08/2026"}' \
  | python -m src.cli --json -
```

### Single-field shortcuts

```bash
python -m src.cli --routing 122105155
python -m src.cli --account 123456789012
python -m src.cli --amount "1,234.56"
python -m src.cli --date 06/08/2026
python -m src.cli --memo "Rent for June"
```

### Example JSON file

```json
{
  "routing_number": "021000021",
  "account_number": "123456789",
  "amount": "1,500.00",
  "date": "06/08/2026",
  "memo": "Rent - June 2026"
}
```

## Python API

```python
from src.check_processor import CheckProcessor

processor = CheckProcessor()

result = processor.validate(
    routing_number="021000021",
    account_number="123456789",
    amount="1,500.00",
    date="06/08/2026",
    memo="Rent - June 2026",
)

if result.valid:
    print("Check is valid")
else:
    for error in result.errors:
        print(f"  {error}")

# Or from a dict
result = processor.validate_from_dict({
    "routing_number": "021000021",
    "amount": "500.00",
})
```

Each validator also has a standalone function:

```python
from src.dfa.validators.routing_number import validate_routing_number
from src.dfa.validators.amount import validate_amount

r = validate_routing_number("021000021")
print(r.accepted)      # True
print(r.final_state)   # _State(position=9, checksum=0)

r = validate_amount("bad")
print(r.accepted)      # False
print(r.error_message) # "Invalid dollar amount format"
```

## Design Principles

1. **No regex** — every validator is a true DFA with explicit states and a transition table.
2. **Meaningful state names** — states are named enums or constants (e.g. `INT_3`, `COMMA_D1`, `FRAC_2`) not arbitrary integers.
3. **Generic engine** — `DFA` in `engine.py` is a reusable 5-tuple implementation; validators only define their states and transitions.
4. **Fail-fast** — once the reject (sink) state is entered it is never left; the engine short-circuits for performance.
5. **Transparent results** — `DFAResult` carries the final state, error message, and position for diagnostics.
