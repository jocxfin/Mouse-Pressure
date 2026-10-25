"""Named pressure profiles and application assignments."""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from mouse_pressure.bridge.config import RuntimeConfig
from mouse_pressure.runtime.config_store import (
    runtime_config_from_dict,
    runtime_config_to_dict,
)

_PROFILE_FIELDS = (
    "linked",
    "left_enabled",
    "right_enabled",
    "suppress_lmb",
    "suppress_rmb",
    "left",
    "right",
)
_NAME_MAX = 64
_EXECUTABLE = re.compile(r"[a-z0-9_ .+()\-]{1,100}\.exe", re.IGNORECASE)


def application_names(text: str) -> tuple[str, ...]:
    names: list[str] = []
    for item in text.split(","):
        item = item.strip().lower()
        if not item:
            continue
        if "/" in item or "\\" in item or not _EXECUTABLE.fullmatch(item):
            raise ValueError("Use executable names such as Photoshop.exe or Krita.exe")
        if item not in names:
            names.append(item)
    return tuple(names)


def mapping_snapshot(config: RuntimeConfig) -> dict[str, Any]:
    full = runtime_config_to_dict(config)
    subset = {name: full[name] for name in _PROFILE_FIELDS}
    for channel in ("left", "right"):
        subset[channel] = dict(subset[channel])
        subset[channel].pop("actuation_level", None)
    return subset


def validated_mapping(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict) or not set(data).issubset(_PROFILE_FIELDS):
        raise ValueError("Invalid profile settings")
    if not {"left", "right"}.issubset(data):
        raise ValueError("Profile must include both button mappings")
    config = runtime_config_from_dict({"schema_version": 2, **data})
    return mapping_snapshot(config)


@dataclass(frozen=True)
class PressureProfile:
    id: str
    name: str
    applications: tuple[str, ...]
    mapping: dict[str, Any]


class ProfileLibrary:
    def __init__(self, config_dir: str | Path) -> None:
        self.path = Path(config_dir) / "profiles.json"
        self.profiles: list[PressureProfile] = []
        self.selected_id = ""
        self.auto_switch = False

    @staticmethod
    def _check_name(name: str) -> str:
        value = str(name).strip()
        if not value or len(value) > _NAME_MAX:
            raise ValueError("Profile names must be between 1 and 64 characters")
        return value

    def load(self, config: RuntimeConfig) -> None:
        if not self.path.exists():
            default = PressureProfile(
                "default", "Default", (), mapping_snapshot(config)
            )
            self.profiles = [default]
            self.selected_id = default.id
            self.save()
            return

        document = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(document, dict) or document.get("version") != 1:
            raise ValueError("Unsupported profile library version")
        items = document.get("profiles")
        if not isinstance(items, list) or not items:
            raise ValueError("Profile library is empty")
        parsed = []
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("Invalid profile")
            names = application_names(",".join(item.get("applications", [])))
            parsed.append(
                PressureProfile(
                    id=str(item["id"]),
                    name=self._check_name(item["name"]),
                    applications=names,
                    mapping=validated_mapping(item["mapping"]),
                )
            )
        ids = [p.id for p in parsed]
        if any(not item for item in ids) or len(ids) != len(set(ids)):
            raise ValueError("Duplicate profile identifiers")
        assigned = [exe for profile in parsed for exe in profile.applications]
        if len(assigned) != len(set(assigned)):
            raise ValueError("An application is assigned to more than one profile")
        self.profiles = parsed
        selected = document.get("selected_id")
        self.selected_id = selected if selected in ids else ids[0]
        self.auto_switch = document.get("auto_switch", False) is True

    def save(self) -> None:
        payload = {
            "version": 1,
            "selected_id": self.selected_id,
            "auto_switch": self.auto_switch,
            "profiles": [asdict(profile) for profile in self.profiles],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        target = self.path.with_suffix(".json.tmp")
        with target.open("w", encoding="utf-8") as output:
            json.dump(payload, output, ensure_ascii=False, indent=2, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(target, self.path)

    def get(self, profile_id: str) -> PressureProfile:
        for item in self.profiles:
            if item.id == profile_id:
                return item
        raise KeyError(f"Profile not found: {profile_id}")

    def _replace(self, updated: PressureProfile) -> None:
        self.profiles = [
            updated if entry.id == updated.id else entry for entry in self.profiles
        ]
        self.save()

    def create(self, name: str, config: RuntimeConfig) -> PressureProfile:
        name = self._check_name(name)
        if any(entry.name.casefold() == name.casefold() for entry in self.profiles):
            raise ValueError("That profile name is already in use")
        created = PressureProfile(
            uuid.uuid4().hex, name, (), mapping_snapshot(config)
        )
        self.profiles.append(created)
        self.selected_id = created.id
        self.save()
        return created

    def update(self, profile_id: str, config: RuntimeConfig) -> PressureProfile:
        updated = replace(self.get(profile_id), mapping=mapping_snapshot(config))
        self._replace(updated)
        return updated

    def rename(self, profile_id: str, name: str) -> None:
        name = self._check_name(name)
        if any(
            entry.id != profile_id and entry.name.casefold() == name.casefold()
            for entry in self.profiles
        ):
            raise ValueError("That profile name is already in use")
        self._replace(replace(self.get(profile_id), name=name))

    def assign(self, profile_id: str, names: str) -> None:
        applications = application_names(names)
        for other in self.profiles:
            if other.id == profile_id:
                continue
            collision = set(applications) & set(other.applications)
            if collision:
                raise ValueError(
                    f"{', '.join(sorted(collision))} is assigned to {other.name}"
                )
        self._replace(replace(self.get(profile_id), applications=applications))

    def remove(self, profile_id: str) -> None:
        if len(self.profiles) <= 1:
            raise ValueError("At least one profile must remain")
        self.get(profile_id)
        self.profiles = [p for p in self.profiles if p.id != profile_id]
        if self.selected_id == profile_id:
            self.selected_id = self.profiles[0].id
        self.save()

    def select(self, profile_id: str) -> None:
        self.get(profile_id)
        self.selected_id = profile_id
        self.save()

    def match(self, executable: str) -> str | None:
        executable = executable.strip().lower()
        for profile in self.profiles:
            if executable in profile.applications:
                return profile.id
        return None

    def export_profile(self, profile_id: str, path: str | Path) -> None:
        profile = self.get(profile_id)
        document = {
            "kind": "mouse-pressure-profile",
            "version": 1,
            "name": profile.name,
            "applications": profile.applications,
            "mapping": profile.mapping,
        }
        Path(path).write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def import_profile(self, path: str | Path) -> PressureProfile:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
        if (
            not isinstance(document, dict)
            or document.get("kind") != "mouse-pressure-profile"
            or document.get("version") != 1
        ):
            raise ValueError("Not a Mouse Pressure profile")
        validated_mapping(document.get("mapping"))
        name = self._check_name(document.get("name", "Imported"))
        proposed = name
        index = 2
        while any(p.name.casefold() == proposed.casefold() for p in self.profiles):
            proposed = f"{name[:54]} ({index})"
            index += 1
        # Imported application assignments are opt-in to avoid conflicting rules.
        created = PressureProfile(
            uuid.uuid4().hex, proposed, (), validated_mapping(document["mapping"])
        )
        self.profiles.append(created)
        self.selected_id = created.id
        self.save()
        return created
