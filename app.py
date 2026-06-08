"""
Flask web interface for the DFA Bank Check Validator.
"""

from __future__ import annotations

from flask import Flask, render_template, request, jsonify

from src.check_processor import CheckProcessor

app = Flask(__name__)
processor = CheckProcessor()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/validate", methods=["POST"])
def validate():
    data = request.get_json(force=True, silent=True) or {}

    result = processor.validate_from_dict(data)

    response: dict = {}
    fields = ["routing_number", "account_number", "amount", "date", "memo"]
    for field_name in fields:
        if field_name in result.fields:
            fr = result.fields[field_name]
            response[field_name] = {
                "valid": fr.valid,
                "message": fr.error_message if not fr.valid else "Valid",
            }
        else:
            # Field was not provided — treat as not validated
            response[field_name] = {
                "valid": None,
                "message": "Not provided",
            }

    return jsonify(response)


if __name__ == "__main__":
    app.run(debug=True)
