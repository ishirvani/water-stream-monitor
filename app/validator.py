from datetime import datetime
from typing import Any

from app.config import VALID_MODELS, VALID_STATIONS


REQUIRED_FIELDS = {
    "reading_id",
    "station_id",
    "model_name",
    "predicted_label",
    "confidence_score",
    "response_time_ms",
    "timestamp",
}


def is_number(value: Any) -> bool:
    """
    Returns True only for int/float values.
    Boolean values are rejected because bool is a subclass of int in Python.
    """
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def is_valid_timestamp(value: Any) -> bool:
    """
    Validate ISO-like timestamps.
    Supports timestamps ending with Z as UTC.
    """

    if not isinstance(value, str):
        return False

    try:
        datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
        return True

    except ValueError:
        return False


def validate_predicted_label(
    model_name: Any,
    predicted_label: Any,
) -> list[str]:

    errors = []

    if model_name == "leak_detector":

        if predicted_label not in {
            "leak",
            "normal",
        }:
            errors.append(
                "predicted_label must be 'leak' or 'normal' "
                "for leak_detector"
            )

    elif model_name == "pressure_drop_predictor":

        if predicted_label not in {
            "drop",
            "stable",
        }:
            errors.append(
                "predicted_label must be 'drop' or 'stable' "
                "for pressure_drop_predictor"
            )

    elif model_name == "demand_forecaster":

        if (
            isinstance(predicted_label, bool)
            or not isinstance(predicted_label, int)
        ):
            errors.append(
                "predicted_label must be an integer "
                "for demand_forecaster"
            )

        elif not 1 <= predicted_label <= 5000:
            errors.append(
                "predicted_label must be between 1 and 5000 "
                "for demand_forecaster"
            )

    return errors


def validate_record(record: Any) -> list[str]:
    """
    Validate one stream record.

    Returns:
        []             -> valid record
        [error, ...]   -> invalid record
    """

    errors = []

    if not isinstance(record, dict):
        return ["record must be a JSON object"]

    #
    # Required fields
    #
    missing_fields = (
        REQUIRED_FIELDS - record.keys()
    )

    for field in sorted(missing_fields):
        errors.append(
            f"missing required field: {field}"
        )

    #
    # reading_id
    #
    if "reading_id" in record:

        reading_id = record["reading_id"]

        if (
            isinstance(reading_id, bool)
            or not isinstance(reading_id, int)
            or reading_id <= 0
        ):
            errors.append(
                "reading_id must be a positive integer"
            )

    #
    # station_id
    #
    if "station_id" in record:

        station_id = record["station_id"]

        if station_id not in VALID_STATIONS:
            errors.append(
                "station_id must be between ST-01 and ST-10"
            )

    #
    # model_name
    #
    if "model_name" in record:

        model_name = record["model_name"]

        if model_name not in VALID_MODELS:
            errors.append(
                "invalid model_name"
            )

    #
    # confidence_score
    #
    if "confidence_score" in record:

        confidence_score = record[
            "confidence_score"
        ]

        if not is_number(confidence_score):

            errors.append(
                "confidence_score must be numeric"
            )

        elif not 0 <= confidence_score <= 1:

            errors.append(
                "confidence_score must be between 0 and 1"
            )

    #
    # response_time_ms
    #
    if "response_time_ms" in record:

        response_time = record[
            "response_time_ms"
        ]

        if not is_number(response_time):

            errors.append(
                "response_time_ms must be numeric"
            )

        elif response_time <= 0:

            errors.append(
                "response_time_ms must be greater than zero"
            )

    #
    # timestamp
    #
    if "timestamp" in record:

        if not is_valid_timestamp(
            record["timestamp"]
        ):
            errors.append(
                "timestamp is invalid"
            )

    #
    # predicted_label
    #
    if (
        "model_name" in record
        and "predicted_label" in record
        and record["model_name"] in VALID_MODELS
    ):

        errors.extend(
            validate_predicted_label(
                record["model_name"],
                record["predicted_label"],
            )
        )

    return errors