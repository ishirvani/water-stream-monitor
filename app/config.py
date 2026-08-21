from pathlib import Path
HOST = "127.0.0.1"
PORT = 9034

SOCKET_BUFFER_SIZE = 4096
SOCKET_TIMEOUT_SECONDS = 1

REPORT_INTERVAL_SECONDS = 20

VALID_STATIONS = {
    "ST-01",
    "ST-02",
    "ST-03",
    "ST-04",
    "ST-05",
    "ST-06",
    "ST-07",
    "ST-08",
    "ST-09",
    "ST-10",
}

VALID_MODELS = {
    "leak_detector",
    "pressure_drop_predictor",
    "demand_forecaster",
}
OUTPUT_DIR = Path("output")

CLEAN_FILE = OUTPUT_DIR / "clean_readings.csv"
BAD_FILE = OUTPUT_DIR / "bad_readings.csv"
REPORT_FILE = OUTPUT_DIR / "real_time_reports.csv"