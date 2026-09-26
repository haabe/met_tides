"""Synthetic MET forecast generator shared by tests."""

import math
import random
from datetime import datetime, timedelta

# Semidiurnal tide: M2 period is ~12h25m
M2_PERIOD = timedelta(hours=12, minutes=25)


def make_forecast(
    start: datetime,
    hours: int = 48,
    step_minutes: int = 10,
    amplitude: float = 1.0,
    phase: float = 0.0,
    noise: float = 0.0,
    seed: int = 0,
) -> str:
    """Build a MET-style forecast body with a sinusoidal TOTAL column.

    ``noise`` adds seeded uniform jitter (metres), mimicking weather surge.
    """
    rng = random.Random(seed)
    lines = [
        "MET - PROGNOSER",
        "",
        "VANNSTANDSVARSEL --- MET STORMFLO ---",
        "",
        f"SIST OPPDATERT: {start:%Y%m%d %H:%M} UTC",
        "==========================================",
        "TESTHAVN",
        "------------------------------",
        " AAR MND DAG TIM MIN  SURGE  TIDE   TOTAL  0p     25p    50p    75p    100p",
    ]
    for i in range(hours * 60 // step_minutes + 1):
        t = start + timedelta(minutes=i * step_minutes)
        tide = amplitude * math.sin(2 * math.pi * (t - start) / M2_PERIOD + phase)
        tide += rng.uniform(-noise, noise)
        lines.append(
            f" {t.year} {t.month:2d} {t.day:2d} {t.hour:2d} {t.minute:2d}"
            f"    0.00  {tide:7.3f} {tide:7.3f}  0.0  0.0  0.0  0.0  0.0"
        )
    return "\n".join(lines)
