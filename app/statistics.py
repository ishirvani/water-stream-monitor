from collections import defaultdict
from datetime import datetime, timezone


MODELS = (
    "leak_detector",
    "pressure_drop_predictor",
    "demand_forecaster",
)


class StreamStatistics:

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:

        self.total_records = 0
        self.clean_records = 0
        self.bad_records = 0

        self.low_confidence_count = 0

        self.active_stations = set()

        self.model_count = defaultdict(int)
        self.confidence_sum = defaultdict(float)
        self.response_time_sum = defaultdict(float)

    def add_bad(self) -> None:

        self.total_records += 1
        self.bad_records += 1

    def add_clean(self, record: dict) -> None:

        self.total_records += 1
        self.clean_records += 1

        model_name = record["model_name"]

        confidence = float(
            record["confidence_score"]
        )

        response_time = float(
            record["response_time_ms"]
        )

        self.model_count[model_name] += 1

        self.confidence_sum[
            model_name
        ] += confidence

        self.response_time_sum[
            model_name
        ] += response_time

        self.active_stations.add(
            record["station_id"]
        )

        if confidence < 0.5:
            self.low_confidence_count += 1

    def average(
        self,
        values,
        model_name: str,
    ):

        count = self.model_count[
            model_name
        ]

        if count == 0:
            return None

        return round(
            values[model_name] / count,
            4,
        )

    def build_report(self) -> dict:

        report = {
            "report_timestamp": datetime.now(
                timezone.utc
            ).isoformat(),

            "total_records":
                self.total_records,

            "clean_records":
                self.clean_records,

            "bad_records":
                self.bad_records,

            "low_confidence_count":
                self.low_confidence_count,

            "active_stations":
                len(self.active_stations),
        }

        for model_name in MODELS:

            report[
                f"{model_name}_avg_confidence"
            ] = self.average(
                self.confidence_sum,
                model_name,
            )

            report[
                f"{model_name}_avg_response_time_ms"
            ] = self.average(
                self.response_time_sum,
                model_name,
            )

        return report