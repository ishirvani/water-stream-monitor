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


class WaterStreamClient:

    def __init__(self) -> None:

        self.storage = CsvStorage()
        self.statistics = StreamStatistics()

        # شمارنده کلی از ابتدای اجرای برنامه
        self.total_records = 0
        self.clean_records = 0
        self.bad_records = 0

        # زمان آخرین گزارش 20 ثانیه‌ای
        self.last_report_time = time.monotonic()

    def process_line(
        self,
        raw_line: bytes,
    ) -> None:

        if not raw_line:
            return

        # -----------------------------
        # Decode bytes to UTF-8
        # -----------------------------
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

        # -----------------------------
        # Parse JSON
        # -----------------------------
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

        # -----------------------------
        # Validate record
        # -----------------------------
        errors = validate_record(record)

        if errors:

            self.bad_records += 1

            self.statistics.add_bad()

            self.storage.save_bad(
                record,
                errors,
            )

            return

        # -----------------------------
        # Clean record
        # -----------------------------
        self.clean_records += 1

        self.statistics.add_clean(record)

        self.storage.save_clean(record)

    def print_status(self) -> None:

        print(
            f"\r"
            f"Total: {self.total_records} | "
            f"Clean: {self.clean_records} | "
            f"Bad: {self.bad_records}",
            end="",
            flush=True,
        )

    def write_periodic_report(self) -> None:

        now = time.monotonic()

        elapsed = (
            now - self.last_report_time
        )

        if elapsed < REPORT_INTERVAL_SECONDS:
            return

        # ساخت گزارش برای همین پنجره 20 ثانیه
        report = (
            self.statistics.build_report()
        )

        # ذخیره در CSV
        self.storage.save_report(
            report
        )

        # نمایش در ترمینال
        print("\n")
        print("=" * 50)
        print("20 SECOND REAL-TIME REPORT")
        print("=" * 50)

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

        print("DEMAND FORECASTER")

        print(
            f"  Avg Confidence   : "
            f"{report['demand_forecaster_avg_confidence']}"
        )

        print(
            f"  Avg Response Time: "
            f"{report['demand_forecaster_avg_response_time_ms']} ms"
        )

        print("=" * 50)
        print()

        # شروع پنجره 20 ثانیه‌ای بعدی
        self.statistics.reset()

        self.last_report_time = now

    def run(self) -> None:

        buffer = b""

        print(
            f"Connecting to {HOST}:{PORT} ..."
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

            print("Connected successfully.")
            print("Receiving stream...")
            print("Press Ctrl+C to stop.\n")

            while True:

                try:

                    chunk = sock.recv(
                        SOCKET_BUFFER_SIZE
                    )

                except socket.timeout:

                    # حتی در timeout هم زمان گزارش را بررسی کن
                    self.write_periodic_report()

                    continue

                if not chunk:

                    print(
                        "\nServer closed the connection."
                    )

                    break

                # TCP stream buffer
                buffer += chunk

                # استخراج تمام رکوردهای کامل
                while b"\n" in buffer:

                    line, buffer = buffer.split(
                        b"\n",
                        1,
                    )

                    self.process_line(
                        line
                    )

                    self.print_status()

                # مهم:
                # بعد از پردازش chunk بررسی کن
                # آیا 20 ثانیه گذشته یا نه
                self.write_periodic_report()

        # داده ناقص باقی‌مانده
        if buffer.strip():

            self.total_records += 1
            self.bad_records += 1

            self.statistics.add_bad()

            self.storage.save_bad(
                repr(buffer),
                [
                    "connection closed with incomplete record"
                ],
            )