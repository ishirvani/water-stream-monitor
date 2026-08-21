import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import (
    OUTPUT_DIR,
    CLEAN_FILE,
    BAD_FILE,
    REPORT_FILE,
)


CLEAN_COLUMNS = [
    "reading_id",
    "station_id",
    "model_name",
    "predicted_label",
    "confidence_score",
    "response_time_ms",
    "timestamp",
]


BAD_COLUMNS = [
    "received_at",
    "raw_record",
    "errors",
]


REPORT_COLUMNS = [
    "report_timestamp",
    "total_records",
    "clean_records",
    "bad_records",
    "low_confidence_count",
    "active_stations",

    "leak_detector_avg_confidence",
    "leak_detector_avg_response_time_ms",

    "pressure_drop_predictor_avg_confidence",
    "pressure_drop_predictor_avg_response_time_ms",

    "demand_forecaster_avg_confidence",
    "demand_forecaster_avg_response_time_ms",
]


class CsvStorage:

    def __init__(self) -> None:

        OUTPUT_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._ensure_file(
            CLEAN_FILE,
            CLEAN_COLUMNS,
        )

        self._ensure_file(
            BAD_FILE,
            BAD_COLUMNS,
        )

        self._ensure_file(
            REPORT_FILE,
            REPORT_COLUMNS,
        )

    @staticmethod
    def _ensure_file(
        file_path: Path,
        columns: list[str],
    ) -> None:

        if (
            file_path.exists()
            and file_path.stat().st_size > 0
        ):
            return

        with file_path.open(
            mode="w",
            encoding="utf-8",
            newline="",
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=columns,
            )

            writer.writeheader()

    @staticmethod
    def _append_row(
        file_path: Path,
        columns: list[str],
        row: dict,
    ) -> None:

        with file_path.open(
            mode="a",
            encoding="utf-8",
            newline="",
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=columns,
            )

            writer.writerow(row)

    def save_clean(
        self,
        record: dict,
    ) -> None:

        row = {
            column: record.get(column)
            for column in CLEAN_COLUMNS
        }

        self._append_row(
            CLEAN_FILE,
            CLEAN_COLUMNS,
            row,
        )

    def save_bad(
        self,
        raw_record: Any,
        errors: list[str],
    ) -> None:

        if isinstance(raw_record, str):

            raw_value = raw_record

        else:

            raw_value = json.dumps(
                raw_record,
                ensure_ascii=False,
            )

        row = {
            "received_at": datetime.now(
                timezone.utc
            ).isoformat(),

            "raw_record": raw_value,

            "errors": " | ".join(errors),
        }

        self._append_row(
            BAD_FILE,
            BAD_COLUMNS,
            row,
        )

    def save_report(
        self,
        report: dict,
    ) -> None:

        self._append_row(
            REPORT_FILE,
            REPORT_COLUMNS,
            report,
        )