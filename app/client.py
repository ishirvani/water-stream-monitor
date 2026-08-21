import json
import socket
import time

from app.config import (
    HOST,
    PORT,
    SOCKET_BUFFER_SIZE,
    SOCKET_TIMEOUT_SECONDS,
    REPORT_INTERVAL_SECONDS,
)

from app.storage import CsvStorage
from app.validator import validate_record
from app.statistics import StreamStatistics
from app.drift import DriftDetector


class WaterStreamClient:

    def __init__(self) -> None:

        self.storage = CsvStorage()
        self.statistics = StreamStatistics()
        self.drift_detector = DriftDetector()

        # Global counters from application start
        self.total_records = 0
        self.clean_records = 0
        self.bad_records = 0

        # Last 20-second report time
        self.last_report_time = time.monotonic()

    def process_line(
        self,
        raw_line: bytes,
    ) -> None:

        if not raw_line:
            return

        # --------------------------------------------------
        # Decode bytes -> UTF-8 string
        # --------------------------------------------------

        try:

            line = raw_line.decode(
                "utf-8"
            ).strip()

        except UnicodeDecodeError as exc:

            self.total_records += 1
            self.bad_records += 1

            self.statistics.add_bad()

            self.storage.save_bad(
                repr(raw_line),
                [
                    f"invalid UTF-8: {exc}"
                ],
            )

            return

        if not line:
            return

        # --------------------------------------------------
        # Parse JSON
        # --------------------------------------------------

        try:

            record = json.loads(line)

        except json.JSONDecodeError as exc:

            self.total_records += 1
            self.bad_records += 1

            self.statistics.add_bad()

            self.storage.save_bad(
                line,
                [
                    f"invalid JSON: {exc.msg}"
                ],
            )

            return

        self.total_records += 1

        # --------------------------------------------------
        # Validate record
        # --------------------------------------------------

        errors = validate_record(record)

        if errors:

            self.bad_records += 1

            self.statistics.add_bad()

            self.storage.save_bad(
                record,
                errors,
            )

            return

        # --------------------------------------------------
        # Clean record
        # --------------------------------------------------

        self.clean_records += 1

        self.statistics.add_clean(
            record
        )

        self.storage.save_clean(
            record
        )

        # --------------------------------------------------
        # Send clean record to Drift Detector
        # --------------------------------------------------

        self.drift_detector.add_record(
            record
        )

    def print_status(self) -> None:

        print(
            f"\r"
            f"Total: {self.total_records} | "
            f"Clean: {self.clean_records} | "
            f"Bad: {self.bad_records}",
            end="",
            flush=True,
        )

    def check_drift(self) -> None:

        alerts = (
            self.drift_detector.check()
        )

        for alert in alerts:

            self.storage.save_drift_alert(
                alert
            )

            print()
            print()
            print("!" * 60)
            print("MODEL DRIFT DETECTED")
            print("!" * 60)

            print(
                f"Model                  : "
                f"{alert['model_name']}"
            )

            print(
                f"Reason                 : "
                f"{alert['reason']}"
            )

            print()

            print(
                f"Baseline Confidence    : "
                f"{alert['baseline_avg_confidence']}"
            )

            print(
                f"Current Confidence     : "
                f"{alert['current_avg_confidence']}"
            )

            print(
                f"Confidence Change      : "
                f"{alert['confidence_change_percent']}%"
            )

            print()

            print(
                f"Baseline Response Time : "
                f"{alert['baseline_avg_response_time_ms']} ms"
            )

            print(
                f"Current Response Time  : "
                f"{alert['current_avg_response_time_ms']} ms"
            )

            print(
                f"Response Time Change   : "
                f"{alert['response_time_change_percent']}%"
            )

            if (
                alert["model_name"]
                == "leak_detector"
            ):

                print()

                print(
                    f"Baseline Leak Rate     : "
                    f"{alert['baseline_leak_rate']}"
                )

                print(
                    f"Current Leak Rate      : "
                    f"{alert['current_leak_rate']}"
                )

            print("!" * 60)
            print()

    def write_periodic_report(self) -> None:

        now = time.monotonic()

        elapsed = (
            now - self.last_report_time
        )

        if (
            elapsed
            < REPORT_INTERVAL_SECONDS
        ):
            return

        # --------------------------------------------------
        # Build 20-second report
        # --------------------------------------------------

        report = (
            self.statistics.build_report()
        )

        self.storage.save_report(
            report
        )

        # --------------------------------------------------
        # Print report
        # --------------------------------------------------

        print()
        print()

        print("=" * 60)
        print("20 SECOND REAL-TIME REPORT")
        print("=" * 60)

        print(
            f"Total Records      : "
            f"{report['total_records']}"
        )

        print(
            f"Clean Records      : "
            f"{report['clean_records']}"
        )

        print(
            f"Bad Records        : "
            f"{report['bad_records']}"
        )

        print(
            f"Low Confidence     : "
            f"{report['low_confidence_count']}"
        )

        print(
            f"Active Stations    : "
            f"{report['active_stations']}"
        )

        print()

        # --------------------------------------------------
        # Leak Detector
        # --------------------------------------------------

        print("LEAK DETECTOR")

        print(
            f"  Avg Confidence   : "
            f"{report['leak_detector_avg_confidence']}"
        )

        print(
            f"  Avg Response Time: "
            f"{report['leak_detector_avg_response_time_ms']} ms"
        )

        print()

        # --------------------------------------------------
        # Pressure Drop Predictor
        # --------------------------------------------------

        print("PRESSURE DROP PREDICTOR")

        print(
            f"  Avg Confidence   : "
            f"{report['pressure_drop_predictor_avg_confidence']}"
        )

        print(
            f"  Avg Response Time: "
            f"{report['pressure_drop_predictor_avg_response_time_ms']} ms"
        )

        print()

        # --------------------------------------------------
        # Demand Forecaster
        # --------------------------------------------------

        print("DEMAND FORECASTER")

        print(
            f"  Avg Confidence   : "
            f"{report['demand_forecaster_avg_confidence']}"
        )

        print(
            f"  Avg Response Time: "
            f"{report['demand_forecaster_avg_response_time_ms']} ms"
        )

        print("=" * 60)

        # --------------------------------------------------
        # Check model drift
        # --------------------------------------------------

        self.check_drift()

        # --------------------------------------------------
        # Start new 20-second reporting window
        # --------------------------------------------------

        self.statistics.reset()

        self.last_report_time = now

    def run(self) -> None:

        buffer = b""

        print(
            f"Connecting to "
            f"{HOST}:{PORT} ..."
        )

        with socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM,
        ) as sock:

            sock.settimeout(
                SOCKET_TIMEOUT_SECONDS
            )

            sock.connect(
                (HOST, PORT)
            )

            print(
                "Connected successfully."
            )

            print(
                "Receiving stream..."
            )

            print(
                "Press Ctrl+C to stop.\n"
            )

            while True:

                try:

                    chunk = sock.recv(
                        SOCKET_BUFFER_SIZE
                    )

                except socket.timeout:

                    self.write_periodic_report()

                    continue

                if not chunk:

                    print(
                        "\nServer closed "
                        "the connection."
                    )

                    break

                # --------------------------------------------------
                # TCP stream buffer
                # --------------------------------------------------

                buffer += chunk

                # --------------------------------------------------
                # Process complete JSON lines only
                # --------------------------------------------------

                while b"\n" in buffer:

                    line, buffer = (
                        buffer.split(
                            b"\n",
                            1,
                        )
                    )

                    self.process_line(
                        line
                    )

                    self.print_status()

                # --------------------------------------------------
                # Periodic report + drift check
                # --------------------------------------------------

                self.write_periodic_report()

        # --------------------------------------------------
        # Remaining incomplete TCP data
        # --------------------------------------------------

        if buffer.strip():

            self.total_records += 1
            self.bad_records += 1

            self.statistics.add_bad()

            self.storage.save_bad(
                repr(buffer),
                [
                    "connection closed "
                    "with incomplete record"
                ],
            )