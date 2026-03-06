# BuzzBridge - Air Quality Helpers
# Rev: 1.0
#
# Functions to interpret air quality data from ecobee Premium thermostats.
# The ecobee Premium has a Bosch BME680 gas sensor that measures VOCs and
# estimates CO2. Beestat normalizes the raw ecobee air quality score (0-350,
# lower=better) to a 0-100 scale (higher=better).
#
# This module maps numeric values to human-readable levels using thresholds
# defined in const.py. Each level includes a description and health guidance.

from __future__ import annotations

from typing import Any

from .const import (
    AQ_ACCURACY_LEVELS,
    AQ_SCORE_THRESHOLDS,
    CO2_THRESHOLDS,
    VOC_THRESHOLDS,
)


def get_aq_score_level(score: float | int | None) -> dict[str, str] | None:
    """Get the air quality level for a beestat-normalized AQ score (0-100).

    Higher scores = better air quality.

    Args:
        score: AQ score from 0 (worst) to 100 (best).

    Returns:
        Dict with keys: level, description, health_note, icon_color.
        None if score is unavailable.
    """
    if score is None:
        return None

    for min_score, level, description, health_note, icon_color in AQ_SCORE_THRESHOLDS:
        if score >= min_score:
            return {
                "level": level,
                "description": description,
                "health_note": health_note,
                "icon_color": icon_color,
            }

    # Should not reach here, but fallback to worst level
    _, level, description, health_note, icon_color = AQ_SCORE_THRESHOLDS[-1]
    return {
        "level": level,
        "description": description,
        "health_note": health_note,
        "icon_color": icon_color,
    }


def get_co2_level(ppm: float | int | None) -> dict[str, str] | None:
    """Get the CO2 level for a reading in parts per million.

    Fresh outdoor air is ~400 ppm. Indoor levels rise with occupancy and
    poor ventilation. EPA recommends under 1000 ppm indoors. Cognitive
    performance measurably declines above 1000 ppm. OSHA 8-hour workplace
    limit is 5000 ppm.

    Args:
        ppm: CO2 concentration in parts per million.

    Returns:
        Dict with keys: level, description, health_note.
        None if ppm is unavailable.
    """
    if ppm is None:
        return None

    for max_ppm, level, description, health_note in CO2_THRESHOLDS:
        if ppm <= max_ppm:
            return {
                "level": level,
                "description": description,
                "health_note": health_note,
            }

    _, level, description, health_note = CO2_THRESHOLDS[-1]
    return {"level": level, "description": description, "health_note": health_note}


def get_voc_level(ppb: float | int | None) -> dict[str, str] | None:
    """Get the VOC level for a reading in parts per billion.

    VOCs (Volatile Organic Compounds) include formaldehyde, benzene, toluene,
    and hundreds of others. Indoor levels are typically 2-5x outdoor (EPA).
    Sources: cleaning products, paint, new furniture, cooking, personal care.

    Args:
        ppb: VOC concentration in parts per billion.

    Returns:
        Dict with keys: level, description, health_note.
        None if ppb is unavailable.
    """
    if ppb is None:
        return None

    for max_ppb, level, description, health_note in VOC_THRESHOLDS:
        if ppb <= max_ppb:
            return {
                "level": level,
                "description": description,
                "health_note": health_note,
            }

    _, level, description, health_note = VOC_THRESHOLDS[-1]
    return {"level": level, "description": description, "health_note": health_note}


def get_aq_accuracy_label(accuracy: int | None) -> tuple[str, str] | None:
    """Get the human-readable accuracy label for the BME680 sensor.

    The gas sensor needs time after power-on to calibrate. Accuracy improves
    as the sensor builds a baseline over hours to days.

    Args:
        accuracy: Calibration level 0-4 (0=warming up, 4=fully calibrated).

    Returns:
        Tuple of (label, description), or None if unavailable.
    """
    if accuracy is None:
        return None
    return AQ_ACCURACY_LEVELS.get(
        accuracy, ("Unknown", f"Unrecognized accuracy level: {accuracy}")
    )
