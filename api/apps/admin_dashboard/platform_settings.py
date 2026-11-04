"""Explicitly bounded settings; absent SLA targets do not imply a deadline."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SettingDefinition:
    description: str
    minimum: int
    maximum: int


SLA_SETTINGS = {
    f"tickets.{priority.lower()}_response_minutes": SettingDefinition(
        f"{priority} support response target in minutes; unset until decided.", 1, 525600
    )
    for priority in ("P0", "P1", "P2", "P3")
}


def validate_setting(key: str, value: object) -> bool:
    definition = SLA_SETTINGS.get(key)
    return bool(definition and (value is None or (
        type(value) is int and definition.minimum <= value <= definition.maximum
    )))
