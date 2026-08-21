import json
import socket

from app.config import (
    HOST,
    PORT,
    SOCKET_BUFFER_SIZE,
    SOCKET_TIMEOUT_SECONDS,
)

from app.storage import CsvStorage
from app.validator import validate_record


class WaterStreamClient:

    def __init__(self) -> None:
        self.storage = CsvStorage()

        self.total_records = 0
        self.clean_records = 0
        self.bad_records = 0

    def process_line(self, raw_line: bytes) -> None:

        if not raw_line:
            return

        try:
            line = raw_line.decode("utf-8").strip()

        except UnicodeDecodeError as exc:

            self.total_records += 1
            self.bad_records += 1

            self.storage.save_bad(
                repr(raw_line),
                [f"invalid UTF-8: {exc}"],
            )

            return

        if not line:
            return

        try:
            record = json.loads(line)

        except json.JSONDecodeError as exc:

            self.total_records += 1
            self.bad_records += 1

            self.storage.save_bad(
                line,
                [f"invalid JSON: {exc.msg}"],
            )

            return

        self.total_records += 1

        errors = validate_record(record)

        if errors:

            self.bad_records += 1

            self.storage.save_bad(
                record,
                errors,
            )

            return

        self.clean_records += 1

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

    def run(self) -> None:

        buffer = b""

        print(f"Connecting to {HOST}:{PORT} ...")

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
                    continue

                if not chunk:

                    print(
                        "\nServer closed the connection."
                    )

                    break

                buffer += chunk

                while b"\n" in buffer:

                    line, buffer = buffer.split(
                        b"\n",
                        1,
                    )

                    self.process_line(line)

                    self.print_status()

        if buffer.strip():

            self.total_records += 1
            self.bad_records += 1

            self.storage.save_bad(
                repr(buffer),
                [
                    "connection closed with incomplete record"
                ],
            )