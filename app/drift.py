import time
from collections import defaultdict, deque
from datetime import datetime, timezone

from app.config import (
    BASELINE_WINDOW_SECONDS,
    CURRENT_WINDOW_SECONDS,
    CONFIDENCE_DROP_THRESHOLD,
    RESPONSE_TIME_INCREASE_THRESHOLD,
    LEAK_RATE_INCREASE_THRESHOLD,
    MIN_DRIFT_SAMPLES,
    DRIFT_REQUIRED_CONSECUTIVE_WINDOWS,
    DRIFT_ALERT_COOLDOWN_SECONDS,
)


class DriftDetector:

    def __init__(self) -> None:

        self.started_at = time.monotonic()

        # Samples collected during the initial baseline period.
        self.baseline_samples = defaultdict(list)

        # Frozen baseline statistics for each model.
        self.baselines = {}

        # Rolling samples after baseline.
        self.current_samples = defaultdict(deque)

        # Used to avoid alerting because of one temporary fluctuation.
        self.consecutive_drift = defaultdict(int)

        # Used to avoid repeating the same alert too frequently.
        self.last_alert_time = defaultdict(float)

    def add_record(self, record: dict) -> None:

        now = time.monotonic()

        model_name = record["model_name"]

        sample = {
            "time": now,
            "confidence": float(
                record["confidence_score"]
            ),
            "response_time": float(
                record["response_time_ms"]
            ),
            "predicted_label": record[
                "predicted_label"
            ],
        }

        elapsed = (
            now - self.started_at
        )

        # --------------------------------
        # Baseline phase
        # --------------------------------

        if elapsed <= BASELINE_WINDOW_SECONDS:

            self.baseline_samples[
                model_name
            ].append(sample)

            return

        # --------------------------------
        # Freeze baseline
        # --------------------------------

        if model_name not in self.baselines:

            samples = self.baseline_samples[
                model_name
            ]

            if len(samples) >= MIN_DRIFT_SAMPLES:

                self.baselines[
                    model_name
                ] = self._calculate_metrics(
                    model_name,
                    samples,
                )

        # --------------------------------
        # Add to rolling current window
        # --------------------------------

        queue = self.current_samples[
            model_name
        ]

        queue.append(sample)

        cutoff = (
            now - CURRENT_WINDOW_SECONDS
        )

        while (
            queue
            and queue[0]["time"] < cutoff
        ):
            queue.popleft()

    def _calculate_metrics(
        self,
        model_name: str,
        samples,
    ) -> dict:

        count = len(samples)

        avg_confidence = (
            sum(
                sample["confidence"]
                for sample in samples
            )
            / count
        )

        avg_response_time = (
            sum(
                sample["response_time"]
                for sample in samples
            )
            / count
        )

        metrics = {
            "sample_count": count,
            "avg_confidence":
                avg_confidence,
            "avg_response_time":
                avg_response_time,
            "leak_rate": None,
        }

        if model_name == "leak_detector":

            leak_count = sum(
                1
                for sample in samples
                if sample[
                    "predicted_label"
                ] == "leak"
            )

            metrics["leak_rate"] = (
                leak_count / count
            )

        return metrics

    def check(self) -> list[dict]:

        alerts = []

        now = time.monotonic()

        for (
            model_name,
            samples,
        ) in self.current_samples.items():

            if model_name not in self.baselines:
                continue

            if len(samples) < MIN_DRIFT_SAMPLES:
                continue

            # Do not compare a very short current window.
            window_duration = (
                now - samples[0]["time"]
            )

            if window_duration < 40:
                continue

            baseline = self.baselines[
                model_name
            ]

            current = self._calculate_metrics(
                model_name,
                samples,
            )

            confidence_change = 0.0
            response_change = 0.0

            if baseline[
                "avg_confidence"
            ] > 0:

                confidence_change = (
                    current[
                        "avg_confidence"
                    ]
                    - baseline[
                        "avg_confidence"
                    ]
                ) / baseline[
                    "avg_confidence"
                ]

            if baseline[
                "avg_response_time"
            ] > 0:

                response_change = (
                    current[
                        "avg_response_time"
                    ]
                    - baseline[
                        "avg_response_time"
                    ]
                ) / baseline[
                    "avg_response_time"
                ]

            reasons = []

            # --------------------------------
            # Confidence Drift
            # --------------------------------

            if (
                confidence_change
                <= -CONFIDENCE_DROP_THRESHOLD
            ):

                reasons.append(
                    "average confidence decreased"
                )

            # --------------------------------
            # Response-time Drift
            # --------------------------------

            if (
                response_change
                >= RESPONSE_TIME_INCREASE_THRESHOLD
            ):

                reasons.append(
                    "average response time increased"
                )

            # --------------------------------
            # Label distribution Drift
            # Only relevant for leak_detector
            # --------------------------------

            leak_rate_change = None

            if (
                model_name == "leak_detector"
                and baseline[
                    "leak_rate"
                ] is not None
                and current[
                    "leak_rate"
                ] is not None
            ):

                leak_rate_change = (
                    current["leak_rate"]
                    - baseline["leak_rate"]
                )

                if (
                    leak_rate_change
                    >= LEAK_RATE_INCREASE_THRESHOLD
                ):

                    reasons.append(
                        "leak prediction rate increased"
                    )

            # --------------------------------
            # Consecutive checks
            # --------------------------------

            if reasons:

                self.consecutive_drift[
                    model_name
                ] += 1

            else:

                self.consecutive_drift[
                    model_name
                ] = 0

            if (
                self.consecutive_drift[
                    model_name
                ]
                < DRIFT_REQUIRED_CONSECUTIVE_WINDOWS
            ):
                continue

            # --------------------------------
            # Alert cooldown
            # --------------------------------

            time_since_last_alert = (
                now
                - self.last_alert_time[
                    model_name
                ]
            )

            if (
                time_since_last_alert
                < DRIFT_ALERT_COOLDOWN_SECONDS
            ):
                continue

            alert = {
                "alert_timestamp":
                    datetime.now(
                        timezone.utc
                    ).isoformat(),

                "model_name":
                    model_name,

                "baseline_avg_confidence":
                    round(
                        baseline[
                            "avg_confidence"
                        ],
                        4,
                    ),

                "current_avg_confidence":
                    round(
                        current[
                            "avg_confidence"
                        ],
                        4,
                    ),

                "confidence_change_percent":
                    round(
                        confidence_change
                        * 100,
                        2,
                    ),

                "baseline_avg_response_time_ms":
                    round(
                        baseline[
                            "avg_response_time"
                        ],
                        4,
                    ),

                "current_avg_response_time_ms":
                    round(
                        current[
                            "avg_response_time"
                        ],
                        4,
                    ),

                "response_time_change_percent":
                    round(
                        response_change
                        * 100,
                        2,
                    ),

                "baseline_leak_rate":
                    (
                        round(
                            baseline[
                                "leak_rate"
                            ],
                            4,
                        )
                        if baseline[
                            "leak_rate"
                        ] is not None
                        else None
                    ),

                "current_leak_rate":
                    (
                        round(
                            current[
                                "leak_rate"
                            ],
                            4,
                        )
                        if current[
                            "leak_rate"
                        ] is not None
                        else None
                    ),

                "reason":
                    " | ".join(reasons),
            }

            alerts.append(alert)

            self.last_alert_time[
                model_name
            ] = now

        return alerts