#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Local Web console for ComfyUI prompt batch generation.

Run:
    python app.py

Then open:
    http://127.0.0.1:7860

ComfyUI should already be running at:
    http://127.0.0.1:8188
"""

from __future__ import annotations

import base64
import copy
from functools import lru_cache
import json
import re
import secrets
import sys
import threading
import time
import uuid
import webbrowser
import random
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from itertools import product
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urljoin, urlparse
from urllib.request import Request, urlopen


BASE_DIR = Path(__file__).resolve().parent
LIBRARY_PATH = BASE_DIR / "prompt_library.json"
CONFIG_PATH = BASE_DIR / "app_config.json"
LAST_API_PROMPT_PATH = BASE_DIR / "last_api_prompt.json"

LEGACY_CLIP_NAMES: set[str] = set()
NODE_INPUT_HINTS = {
    ("901", "unet_name"): "This workflow uses UNETLoader. Model files must be placed in ComfyUI/models/diffusion_models.",
    ("902", "clip_name"): "Text encoders must be placed in ComfyUI/models/text_encoders or ComfyUI/models/clip.",
    ("903", "vae_name"): "VAE files must be placed in ComfyUI/models/vae.",
}

HOST = "127.0.0.1"
PORT = 7860

POSITIVE_NODE = "609"
NEGATIVE_NODE = "610"
KSAMPLER_NODE = "50"
LATENT_NODE = "40"
SAVE_NODE = "220"
UNET_NODE = "901"
CLIP_NODE = "902"
VAE_NODE = "903"
PROMPT_SECTIONS = ["characters", "outfits", "objects", "actions", "angles", "backgrounds"]
RUN_LOG_LIMIT = 200
JSON_RESPONSE_SEPARATORS = (",", ":")
WHITESPACE_RE = re.compile(r"\s+")
SAFE_NAME_INVALID_RE = re.compile(r"[^A-Za-z0-9_.-]+")
SAFE_NAME_UNDERSCORE_RE = re.compile(r"_+")
NUMBER_KEY_RE = re.compile(r"(\d+)([A-Z]?)")
DEFAULT_ACTION_KEY = "smile"
ACTION_GROUP_TAG_BY_SORT_GROUP = {
    0: "SFW Emotion / Action",
    1: "SFW Emotion / Action",
    2: "SFW Emotion / Action",
    3: "NSFW Display / Invitation",
    4: "NSFW Solo / Toys",
    5: "NSFW Oral Interaction",
    6: "NSFW Hands / Feet / Breast Interaction",
    7: "NSFW Lying Positions",
    8: "NSFW Riding / Seated",
    9: "NSFW Standing / Lifted",
    10: "NSFW Side-Lying / Supported",
}
ACTION_GROUP_KEY_BY_SORT_GROUP = {
    0: "sfw_emotion_action",
    1: "sfw_emotion_action",
    2: "sfw_emotion_action",
    3: "nsfw_display_invitation",
    4: "nsfw_solo_toys",
    5: "nsfw_oral_interaction",
    6: "nsfw_hands_feet_breast",
    7: "nsfw_lying_positions",
    8: "nsfw_riding_seated",
    9: "nsfw_standing_lifted",
    10: "nsfw_side_supported",
}
DEFAULT_GROUP_BY_SECTION = {
    "characters": ("default", "Characters"),
    "outfits": ("default", "Outfits"),
    "objects": ("equipment", "Equipment / Props"),
    "actions": ("sfw_emotion_action", "SFW Emotion / Action"),
    "angles": ("default", "View"),
    "backgrounds": ("default", "Background"),
}

VIEW_DISPLAY_NAMES = {
    "no_view_blank": "No view specified",
    "three_quarter_headshot": "Three-quarter body (head to knees)",
    "half_headshot": "Half portrait (face and upper shoulders)",
    "close_up_portrait": "Close-up face",
    "bust_portrait": "Bust portrait (head to chest)",
    "waist_up_portrait": "Half body (head to waist)",
    "full_body_portrait": "Full body (head to toe)",
}

API_TEMPLATE: dict[str, dict[str, Any]] = {
    "40": {
        "class_type": "EmptySD3LatentImage",
        "inputs": {
            "width": 0,
            "height": 0,
            "batch_size": 1,
        },
    },
    "50": {
        "class_type": "KSampler",
        "inputs": {
            "model": ["901", 0],
            "positive": ["609", 0],
            "negative": ["610", 0],
            "latent_image": ["40", 0],
            "seed": 0,
            "steps": 0,
            "cfg": 0,
            "sampler_name": "",
            "scheduler": "",
            "denoise": 0,
        },
    },
    "220": {
        "class_type": "SaveImage",
        "inputs": {
            "images": ["611", 0],
            "filename_prefix": "",
        },
    },
    "609": {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "clip": ["902", 0],
            "text": "POSITIVE_PROMPT_PLACEHOLDER",
        },
    },
    "610": {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "clip": ["902", 0],
            "text": "",
        },
    },
    "611": {
        "class_type": "VAEDecode",
        "inputs": {
            "samples": ["50", 0],
            "vae": ["903", 0],
        },
    },
    "901": {
        "class_type": "UNETLoader",
        "inputs": {
            "unet_name": "",
            "weight_dtype": "default",
        },
    },
    "902": {
        "class_type": "CLIPLoader",
        "inputs": {
            "clip_name": "",
            "type": "qwen_image",
            "device": "default",
        },
    },
    "903": {
        "class_type": "VAELoader",
        "inputs": {
            "vae_name": "",
        },
    },
}


class ComfyUIRequestError(RuntimeError):
    """Raised when ComfyUI rejects an HTTP request."""

STATE_LOCK = threading.Lock()
RUN_STATE: dict[str, Any] = {
    "running": False,
    "stop_requested": False,
    "current": 0,
    "total": 0,
    "started_at": None,
    "finished_at": None,
    "last_prompt_id": "",
    "last_error": "",
    "status_message": "",
    "last_outputs": [],
    "last_duration": 0.0,
    "average_duration": 0.0,
    "logs": [],
}


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: Any) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def truncate_text(value: str, limit: int = 600) -> str:
    value = WHITESPACE_RE.sub(" ", value).strip()
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def explain_known_comfy_error(message: str) -> str:
    text = str(message or "")
    if (
        "Error(s) in loading state_dict" in text
        and "Llama2" in text
        and "size mismatch" in text
    ):
        return (
            "ComfyUI text encoder is incompatible with the selected workflow. "
            "The current prompt uses CLIPLoader with the configured clip_name/clip_type, "
            "but the safetensors weights have a different architecture. "
            "Use the matching Qwen Image text encoder for clip_type=qwen_image, "
            "or switch the workflow/model preset to the architecture that this text encoder was made for."
        )
    if "UnicodeDecodeError" in text and "utf-8" in text:
        return (
            "ComfyUI emitted non-UTF-8 text while starting a custom node. "
            "This usually comes from a Windows console encoding mismatch and is not the generation failure by itself."
        )
    return ""


def parse_json_text(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def format_comfy_error(endpoint: str, status: int, reason: str, raw: str) -> str:
    data = parse_json_text(raw)
    details: list[str] = []
    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, dict):
            message = error.get("message") or error.get("type")
            if message:
                details.append(str(message))
            if error.get("details"):
                details.append(str(error["details"]))
        elif error:
            details.append(str(error))

        node_errors = data.get("node_errors")
        if isinstance(node_errors, dict):
            for node_id, node_error in node_errors.items():
                if not isinstance(node_error, dict):
                    continue
                class_type = node_error.get("class_type", "")
                prefix = f"node {node_id}"
                if class_type:
                    prefix += f" {class_type}"
                errors = node_error.get("errors", [])
                if isinstance(errors, list) and errors:
                    for item in errors:
                        if not isinstance(item, dict):
                            continue
                        message = item.get("message") or item.get("type") or "invalid input"
                        item_details = item.get("details")
                        if item_details:
                            details.append(f"{prefix}: {message}: {item_details}")
                        else:
                            details.append(f"{prefix}: {message}")
                else:
                    details.append(prefix)
    elif raw:
        details.append(raw)

    summary = "; ".join(truncate_text(part, 500) for part in details if str(part).strip())
    if not summary:
        summary = reason or "Bad Request"
    summary = explain_known_comfy_error(summary) or summary
    return f"ComfyUI {endpoint} returned HTTP {status}: {truncate_text(summary, 1200)}"


def post_json(base_url: str, endpoint: str, payload: dict, timeout: float = 30.0) -> dict:
    url = urljoin(base_url.rstrip("/") + "/", endpoint.lstrip("/"))
    data = json.dumps(payload).encode("utf-8")
    request = Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise ComfyUIRequestError(format_comfy_error(endpoint, exc.code, exc.reason, raw)) from exc


def get_json(base_url: str, endpoint: str, timeout: float = 10.0) -> Any:
    url = urljoin(base_url.rstrip("/") + "/", endpoint.lstrip("/"))
    try:
        with urlopen(url, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise ComfyUIRequestError(format_comfy_error(endpoint, exc.code, exc.reason, raw)) from exc


def safe_name(value: str) -> str:
    value = value.strip().replace(" ", "_")
    value = SAFE_NAME_INVALID_RE.sub("_", value)
    value = SAFE_NAME_UNDERSCORE_RE.sub("_", value).strip("_")
    return value or "item"


def compact_lines(*parts: str) -> str:
    lines: list[str] = []
    for part in parts:
        if not part:
            continue
        for line in str(part).splitlines():
            line = line.strip()
            if line:
                lines.append(line)
    return "\n".join(lines)


@lru_cache(maxsize=1024)
def random_prompt_choice_tuple(value: str) -> tuple[str, ...]:
    return tuple(line.strip() for line in value.splitlines() if line.strip())


def random_prompt_choices(value: str) -> list[str]:
    return list(random_prompt_choice_tuple(str(value or "")))


def choose_random_prompt_from_choices(choices: tuple[str, ...], rng: random.Random) -> tuple[str, int, int]:
    if not choices:
        return "", 0, 0
    index = rng.randrange(len(choices))
    return choices[index], index + 1, len(choices)


def choose_random_prompt(value: str, rng: random.Random) -> tuple[str, int, int]:
    return choose_random_prompt_from_choices(random_prompt_choice_tuple(str(value or "")), rng)


def number_key(value: str | None) -> tuple[int, str]:
    if not value:
        return (9999, "")
    match = NUMBER_KEY_RE.match(str(value))
    if not match:
        return (9999, str(value))
    return (int(match.group(1)), match.group(2))


def group_sort_index(library: dict | None, section: str, group_key: str) -> int:
    if not library or not section:
        return 9999
    group = library.get("groups", {}).get(section, {}).get(group_key, {})
    try:
        return int(group.get("sort_index", 9999))
    except (TypeError, ValueError):
        return 9999


def record_group_key(section: str, record: dict) -> str:
    if isinstance(record, dict):
        group_key = record.get("group") or record.get("group_key")
        if group_key:
            return safe_name(str(group_key))
    return default_group_for_section(section)[0]


def ordered_keys(records: dict, section: str = "", library: dict | None = None) -> list[str]:
    return [
        key
        for key, _record in sorted(
            records.items(),
            key=lambda item: (
                group_sort_index(library, section, record_group_key(section, item[1])),
                item[1].get("sort_index", 9999),
                number_key(item[1].get("number")),
                item[1].get("source_node", 999999),
                item[0],
            ),
        )
    ]


def label_for(record: dict, key: str) -> str:
    if not isinstance(record, dict):
        return key
    return record.get("name") or record.get("display_name") or record.get("zh_name") or key


def normalized_record_name(record: dict, key: str) -> str:
    raw = record.get("name") or record.get("zh_name") or record.get("display_name") or key
    name = str(raw).strip()
    if " / " in name:
        name = name.split(" / ", 1)[0].strip()
    return name or key


def default_loras() -> list[dict]:
    return [
        {
            "enabled": False,
            "lora_name": "",
            "strength_model": "",
            "strength_clip": "",
            "positive_prompt": "",
            "negative_prompt": "",
        }
        for _ in range(5)
    ]


def default_model_settings() -> dict:
    return {
        "unet_name": "",
        "unet_weight_dtype": "default",
        "clip_name": "",
        "clip_type": "qwen_image",
        "clip_device": "default",
        "vae_name": "",
        "width": "",
        "height": "",
        "batch_size": 1,
        "steps": "",
        "cfg": "",
        "sampler_name": "",
        "scheduler": "",
        "denoise": "",
        "seed": "",
        "seed_mode": "",
        "loras": default_loras(),
        "upscale": {
            "enabled": False,
            "model_name": "",
            "scale_by": "",
            "method": "lanczos",
        },
    }


def default_single_image_settings() -> dict:
    return {
        "source_mode": "previous",
        "use_global_positive": False,
        "use_global_negative": False,
        "use_action_random_prompt": False,
        "action_random_index": 1,
        "use_action_custom_prompt": False,
        "character": "",
        "outfit": "",
        "action": "",
        "angle": "",
        "background": "",
        "object": "",
    }


def first_available_key(records: dict, fallback: str) -> str:
    if isinstance(records, dict) and records:
        return ordered_keys(records)[0]
    return fallback


def valid_default_keys(records: dict, preferred: list[str], fallback: str) -> list[str]:
    if not isinstance(records, dict):
        return [fallback]
    keys = [key for key in preferred if key in records]
    if keys:
        return keys
    fallback_key = first_available_key(records, fallback)
    return [fallback_key] if fallback_key else []


def default_loop_settings(library: dict | None = None) -> dict:
    library = library or {}
    batch_defaults = library.get("batch_defaults", {}) if isinstance(library.get("batch_defaults"), dict) else {}
    defaults = library.get("defaults", {}) if isinstance(library.get("defaults"), dict) else {}
    characters = valid_default_keys(library.get("characters", {}), batch_defaults.get("characters", []), "")
    outfits = valid_default_keys(library.get("outfits", {}), batch_defaults.get("outfits", []), "")
    actions = valid_default_keys(library.get("actions", {}), batch_defaults.get("actions", []), "")
    angle = defaults.get("angle") if defaults.get("angle") in library.get("angles", {}) else first_available_key(library.get("angles", {}), "")
    background = (
        defaults.get("background")
        if defaults.get("background") in library.get("backgrounds", {})
        else first_available_key(library.get("backgrounds", {}), "")
    )
    return {
        "characters": characters,
        "outfits": outfits,
        "objects": [],
        "actions": actions,
        "angle": angle,
        "background": background,
        "use_global_positive": False,
        "use_global_negative": False,
        "use_custom_prompt": False,
        "include_random": bool(defaults.get("include_random_prompt", False)),
        "random_prompt_mode": "random",
    }


def default_loop_presets(library: dict | None = None) -> list[dict]:
    return [
        {"name": f"Preset {idx}", "settings": default_loop_settings(library)}
        for idx in range(1, 5)
    ]


def default_config() -> dict:
    return {
        "schema_version": "web-1.0",
        "comfy_url": "http://127.0.0.1:8188",
        "active_model_preset": 0,
        "active_loop_preset": 0,
        "model_presets": [
            {"name": f"Preset {idx}", "settings": default_model_settings()}
            for idx in range(1, 5)
        ],
        "single_image": default_single_image_settings(),
        "run": {
            "repeat_count": 1,
            "start_index": 1,
            "limit": 0,
            "save_prompts_json": True,
            "prompts_file": "prompts.json",
        },
    }


def merge_missing(base: Any, incoming: Any) -> Any:
    if isinstance(base, dict) and isinstance(incoming, dict):
        result = dict(incoming)
        for key, value in base.items():
            result[key] = merge_missing(value, result[key]) if key in result else value
        return result
    if isinstance(base, list) and isinstance(incoming, list):
        if all(not isinstance(item, (dict, list)) for item in base + incoming):
            return list(incoming)
        result = []
        for index, incoming_item in enumerate(incoming):
            if index < len(base):
                result.append(merge_missing(base[index], incoming_item))
            else:
                result.append(incoming_item)
        if len(result) < len(base):
            result.extend(copy.deepcopy(base[len(result) :]))
        return result
    return incoming


def load_config(*, write_back: bool = True, strip_loop_presets: bool = True) -> dict:
    base = default_config()
    if CONFIG_PATH.exists():
        try:
            config = merge_missing(base, read_json(CONFIG_PATH))
        except json.JSONDecodeError:
            config = base
    else:
        config = base
    migrate_config(config)
    if strip_loop_presets:
        config.pop("loop_presets", None)
    if write_back:
        write_json(CONFIG_PATH, config)
    return config


def migrate_config(config: dict) -> None:
    single = config.setdefault("single_image", default_single_image_settings())
    if not isinstance(single, dict):
        config["single_image"] = default_single_image_settings()
        single = config["single_image"]
    single.setdefault("source_mode", "previous")
    if single.get("source_mode") not in {"fixed", "previous"}:
        single["source_mode"] = "previous"
    single.pop("positive_prompt", None)
    single.pop("negative_prompt", None)
    single.pop("filename_prefix", None)
    single.setdefault("use_global_positive", False)
    single.setdefault("use_global_negative", False)
    single.setdefault("use_action_random_prompt", False)
    single.setdefault("action_random_index", 1)
    single.setdefault("use_action_custom_prompt", False)
    try:
        single["action_random_index"] = max(1, int(single.get("action_random_index", 1)))
    except (TypeError, ValueError):
        single["action_random_index"] = 1
    single.setdefault("character", "")
    single.setdefault("outfit", "")
    single.setdefault("action", "")
    single.setdefault("angle", "")
    single.setdefault("background", "")
    single.setdefault("object", "")
    run = config.setdefault("run", {})
    run["limit"] = 0
    for preset in config.get("model_presets", []):
        settings = preset.get("settings", {})
        settings.setdefault("scheduler", "normal")
        # Do not auto-remap a valid selected text encoder. Older builds
        # rewrote the qwen text encoder to a model-specific legacy CLIP file,
        # which caused deleted CLIP files to be restored during config load/save
        # and blocked ComfyUI submission.
        loras = settings.get("loras")
        if not isinstance(loras, list):
            settings["loras"] = default_loras()
            loras = settings["loras"]
        for lora in loras:
            if not isinstance(lora, dict):
                continue
            lora.setdefault("positive_prompt", "")
            lora.setdefault("negative_prompt", "")


def clamp_index(value: Any, length: int) -> int:
    if length <= 0:
        return 0
    try:
        index = int(value)
    except (TypeError, ValueError):
        index = 0
    return max(0, min(length - 1, index))


def merge_identity_into_global_positive(library: dict) -> dict:
    defaults = library.get("defaults", {})
    identity = str(defaults.get("identity_consistency", "") or "").strip()
    if identity:
        global_positive = str(defaults.get("global_positive", "") or "")
        if identity not in global_positive:
            defaults["global_positive"] = compact_lines(global_positive, identity)
        defaults["identity_consistency"] = ""
    return library


def normalize_group_label(value: str) -> str:
    return str(value or "").replace("\u6210\u4eba", "NSFW").strip()


def sort_group_int(record: dict) -> int:
    try:
        return int(record.get("sort_group", 9999))
    except (TypeError, ValueError):
        return 9999


def default_group_for_section(section: str) -> tuple[str, str]:
    return DEFAULT_GROUP_BY_SECTION.get(section, ("default", "Uncategorized"))


def legacy_group_key_for_record(section: str, record: dict) -> str:
    if record.get("group"):
        return safe_name(str(record["group"]))
    if record.get("group_key"):
        return safe_name(str(record["group_key"]))
    if section == "actions":
        sort_group = sort_group_int(record)
        if sort_group in ACTION_GROUP_KEY_BY_SORT_GROUP:
            return ACTION_GROUP_KEY_BY_SORT_GROUP[sort_group]
    return default_group_for_section(section)[0]


def legacy_group_label_for_record(section: str, record: dict) -> str:
    if record.get("group_tag"):
        return normalize_group_label(str(record["group_tag"]))
    if section == "actions":
        return ACTION_GROUP_TAG_BY_SORT_GROUP.get(sort_group_int(record), "Other")
    return default_group_for_section(section)[1]


def normalize_section_groups(raw_groups: Any) -> dict:
    normalized: dict[str, dict[str, Any]] = {}
    if isinstance(raw_groups, dict):
        iterable = raw_groups.items()
    elif isinstance(raw_groups, list):
        iterable = ((item.get("key") or item.get("group"), item) for item in raw_groups if isinstance(item, dict))
    else:
        iterable = []
    for index, (key, record) in enumerate(iterable, start=1):
        if not isinstance(record, dict):
            record = {"name": str(record)}
        group_key = safe_name(str(record.get("key") or key or f"group_{index}"))
        display_name = normalize_group_label(record.get("name") or record.get("display_name") or group_key)
        normalized[group_key] = {
            "name": display_name,
            "sort_index": int(record.get("sort_index", index) or index),
        }
    return normalized


def ensure_library_sections(library: dict) -> dict:
    for section in PROMPT_SECTIONS:
        if section not in library or not isinstance(library.get(section), dict):
            library[section] = {}
    return library


def canonicalize_record(section: str, key: str, record: Any) -> dict:
    if not isinstance(record, dict):
        record = {"prompt": str(record)}
    record["name"] = normalized_record_name(record, key)
    record["group"] = legacy_group_key_for_record(section, record)
    record.setdefault("negative_prompt", "")
    for legacy_key in [
        "key",
        "zh_name",
        "display_name",
        "group_key",
        "group_tag",
        "sort_group",
        "sort_category",
    ]:
        record.pop(legacy_key, None)
    return record


def ensure_library_groups(library: dict) -> dict:
    raw_groups = library.get("groups") if isinstance(library.get("groups"), dict) else {}
    groups: dict[str, dict[str, dict[str, Any]]] = {}
    for section in PROMPT_SECTIONS:
        section_groups = normalize_section_groups(raw_groups.get(section) if isinstance(raw_groups, dict) else {})
        for key, record in list(library.get(section, {}).items()):
            group_label = legacy_group_label_for_record(section, record if isinstance(record, dict) else {})
            record = canonicalize_record(section, key, record)
            library[section][key] = record
            group_key = record["group"]
            if group_key not in section_groups:
                section_groups[group_key] = {
                    "name": group_label,
                    "sort_index": len(section_groups) + 1,
                }
        if not section_groups:
            group_key, group_label = default_group_for_section(section)
            section_groups[group_key] = {"name": group_label, "sort_index": 1}
        groups[section] = dict(
            sorted(
                section_groups.items(),
                key=lambda item: (int(item[1].get("sort_index", 9999) or 9999), item[0]),
            )
        )
    library["groups"] = groups
    return library


def repair_view_records(library: dict) -> dict:
    angles = library.get("angles", {})
    if isinstance(angles, dict):
        for key, display_name in VIEW_DISPLAY_NAMES.items():
            record = angles.get(key)
            if isinstance(record, dict):
                record["name"] = display_name
                record["group"] = record.get("group") or "default"
    groups = library.setdefault("groups", {})
    angle_groups = groups.setdefault("angles", {})
    default_group = angle_groups.setdefault("default", {"sort_index": 1})
    default_group["name"] = "View"
    return library


def normalize_loop_settings(settings: dict, library: dict) -> dict:
    defaults = default_loop_settings(library)
    for section in ["characters", "outfits", "actions"]:
        records = library.get(section, {})
        selected = settings.get(section, [])
        if not isinstance(selected, list):
            selected = []
        valid = [key for key in selected if key in records]
        settings[section] = valid or defaults[section]

    object_records = library.get("objects", {})
    selected_objects = settings.get("objects", [])
    if not isinstance(selected_objects, list):
        selected_objects = []
    settings["objects"] = [key for key in selected_objects if key in object_records]

    if settings.get("angle") not in library.get("angles", {}):
        settings["angle"] = defaults["angle"]
    if settings.get("background") not in library.get("backgrounds", {}):
        settings["background"] = defaults["background"]
    if settings.get("random_prompt_mode") not in {"random", "all"}:
        settings["random_prompt_mode"] = "random"

    for key in ["use_global_positive", "use_global_negative", "use_custom_prompt", "include_random"]:
        if key not in settings:
            settings[key] = defaults[key]
        else:
            settings[key] = bool(settings[key])
    settings.pop("use_identity", None)
    return settings


def normalize_loop_presets(library: dict) -> dict:
    presets = library.get("loop_presets")
    if not isinstance(presets, list) or not presets:
        return library
    normalized = []
    for index, preset in enumerate(presets, start=1):
        if not isinstance(preset, dict):
            preset = {}
        settings = preset.get("settings", {})
        if not isinstance(settings, dict):
            settings = {}
        normalized.append(
            {
                "name": str(preset.get("name") or f"Preset {index}"),
                "settings": normalize_loop_settings(settings, library),
            }
        )
    library["loop_presets"] = normalized
    return library


def prune_library_config_defaults(library: dict) -> dict:
    defaults = library.get("defaults")
    if isinstance(defaults, dict):
        for key in ["image", "sampler", "models"]:
            defaults.pop(key, None)
    return library


def prune_legacy_reference_layers(library: dict) -> dict:
    for key in ["categories", "angle_names_from_original_selector", "background_names_from_original_selector"]:
        library.pop(key, None)
    return library


def normalize_library(library: dict) -> dict:
    library["schema_version"] = "2.0-single-source"
    library = ensure_library_sections(library)
    library = merge_identity_into_global_positive(library)
    library = ensure_library_groups(library)
    library = repair_view_records(library)
    library = normalize_loop_presets(library)
    library = prune_library_config_defaults(library)
    return prune_legacy_reference_layers(library)


def load_library() -> dict:
    return normalize_library(read_json(LIBRARY_PATH))


def migrate_state_ownership(config: dict, library: dict) -> tuple[bool, bool]:
    config_changed = False
    library_changed = False
    legacy_loop_names = config.pop("loop_preset_names", None)
    if legacy_loop_names is not None:
        config_changed = True
    legacy_loop_presets = config.pop("loop_presets", None)
    if legacy_loop_presets is not None:
        config_changed = True
        if not library.get("loop_presets"):
            library["loop_presets"] = legacy_loop_presets
            library_changed = True

    if not library.get("loop_presets"):
        library["loop_presets"] = default_loop_presets(library)
        library_changed = True

    if isinstance(legacy_loop_names, list):
        for index, name in enumerate(legacy_loop_names):
            if index < len(library.get("loop_presets", [])) and name:
                preset = library["loop_presets"][index]
                if preset.get("name") != str(name):
                    preset["name"] = str(name)
                    library_changed = True

    before_library = copy.deepcopy(library)
    normalize_library(library)
    if library != before_library:
        library_changed = True

    model_index = clamp_index(config.get("active_model_preset", 0), len(config.get("model_presets", [])))
    loop_index = clamp_index(config.get("active_loop_preset", 0), len(library.get("loop_presets", [])))
    if config.get("active_model_preset") != model_index:
        config["active_model_preset"] = model_index
        config_changed = True
    if config.get("active_loop_preset") != loop_index:
        config["active_loop_preset"] = loop_index
        config_changed = True
    return config_changed, library_changed


def load_state() -> tuple[dict, dict]:
    raw_config = read_json(CONFIG_PATH) if CONFIG_PATH.exists() else {}
    config = load_config(write_back=False, strip_loop_presets=False)
    raw_library = read_json(LIBRARY_PATH)
    library = normalize_library(copy.deepcopy(raw_library))
    config_changed, library_changed = migrate_state_ownership(config, library)
    config_changed = config_changed or config != raw_config
    library_changed = library_changed or library != raw_library
    if config_changed:
        write_json(CONFIG_PATH, config)
    if library_changed:
        write_json(LIBRARY_PATH, library)
    return config, library


def active_presets(config: dict, library: dict) -> tuple[dict, dict]:
    model_index = clamp_index(config.get("active_model_preset", 0), len(config.get("model_presets", [])))
    loop_index = clamp_index(config.get("active_loop_preset", 0), len(library.get("loop_presets", [])))
    loop_preset = copy.deepcopy(library["loop_presets"][loop_index])
    return config["model_presets"][model_index], loop_preset


MODEL_SETTINGS_OVERRIDE_KEYS = {
    "unet_name",
    "unet_weight_dtype",
    "clip_name",
    "clip_type",
    "clip_device",
    "vae_name",
    "width",
    "height",
    "steps",
    "cfg",
    "sampler_name",
    "scheduler",
    "denoise",
    "seed",
    "seed_mode",
    "loras",
    "upscale",
}


def apply_model_settings_override(config: dict, request_data: dict | None) -> bool:
    if not isinstance(request_data, dict):
        return False
    override = request_data.get("model_override")
    if not isinstance(override, dict):
        return False
    presets = config.get("model_presets")
    if not isinstance(presets, list) or not presets:
        return False
    index = clamp_index(override.get("active_model_preset", config.get("active_model_preset", 0)), len(presets))
    settings_override = override.get("settings")
    if not isinstance(settings_override, dict):
        return False
    config["active_model_preset"] = index
    preset = presets[index]
    if not isinstance(preset, dict):
        return False
    settings = preset.setdefault("settings", {})
    if not isinstance(settings, dict):
        preset["settings"] = {}
        settings = preset["settings"]
    changed = False
    for key in MODEL_SETTINGS_OVERRIDE_KEYS:
        if key in settings_override:
            value = copy.deepcopy(settings_override[key])
            if settings.get(key) != value:
                settings[key] = value
                changed = True
    before = copy.deepcopy(config)
    migrate_config(config)
    return changed or config != before


def build_prompt_payload(library: dict, config: dict) -> dict:
    model_preset, loop_preset = active_presets(config, library)
    model = model_preset["settings"]
    loop = loop_preset["settings"]
    defaults = library.get("defaults", {})
    run = config["run"]

    selected_characters = set(loop["characters"])
    selected_outfits = set(loop["outfits"])
    selected_actions = set(loop["actions"])
    characters = [key for key in ordered_keys(library["characters"], "characters", library) if key in selected_characters]
    outfits = [key for key in ordered_keys(library["outfits"], "outfits", library) if key in selected_outfits]
    selected_object_keys = set(loop.get("objects", []))
    objects = [key for key in ordered_keys(library.get("objects", {}), "objects", library) if key in selected_object_keys]
    object_records = [library.get("objects", {})[key] for key in objects]
    object_prompt = compact_lines(*(record.get("prompt", "") for record in object_records))
    object_negative = compact_lines(*(record.get("negative_prompt", "") for record in object_records))
    object_display = ", ".join(label_for(record, key) for key, record in zip(objects, object_records))
    object_key = "+".join(objects)
    actions = [key for key in ordered_keys(library["actions"], "actions", library) if key in selected_actions]
    if not characters or not outfits or not actions:
        raise ValueError("Select at least 1 character, 1 outfit, and 1 emotion/action.")

    repeat_count = max(1, int(run.get("repeat_count", 1)))
    seed_base = int(model.get("seed", 100001))
    seed_mode = model.get("seed_mode", "increment")
    random_pool_seed = secrets.randbits(63)
    random_pool_rng = random.Random(random_pool_seed)
    image = {
        "width": int(model["width"]),
        "height": int(model["height"]),
        "batch_size": 1,
    }
    sampler = {
        "seed": seed_base,
        "steps": int(model["steps"]),
        "cfg": float(model["cfg"]),
        "sampler_name": model["sampler_name"],
        "scheduler": model.get("scheduler", "normal"),
        "denoise": float(model.get("denoise", 1.0)),
    }
    active_loras = [
        lora
        for lora in model.get("loras", [])
        if isinstance(lora, dict) and lora.get("enabled") and str(lora.get("lora_name") or "").strip()
    ]
    lora_positive_prompt = compact_lines(*(lora.get("positive_prompt", "") for lora in active_loras))
    lora_negative_prompt = compact_lines(*(lora.get("negative_prompt", "") for lora in active_loras))
    items: list[dict] = []
    random_prompt_mode = loop.get("random_prompt_mode", "random")
    action_random_choices = {
        action_key: random_prompt_choice_tuple(str(library["actions"][action_key].get("random_prompt", "") or ""))
        for action_key in actions
    }

    for repeat in range(1, repeat_count + 1):
        for character_key, outfit_key, action_key in product(characters, outfits, actions):
            character = library["characters"][character_key]
            outfit = library["outfits"][outfit_key]
            action = library["actions"][action_key]
            angle = library["angles"][loop["angle"]]
            background = library["backgrounds"][loop["background"]]
            custom_prompt = str(action.get("custom_prompt", "") or "") if loop.get("use_custom_prompt", False) else ""
            item_negative = compact_lines(
                character.get("negative_prompt", ""),
                outfit.get("negative_prompt", ""),
                object_negative,
                action.get("negative_prompt", ""),
                angle.get("negative_prompt", ""),
                background.get("negative_prompt", ""),
            )
            random_variants = [("", 0, 0)]
            if loop.get("include_random", True):
                choices = action_random_choices.get(action_key, ())
                if random_prompt_mode == "all" and choices:
                    random_variants = [(choice, index, len(choices)) for index, choice in enumerate(choices, 1)]
                else:
                    random_variants = [choose_random_prompt_from_choices(choices, random_pool_rng)]

            for random_prompt, random_prompt_choice, random_prompt_choices_count in random_variants:
                idx = len(items) + 1
                if seed_mode == "fixed":
                    seed = seed_base
                elif seed_mode == "random":
                    seed = secrets.randbelow(2**63)
                else:
                    seed = seed_base + idx - 1
                positive = compact_lines(
                    defaults.get("global_positive", "") if loop.get("use_global_positive", True) else "",
                    lora_positive_prompt,
                    character["prompt"],
                    outfit["prompt"],
                    object_prompt,
                    action["prompt"],
                    custom_prompt,
                    angle["prompt"],
                    random_prompt,
                    background["prompt"],
                )
                negative = compact_lines(
                    defaults.get("global_negative", "") if loop.get("use_global_negative", True) else "",
                    lora_negative_prompt,
                    item_negative,
                )
                character_display = label_for(character, character_key)
                outfit_display = label_for(outfit, outfit_key)
                action_display = label_for(action, action_key)
                filename_parts = [character_key, outfit_key, action_key]
                if random_prompt_mode == "all" and random_prompt_choices_count:
                    filename_parts.append(f"rp{random_prompt_choice:02d}")
                filename_prefix = "_".join(safe_name(part) for part in filename_parts)
                items.append(
                    {
                        "index": idx,
                        "repeat": repeat,
                        "character": character_key,
                        "outfit": outfit_key,
                        "object": object_key,
                        "objects": objects,
                        "view": loop["angle"],
                        "action": action_key,
                        "angle": loop["angle"],
                        "background": loop["background"],
                        "seed": seed,
                        "positive": positive,
                        "negative": negative,
                        "filename_prefix": filename_prefix,
                        "metadata": {
                            "character_display": character_display,
                            "outfit_display": outfit_display,
                            "object_display": object_display,
                            "action_display": action_display,
                            "view_display": label_for(angle, loop["angle"]),
                            "angle_display": label_for(angle, loop["angle"]),
                            "background_display": label_for(background, loop["background"]),
                            "model_preset": model_preset["name"],
                            "loop_preset": loop_preset["name"],
                            "random_prompt_used": bool(random_prompt),
                            "custom_prompt_used": bool(custom_prompt),
                            "random_pool_seed": random_pool_seed,
                            "random_prompt_mode": random_prompt_mode,
                            "random_prompt_choice": random_prompt_choice,
                            "random_prompt_choices_count": random_prompt_choices_count,
                        },
                    },
                )

    return {
        "schema_version": "1.0",
        "source_library": LIBRARY_PATH.name,
        "count": len(items),
        "image": image,
        "sampler": sampler,
        "model": copy.deepcopy(model),
        "items": items,
    }


def split_comfy_image_name(image_name: str) -> tuple[str, str]:
    name = str(image_name or "").strip().replace("\\", "/")
    if "/" in name:
        subfolder, filename = name.rsplit("/", 1)
        return filename, subfolder
    return name, ""


def decode_browser_image(data_url: str) -> tuple[bytes, str]:
    if not data_url:
        raise ValueError("missing image data")
    match = re.match(r"^data:([^;,]+)?(;base64)?,(.*)$", data_url, re.S)
    if not match:
        raise ValueError("unsupported image data format")
    mime = match.group(1) or "image/png"
    is_base64 = bool(match.group(2))
    payload = match.group(3) or ""
    if not is_base64:
        raise ValueError("image data must be base64")
    return base64.b64decode(payload), mime


def post_multipart(base_url: str, path: str, fields: dict[str, str], files: list[tuple[str, str, bytes, str]], timeout: int = 30) -> Any:
    boundary = "----RisuBoundary" + secrets.token_hex(16)
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        chunks.append(str(value).encode("utf-8"))
        chunks.append(b"\r\n")
    for field_name, filename, content, content_type in files:
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        disposition = f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'
        chunks.append(disposition.encode("utf-8"))
        chunks.append(f"Content-Type: {content_type or 'application/octet-stream'}\r\n\r\n".encode("utf-8"))
        chunks.append(content)
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(chunks)
    request = Request(
        urljoin(base_url.rstrip("/") + "/", path.lstrip("/")),
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "Content-Length": str(len(body))},
    )
    with urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw) if raw else {}


def upload_image_to_comfy(base_url: str, filename: str, content: bytes, mime: str) -> str:
    original = Path(filename or "single_input.png")
    suffix = original.suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        suffix = ".png"
    safe_stem = safe_name(original.stem) or "single_input"
    upload_name = f"single_{int(time.time())}_{secrets.token_hex(4)}_{safe_stem}{suffix}"
    result = post_multipart(
        base_url,
        "/upload/image",
        {"type": "input", "overwrite": "true"},
        [("image", upload_name, content, mime or "image/png")],
    )
    name = result.get("name") if isinstance(result, dict) else ""
    subfolder = result.get("subfolder") if isinstance(result, dict) else ""
    if name:
        return f"{subfolder}/{name}" if subfolder else str(name)
    return upload_name


def download_comfy_output_image(base_url: str, image_name: str) -> tuple[bytes, str]:
    filename, subfolder = split_comfy_image_name(image_name)
    if not filename:
        raise ValueError("missing previous image filename")
    query = urlencode({"filename": filename, "subfolder": subfolder, "type": "output"})
    request = Request(urljoin(base_url.rstrip("/") + "/", "view") + "?" + query)
    with urlopen(request, timeout=30) as response:
        return response.read(), response.headers.get("Content-Type", "image/png")


def last_generated_output_name() -> str:
    with STATE_LOCK:
        outputs = list(RUN_STATE.get("last_outputs") or [])
    return str(outputs[0]) if outputs else ""



def build_single_image_payload(config: dict, library: dict, request_data: dict | None = None) -> dict:
    request_data = request_data or {}
    model_index = clamp_index(config.get("active_model_preset", 0), len(config.get("model_presets", [])))
    model_preset = config["model_presets"][model_index]
    model = model_preset["settings"]
    single = config.setdefault("single_image", default_single_image_settings())
    for key in [
        "source_mode",
        "character",
        "outfit",
        "action",
        "angle",
        "background",
        "object",
    ]:
        if key in request_data:
            single[key] = str(request_data.get(key) or "")
    if "action_random_index" in request_data:
        try:
            single["action_random_index"] = max(1, int(request_data.get("action_random_index") or 1))
        except (TypeError, ValueError):
            single["action_random_index"] = 1
    for key in ["use_global_positive", "use_global_negative", "use_action_random_prompt", "use_action_custom_prompt"]:
        if key in request_data:
            single[key] = bool(request_data.get(key))
    if single.get("source_mode") not in {"fixed", "previous"}:
        single["source_mode"] = "previous"

    defaults = library.get("defaults", {}) if isinstance(library.get("defaults"), dict) else {}
    single["character"] = single.get("character") if single.get("character") in library.get("characters", {}) else first_available_key(library.get("characters", {}), "")
    single["outfit"] = single.get("outfit") if single.get("outfit") in library.get("outfits", {}) else first_available_key(library.get("outfits", {}), "")
    single["action"] = single.get("action") if single.get("action") in library.get("actions", {}) else first_available_key(library.get("actions", {}), DEFAULT_ACTION_KEY)
    single["angle"] = single.get("angle") if single.get("angle") in library.get("angles", {}) else first_available_key(library.get("angles", {}), "")
    single["background"] = single.get("background") if single.get("background") in library.get("backgrounds", {}) else first_available_key(library.get("backgrounds", {}), "")
    single["object"] = single.get("object") if single.get("object") in library.get("objects", {}) else ""

    # The reference image shown on the Single Tune page is for visual comparison only.
    # It must not be inserted into the ComfyUI generation graph.
    seed_base = int(model.get("seed", 100001))
    seed_mode = model.get("seed_mode", "increment")
    if seed_mode == "random":
        seed = secrets.randbelow(2**63)
    else:
        seed = seed_base
    image = {"width": int(model["width"]), "height": int(model["height"]), "batch_size": 1}
    sampler = {
        "seed": seed,
        "steps": int(model["steps"]),
        "cfg": float(model["cfg"]),
        "sampler_name": model["sampler_name"],
        "scheduler": model.get("scheduler", "normal"),
        "denoise": float(model.get("denoise", 1.0)),
    }
    active_loras = [
        lora
        for lora in model.get("loras", [])
        if isinstance(lora, dict) and lora.get("enabled") and str(lora.get("lora_name") or "").strip()
    ]
    character = library.get("characters", {}).get(single.get("character", ""), {})
    outfit = library.get("outfits", {}).get(single.get("outfit", ""), {})
    action = library.get("actions", {}).get(single.get("action", ""), {})
    angle = library.get("angles", {}).get(single.get("angle", ""), {})
    background = library.get("backgrounds", {}).get(single.get("background", ""), {})
    object_record = library.get("objects", {}).get(single.get("object", ""), {}) if single.get("object") else {}
    action_random_choices = random_prompt_choices(str(action.get("random_prompt", "") or ""))
    if action_random_choices:
        try:
            action_random_index = max(1, min(int(single.get("action_random_index", 1)), len(action_random_choices)))
        except (TypeError, ValueError):
            action_random_index = 1
        single["action_random_index"] = action_random_index
    else:
        action_random_index = 1
        single["action_random_index"] = 1
    action_random_prompt = (
        action_random_choices[action_random_index - 1]
        if single.get("use_action_random_prompt", False) and action_random_choices
        else ""
    )
    action_custom_prompt = str(action.get("custom_prompt", "") or "") if single.get("use_action_custom_prompt", False) else ""

    positive = compact_lines(
        defaults.get("global_positive", "") if single.get("use_global_positive", True) else "",
        *(lora.get("positive_prompt", "") for lora in active_loras),
        character.get("prompt", ""),
        outfit.get("prompt", ""),
        object_record.get("prompt", ""),
        action.get("prompt", ""),
        action_custom_prompt,
        angle.get("prompt", ""),
        action_random_prompt,
        background.get("prompt", ""),
    )
    negative = compact_lines(
        defaults.get("global_negative", "") if single.get("use_global_negative", True) else "",
        *(lora.get("negative_prompt", "") for lora in active_loras),
        character.get("negative_prompt", ""),
        outfit.get("negative_prompt", ""),
        object_record.get("negative_prompt", ""),
        action.get("negative_prompt", ""),
        angle.get("negative_prompt", ""),
        background.get("negative_prompt", ""),
    )
    # Keep single comparison output names aligned with the batch naming rule:
    # character_outfit_action. ComfyUI SaveImage uses the filename_prefix to
    # allocate the next available numbered file, so repeated prefixes advance the
    # output sequence instead of overwriting an existing image.
    filename_parts = [single.get("character", ""), single.get("outfit", ""), single.get("action", "")]
    filename_prefix = "_".join(safe_name(part) for part in filename_parts)
    item = {
        "index": 1,
        "repeat": 1,
        "character": single.get("character", ""),
        "outfit": single.get("outfit", ""),
        "object": single.get("object", ""),
        "objects": [single.get("object", "")] if single.get("object") else [],
        "view": single.get("angle", ""),
        "action": single.get("action", ""),
        "angle": single.get("angle", ""),
        "background": single.get("background", ""),
        "seed": seed,
        "positive": positive,
        "negative": negative,
        "filename_prefix": filename_prefix,
        "metadata": {
            "model_preset": model_preset.get("name", ""),
            "source_mode": single.get("source_mode", "previous"),
            "action_random_prompt_used": bool(action_random_prompt),
            "action_random_prompt_choice": action_random_index if action_random_prompt else 0,
            "action_random_prompt_choices_count": len(action_random_choices),
            "action_custom_prompt_used": bool(action_custom_prompt),
            },
    }
    return {
        "schema_version": "1.0-single-image",
        "mode": "single",
        "source_library": CONFIG_PATH.name,
        "count": 1,
        "image": image,
        "sampler": sampler,
        "model": copy.deepcopy(model),
        "items": [item],
    }


def add_lora_chain(prompt: dict, model_settings: dict) -> None:
    previous_model = [UNET_NODE, 0]
    previous_clip = [CLIP_NODE, 0]
    node_index = 1200
    for lora in model_settings.get("loras", []):
        name = (lora.get("lora_name") or "").strip()
        if not lora.get("enabled") or not name:
            continue
        node_id = str(node_index)
        node_index += 1
        prompt[node_id] = {
            "class_type": "LoraLoader",
            "inputs": {
                "model": previous_model,
                "clip": previous_clip,
                "lora_name": name,
                "strength_model": float(lora.get("strength_model", 0.8)),
                "strength_clip": float(lora.get("strength_clip", 0.8)),
            },
        }
        previous_model = [node_id, 0]
        previous_clip = [node_id, 1]
    prompt[KSAMPLER_NODE]["inputs"]["model"] = previous_model
    prompt[POSITIVE_NODE]["inputs"]["clip"] = previous_clip
    prompt[NEGATIVE_NODE]["inputs"]["clip"] = previous_clip


def add_upscale_chain(prompt: dict, model_settings: dict, item: dict) -> None:
    upscale = model_settings.get("upscale", {})
    model_name = (upscale.get("model_name") or "").strip()
    if not model_name:
        return
    prompt["1300"] = {
        "class_type": "UpscaleModelLoader",
        "inputs": {
            "model_name": model_name,
        },
    }
    prompt["1301"] = {
        "class_type": "ImageUpscaleWithModel",
        "inputs": {
            "upscale_model": ["1300", 0],
            "image": ["611", 0],
        },
    }
    image_link = ["1301", 0]
    scale_by = float(upscale.get("scale_by", 1.0))
    if abs(scale_by - 1.0) > 0.0001:
        prompt["1302"] = {
            "class_type": "ImageScaleBy",
            "inputs": {
                "image": image_link,
                "upscale_method": upscale.get("method", "lanczos"),
                "scale_by": scale_by,
            },
        }
        image_link = ["1302", 0]
    prompt[SAVE_NODE]["inputs"]["images"] = image_link


def patch_template(template: dict, payload: dict, item: dict) -> dict:
    prompt = copy.deepcopy(template)
    model = payload["model"]
    image = payload["image"]
    sampler = payload["sampler"]

    prompt[UNET_NODE]["inputs"]["unet_name"] = model["unet_name"]
    prompt[UNET_NODE]["inputs"]["weight_dtype"] = model.get("unet_weight_dtype", "default")
    prompt[CLIP_NODE]["inputs"]["clip_name"] = model["clip_name"]
    prompt[CLIP_NODE]["inputs"]["type"] = model.get("clip_type", "qwen_image")
    prompt[CLIP_NODE]["inputs"]["device"] = model.get("clip_device", "default")
    prompt[VAE_NODE]["inputs"]["vae_name"] = model["vae_name"]

    add_lora_chain(prompt, model)
    source_image = str(item.get("source_image") or "").strip()
    if source_image:
        prompt["30"] = {"class_type": "LoadImage", "inputs": {"image": source_image}}
        prompt["41"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["30", 0], "vae": [VAE_NODE, 0]}}
        prompt[KSAMPLER_NODE]["inputs"]["latent_image"] = ["41", 0]
    add_upscale_chain(prompt, model, item)

    prompt[POSITIVE_NODE]["inputs"]["text"] = item["positive"]
    prompt[NEGATIVE_NODE]["inputs"]["text"] = item["negative"]
    prompt[SAVE_NODE]["inputs"]["filename_prefix"] = item["filename_prefix"]
    prompt[LATENT_NODE]["inputs"]["width"] = int(image["width"])
    prompt[LATENT_NODE]["inputs"]["height"] = int(image["height"])
    prompt[LATENT_NODE]["inputs"]["batch_size"] = 1
    prompt[KSAMPLER_NODE]["inputs"]["seed"] = int(item["seed"])
    prompt[KSAMPLER_NODE]["inputs"]["steps"] = int(sampler["steps"])
    prompt[KSAMPLER_NODE]["inputs"]["cfg"] = float(sampler["cfg"])
    prompt[KSAMPLER_NODE]["inputs"]["sampler_name"] = sampler["sampler_name"]
    prompt[KSAMPLER_NODE]["inputs"]["scheduler"] = sampler["scheduler"]
    prompt[KSAMPLER_NODE]["inputs"]["denoise"] = float(sampler["denoise"])
    return prompt


def input_options(schema: Any) -> list[Any]:
    if isinstance(schema, list) and schema and isinstance(schema[0], list):
        return schema[0]
    return []


def summarize_options(options: list[Any], limit: int = 8) -> str:
    values = [str(value) for value in options[:limit]]
    if len(options) > limit:
        values.append(f"... {len(options)} total")
    return ", ".join(values) if values else "None"


def validate_prompt_with_comfy(base_url: str, prompt: dict) -> None:
    class_types = sorted(
        {
            str(node.get("class_type"))
            for node in prompt.values()
            if isinstance(node, dict) and node.get("class_type")
        }
    )
    class_info_by_type: dict[str, dict] = {}
    errors: list[str] = []

    for class_type in class_types:
        info = get_json(base_url, f"/object_info/{class_type}", timeout=10)
        class_info = info.get(class_type) if isinstance(info, dict) else None
        if not isinstance(class_info, dict):
            errors.append(f"ComfyUI could not find node type {class_type}. Confirm that the node is installed and version-compatible.")
            continue
        class_info_by_type[class_type] = class_info

    for node_id, node in prompt.items():
        if not isinstance(node, dict):
            continue
        class_type = str(node.get("class_type", ""))
        class_info = class_info_by_type.get(class_type)
        if not class_info:
            continue
        node_inputs = node.get("inputs", {})
        input_info = class_info.get("input", {}) if isinstance(class_info.get("input"), dict) else {}
        required = input_info.get("required", {}) if isinstance(input_info.get("required"), dict) else {}
        optional = input_info.get("optional", {}) if isinstance(input_info.get("optional"), dict) else {}

        for input_name in required:
            if input_name not in node_inputs:
                errors.append(f"node {node_id} {class_type}: is missing required field {input_name}.")

        for input_name, value in node_inputs.items():
            schema = required.get(input_name) or optional.get(input_name)
            options = input_options(schema)
            if not options or not isinstance(value, str):
                continue
            if value in options:
                continue
            hint = NODE_INPUT_HINTS.get((node_id, input_name), "")
            message = (
                f"node {node_id} {class_type}: {input_name}='{value}' is not in ComfyUI's valid option list."
                f"Available examples: {summarize_options(options)}."
            )
            if hint:
                message += f" {hint}"
            errors.append(message)

    if errors:
        raise ValueError("ComfyUI preflight failed: " + " ".join(errors[:8]))


def select_run_items(payload: dict, config: dict) -> list[dict]:
    if payload.get("mode") == "single":
        return list(payload.get("items", []))
    run = config["run"]
    start_index = max(1, int(run.get("start_index", 1)))
    limit = max(0, int(run.get("limit", 0)))
    selected = payload["items"][start_index - 1 :]
    return selected[:limit] if limit else selected


def append_log(message: str) -> None:
    with STATE_LOCK:
        RUN_STATE["logs"].append(f"{time.strftime('%H:%M:%S')} {message}")
        if len(RUN_STATE["logs"]) > RUN_LOG_LIMIT:
            del RUN_STATE["logs"][:-RUN_LOG_LIMIT]


def set_status_message(message: str) -> None:
    with STATE_LOCK:
        RUN_STATE["status_message"] = message


def is_stop_requested() -> bool:
    with STATE_LOCK:
        return bool(RUN_STATE["stop_requested"])


def run_state_snapshot() -> dict:
    with STATE_LOCK:
        snapshot = dict(RUN_STATE)
        snapshot["logs"] = list(RUN_STATE.get("logs", []))
        snapshot["last_outputs"] = list(RUN_STATE.get("last_outputs", []))
        return snapshot


def queued_prompt_ids(entries: Any) -> set[str]:
    prompt_ids: set[str] = set()
    if not isinstance(entries, list):
        return prompt_ids
    for entry in entries:
        if isinstance(entry, (list, tuple)) and len(entry) > 1:
            prompt_ids.add(str(entry[1]))
        elif isinstance(entry, dict):
            for key in ["prompt_id", "id"]:
                if entry.get(key):
                    prompt_ids.add(str(entry[key]))
            extra_data = entry.get("extra_data")
            if isinstance(extra_data, dict) and extra_data.get("prompt_id"):
                prompt_ids.add(str(extra_data["prompt_id"]))
    return prompt_ids


def describe_comfy_queue(queue: Any, prompt_id: str) -> str:
    if not isinstance(queue, dict):
        return "Waiting for ComfyUI history"
    running = queue.get("queue_running", [])
    pending = queue.get("queue_pending", [])
    running_count = len(running) if isinstance(running, list) else 0
    pending_count = len(pending) if isinstance(pending, list) else 0
    if prompt_id in queued_prompt_ids(running):
        return f"ComfyUI running prompt ({pending_count} pending)"
    if prompt_id in queued_prompt_ids(pending):
        return f"ComfyUI queued prompt ({running_count} running, {pending_count} pending)"
    return f"Waiting for ComfyUI history ({running_count} running, {pending_count} pending)"


def history_error_details(history: dict) -> str:
    status = history.get("status", {}) if isinstance(history, dict) else {}
    messages = status.get("messages", []) if isinstance(status, dict) else []
    details: list[str] = []
    if isinstance(messages, list):
        for message in messages:
            if not (isinstance(message, (list, tuple)) and len(message) >= 2):
                continue
            event, data = message[0], message[1]
            if event != "execution_error" or not isinstance(data, dict):
                continue
            node_id = data.get("node_id") or data.get("node")
            node_type = data.get("node_type") or data.get("class_type")
            exception_message = data.get("exception_message") or data.get("exception_type")
            part = "ComfyUI execution error"
            if node_id or node_type:
                part += f" at node {node_id or '?'} {node_type or ''}".rstrip()
            if exception_message:
                friendly_message = explain_known_comfy_error(str(exception_message))
                part += f": {friendly_message or exception_message}"
            details.append(part)
    return "; ".join(details)


def saved_image_names(history: dict) -> list[str]:
    outputs = history.get("outputs", {}) if isinstance(history, dict) else {}
    names: list[str] = []
    if not isinstance(outputs, dict):
        return names
    for output in outputs.values():
        if not isinstance(output, dict):
            continue
        for image in output.get("images", []) or []:
            if not isinstance(image, dict):
                continue
            filename = image.get("filename")
            if not filename:
                continue
            subfolder = image.get("subfolder") or ""
            names.append(f"{subfolder}/{filename}" if subfolder else str(filename))
    return names


def submitted_prompt_summary(prompt: dict) -> str:
    latent = prompt.get(LATENT_NODE, {}).get("inputs", {})
    sampler = prompt.get(KSAMPLER_NODE, {}).get("inputs", {})
    unet = prompt.get(UNET_NODE, {}).get("inputs", {})
    clip = prompt.get(CLIP_NODE, {}).get("inputs", {})
    vae = prompt.get(VAE_NODE, {}).get("inputs", {})
    loras = [
        node.get("inputs", {}).get("lora_name")
        for node in prompt.values()
        if isinstance(node, dict)
        and node.get("class_type") == "LoraLoader"
        and node.get("inputs", {}).get("lora_name")
    ]
    parts = [
        f"size={latent.get('width')}x{latent.get('height')}",
        f"batch={latent.get('batch_size')}",
        f"steps={sampler.get('steps')}",
        f"cfg={sampler.get('cfg')}",
        f"seed={sampler.get('seed')}",
        f"sampler={sampler.get('sampler_name')}/{sampler.get('scheduler')}",
        f"denoise={sampler.get('denoise')}",
        f"unet={unet.get('unet_name')}",
        f"clip={clip.get('clip_name')}",
        f"vae={vae.get('vae_name')}",
    ]
    if loras:
        parts.append("loras=" + ", ".join(str(name) for name in loras))
    return "Submitted params: " + " | ".join(parts)


def write_last_api_prompt(prompt: dict, item: dict) -> None:
    data = {
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "item": {
            "index": item.get("index"),
            "character": item.get("character"),
            "outfit": item.get("outfit"),
            "object": item.get("object"),
            "action": item.get("action"),
            "seed": item.get("seed"),
            "filename_prefix": item.get("filename_prefix"),
        },
        "prompt": prompt,
    }
    write_json(LAST_API_PROMPT_PATH, data)


def remap_node_links(value: Any, mapping: dict[str, str]) -> Any:
    if (
        isinstance(value, list)
        and len(value) == 2
        and isinstance(value[0], str)
        and value[0] in mapping
        and isinstance(value[1], int)
    ):
        return [mapping[value[0]], value[1]]
    if isinstance(value, list):
        return [remap_node_links(item, mapping) for item in value]
    if isinstance(value, dict):
        return {key: remap_node_links(item, mapping) for key, item in value.items()}
    return value


def cache_busted_prompt(prompt: dict) -> tuple[dict, str]:
    nonce = str(secrets.randbelow(900000) + 100000)
    node_ids = list(prompt.keys())
    mapping = {node_id: f"{nonce}{index:04d}" for index, node_id in enumerate(node_ids, start=1)}
    remapped = {
        mapping[node_id]: remap_node_links(node, mapping)
        for node_id, node in prompt.items()
    }
    return remapped, nonce


def sync_seed_setting_after_payload(config: dict, payload: dict, *, advance_increment: bool) -> dict:
    model_index = clamp_index(config.get("active_model_preset", 0), len(config.get("model_presets", [])))
    model_preset = config["model_presets"][model_index]
    settings = model_preset.get("settings", {})
    seed_mode = settings.get("seed_mode", "increment")
    selected_items = select_run_items(payload, config)
    current_seed = int(settings.get("seed", 0) or 0)
    seed_info = {
        "mode": seed_mode,
        "seed": current_seed,
        "selected_count": len(selected_items),
        "updated": False,
    }

    if seed_mode == "random":
        if selected_items:
            settings["seed"] = int(selected_items[-1].get("seed", current_seed) or 0)
            if isinstance(payload.get("model"), dict):
                payload["model"]["seed"] = int(settings["seed"])
            if isinstance(payload.get("sampler"), dict):
                payload["sampler"]["seed"] = int(settings["seed"])
            seed_info["seed"] = int(settings["seed"])
            seed_info["updated"] = True
        return seed_info

    if seed_mode != "increment" or not advance_increment:
        return seed_info

    settings["seed"] = current_seed + max(1, len(selected_items))
    seed_info["seed"] = int(settings["seed"])
    seed_info["updated"] = True
    return seed_info


def wait_for_completion(base_url: str, prompt_id: str, poll_seconds: float = 2.0, timeout_seconds: float = 3600.0) -> dict:
    started = time.time()
    last_log_at = 0.0
    last_message = ""
    while True:
        if is_stop_requested():
            return {"status": {"status_str": "stopped"}}
        history = get_json(base_url, f"/history/{prompt_id}", timeout=30)
        if isinstance(history, dict) and prompt_id in history:
            set_status_message("ComfyUI history received")
            return history[prompt_id]
        try:
            queue = get_json(base_url, "/queue", timeout=10)
            message = describe_comfy_queue(queue, prompt_id)
        except Exception as exc:  # noqa: BLE001 - keep waiting but show why status is incomplete
            message = f"Waiting for ComfyUI queue status: {exc}"
        set_status_message(message)
        now = time.time()
        if message != last_message or now - last_log_at >= 15:
            append_log(message)
            last_message = message
            last_log_at = now
        if time.time() - started > timeout_seconds:
            raise TimeoutError(f"Timed out waiting for prompt_id={prompt_id}")
        time.sleep(poll_seconds)


def run_worker(config: dict, payload: dict) -> None:
    template = API_TEMPLATE
    comfy_url = config["comfy_url"]
    items = select_run_items(payload, config)
    client_id = str(uuid.uuid4())
    with STATE_LOCK:
        RUN_STATE.update(
            {
                "running": True,
                "stop_requested": False,
                "current": 0,
                "total": len(items),
                "started_at": time.time(),
                "finished_at": None,
                "last_prompt_id": "",
                "last_error": "",
                "status_message": "Starting",
                "last_outputs": [],
                "last_duration": 0.0,
                "average_duration": 0.0,
                "logs": [],
            }
        )
    append_log(f"Start: {len(items)} job(s)")
    try:
        for current, item in enumerate(items, start=1):
            if is_stop_requested():
                set_status_message("Stop requested")
                append_log("Stop requested.")
                break
            with STATE_LOCK:
                RUN_STATE["current"] = current
            object_label = f" / {item['object']}" if item.get("object") else ""
            label = f"{item['index']} {item['character']} / {item['outfit']}{object_label} / {item['action']}"
            prompt = patch_template(template, payload, item)
            if current == 1:
                set_status_message("Preflight ComfyUI workflow")
                append_log("Preflight ComfyUI workflow")
                try:
                    validate_prompt_with_comfy(comfy_url, prompt)
                    append_log("Preflight OK")
                except Exception as exc:  # noqa: BLE001 - advisory only; let /prompt be the source of truth
                    append_log(f"Preflight warning: {exc}")
                    append_log("Submitting to ComfyUI anyway; /prompt will return the authoritative error if the workflow is invalid.")
            if is_stop_requested():
                set_status_message("Stop requested")
                append_log("Stop requested before submitting next prompt.")
                break
            append_log(f"Queue {label}")
            append_log(submitted_prompt_summary(prompt))
            metadata = item.get("metadata", {})
            if metadata.get("random_prompt_choices_count"):
                append_log(
                    "Random pool: "
                    f"seed={metadata.get('random_pool_seed')} "
                    f"choice={metadata.get('random_prompt_choice')}/{metadata.get('random_prompt_choices_count')}"
                )
            prompt_to_submit, cache_nonce = cache_busted_prompt(prompt)
            append_log(f"ComfyUI cache bypass nonce={cache_nonce}")
            write_last_api_prompt(prompt_to_submit, item)
            set_status_message(f"Queue {label}")
            item_started_at = time.time()
            response = post_json(comfy_url, "/prompt", {"prompt": prompt_to_submit, "client_id": client_id}, timeout=30)
            prompt_id = response.get("prompt_id")
            if not prompt_id:
                raise RuntimeError(f"No prompt_id returned: {response}")
            with STATE_LOCK:
                RUN_STATE["last_prompt_id"] = prompt_id
                RUN_STATE["status_message"] = "Prompt accepted by ComfyUI"
            append_log(f"prompt_id={prompt_id}")
            history = wait_for_completion(comfy_url, prompt_id)
            status = history.get("status", {}).get("status_str", "completed")
            error_details = history_error_details(history)
            images = saved_image_names(history)
            duration = max(0.0, time.time() - item_started_at)
            with STATE_LOCK:
                RUN_STATE["last_duration"] = duration
                RUN_STATE["last_outputs"] = images
                RUN_STATE["status_message"] = f"Finished {label}: {status}"
                completed = max(1, current)
                previous_average = float(RUN_STATE.get("average_duration", 0.0) or 0.0)
                RUN_STATE["average_duration"] = (
                    duration if completed == 1 else ((previous_average * (completed - 1)) + duration) / completed
                )
            append_log(f"Finished {label}: {status} ({duration:.1f}s)")
            if error_details:
                raise RuntimeError(error_details)
            status_lower = str(status).lower()
            if status_lower in {"error", "failed"}:
                raise RuntimeError(f"ComfyUI finished with status: {status}")
            if images:
                preview = ", ".join(images[:5])
                suffix = "" if len(images) <= 5 else f", ... {len(images)} images total"
                append_log(f"Saved image: {preview}{suffix}")
            elif status_lower != "stopped":
                append_log("Warning: ComfyUI finished but did not report any saved image output.")
            if status_lower == "stopped":
                append_log("Stopped before queueing remaining jobs.")
                break
    except Exception as exc:  # noqa: BLE001 - show local tool errors in UI
        with STATE_LOCK:
            RUN_STATE["last_error"] = str(exc)
            RUN_STATE["status_message"] = f"Error: {exc}"
        append_log(f"Error: {exc}")
    finally:
        with STATE_LOCK:
            stopped = bool(RUN_STATE.get("stop_requested"))
            RUN_STATE["running"] = False
            RUN_STATE["finished_at"] = time.time()
            if not RUN_STATE.get("last_error"):
                RUN_STATE["status_message"] = "Run stopped" if stopped else "Run ended"
        append_log("Run stopped." if stopped else "Run ended.")


def summarize_library(library: dict) -> dict:
    return {
        section: [
            {"key": key, "label": label_for(record, key), "record": record}
            for key, record in library[section].items()
        ]
        for section in PROMPT_SECTIONS
    }


def get_comfy_status(config: dict) -> dict:
    try:
        stats = get_json(config["comfy_url"], "/system_stats", timeout=3)
        return {"connected": True, "stats": stats}
    except Exception as exc:  # noqa: BLE001
        return {"connected": False, "error": str(exc)}


def get_comfy_models(config: dict) -> dict:
    folders: list[str]
    try:
        raw = get_json(config["comfy_url"], "/models", timeout=5)
        if isinstance(raw, list):
            folders = [str(item) for item in raw]
        elif isinstance(raw, dict):
            folders = [str(item) for item in raw.keys()]
        else:
            folders = []
    except Exception:
        folders = ["checkpoints", "diffusion_models", "loras", "vae", "text_encoders", "clip", "upscale_models"]

    result: dict[str, list[str]] = {}
    for folder in folders:
        try:
            values = get_json(config["comfy_url"], f"/models/{folder}", timeout=5)
            result[folder] = values if isinstance(values, list) else []
        except Exception:
            result[folder] = []
    try:
        object_info = get_json(config["comfy_url"], "/object_info/KSampler", timeout=5)
        ksampler = object_info.get("KSampler", {}) if isinstance(object_info, dict) else {}
        required = ksampler.get("input", {}).get("required", {})
        sampler_values = required.get("sampler_name", [[], {}])[0]
        scheduler_values = required.get("scheduler", [[], {}])[0]
        result["_samplers"] = sampler_values if isinstance(sampler_values, list) else []
        result["_schedulers"] = scheduler_values if isinstance(scheduler_values, list) else []
    except Exception:
        result["_samplers"] = [
            "euler_ancestral",
            "euler",
            "dpmpp_2m",
            "dpmpp_2m_sde",
            "dpmpp_3m_sde",
            "ddim",
        ]
        result["_schedulers"] = ["normal"]
    return result


def _available_model_names(model_lists: dict, folders: list[str]) -> set[str]:
    names: set[str] = set()
    for folder in folders:
        values = model_lists.get(folder, [])
        if isinstance(values, list):
            names.update(str(value) for value in values if value)
    return names


def validate_model_settings_available(config: dict, model_settings: dict) -> None:
    """Fail early when the selected model/text encoder/VAE was deleted from ComfyUI."""
    model_lists = get_comfy_models(config)
    checks = [
        ("Model/UNET", "unet_name", ["diffusion_models", "checkpoints", "unet"]),
        ("Text encoder/CLIP", "clip_name", ["text_encoders", "clip"]),
        ("VAE", "vae_name", ["vae"]),
    ]
    missing: list[str] = []
    for label, field, folders in checks:
        value = str(model_settings.get(field) or "").strip()
        if not value:
            continue
        available = _available_model_names(model_lists, folders)
        if available and value not in available:
            missing.append(f"{label}: {value}")
    if missing:
        raise ValueError("The selected model is missing from the ComfyUI model list. Refresh the model list on the tuning-comparison page and select it again: " + "; ".join(missing))


HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Anima Image Set Generator</title>
  <style>
    :root {
      --bg: #101113;
      --panel: #181a1f;
      --panel-2: #20232a;
      --line: #323741;
      --text: #f0f2f5;
      --muted: #a9b0bd;
      --red: #c45a62;
      --purple: #8068d9;
      --green: #54a66f;
      --yellow: #d5a84d;
      --blue: #5da1d9;
      --danger: #e06b6b;
      --radius: 8px;
      --font-body: 13px;
      --font-label: 13px;
      --font-help: 13px;
      --font-section: 13px;
      --font-metric: 18px;
      --control-height: 36px;
      --checkbox-size: 16px;
      --header-height: 64px;
      --tabs-height: 53px;
      --bottom-bar-height: 128px;
      --bottom-bar-gap: 20px;
      --header-bg: #121418;
      --tab-bg: #15171c;
      --input-bg: #111318;
      --row-bg: #14171c;
      --row-line: #282d35;
      --deep-bg: #0b0d10;
      --drop-line: #3a4350;
      --soft-line: #29303a;
      --hover-line: #57606f;
      --shadow: rgba(0, 0, 0, .22);
      --overlay-bg: rgba(17, 19, 24, .72);
      --active-control-bg: #22354d;
      --active-control-border: var(--blue);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color-scheme: dark;
    }
    body.theme-light {
      --bg: #f6f7f9;
      --panel: #ffffff;
      --panel-2: #edf0f5;
      --line: #ccd3df;
      --text: #1d2430;
      --muted: #5d6777;
      --red: #b94f59;
      --purple: #715bd1;
      --green: #3f8f5b;
      --yellow: #b88328;
      --blue: #2f7db9;
      --danger: #c55252;
      --header-bg: #ffffff;
      --tab-bg: #f2f4f8;
      --input-bg: #ffffff;
      --row-bg: #f7f8fb;
      --row-line: #d9dee8;
      --deep-bg: #f1f3f7;
      --drop-line: #b8c0ce;
      --soft-line: #d7dde8;
      --hover-line: #8994a6;
      --shadow: rgba(29, 36, 48, .12);
      --overlay-bg: rgba(255, 255, 255, .82);
      --active-control-bg: #dcecff;
      --active-control-border: var(--blue);
      color-scheme: light;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-size: var(--font-body);
      min-height: 100vh;
      scroll-padding-bottom: calc(var(--bottom-bar-height) + var(--bottom-bar-gap));
    }
    header {
      height: var(--header-height);
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 24px;
      border-bottom: 1px solid var(--line);
      background: var(--header-bg);
      position: sticky;
      top: 0;
      z-index: 30;
    }
    h1 {
      margin: 0;
      font-size: var(--font-metric);
      font-weight: 700;
      letter-spacing: 0;
    }
    .status {
      display: flex;
      gap: 10px;
      align-items: center;
      color: var(--muted);
      font-size: var(--font-body);
    }
    .header-left,
    .header-right {
      display: flex;
      align-items: center;
      gap: 12px;
      min-width: 0;
    }
    .header-right { margin-left: auto; }
    .header-switch {
      display: flex;
      align-items: center;
      gap: 5px;
      flex: 0 0 auto;
    }
    .header-switch button {
      min-height: 30px;
      padding: 5px 9px;
      border-radius: 999px;
      font-size: 12px;
      color: var(--muted);
      background: var(--tab-bg);
    }
    .header-switch button.active {
      color: var(--text);
      border-color: var(--active-control-border);
      background: var(--active-control-bg);
      font-weight: 750;
    }
    .dot {
      width: 9px;
      height: 9px;
      border-radius: 999px;
      background: var(--danger);
      display: inline-block;
    }
    .dot.ok { background: var(--green); }
    nav {
      display: flex;
      flex-wrap: nowrap;
      gap: 6px;
      padding: 14px 24px 0;
      min-height: var(--tabs-height);
      overflow-x: auto;
      background: var(--header-bg);
      border-bottom: 1px solid var(--line);
      position: sticky;
      top: var(--header-height);
      z-index: 25;
    }
    .tab-btn {
      border: 1px solid var(--line);
      background: var(--tab-bg);
      color: var(--muted);
      padding: 10px 14px;
      border-radius: var(--radius) var(--radius) 0 0;
      cursor: pointer;
      font-weight: 650;
      font-size: var(--font-body);
      flex: 0 0 auto;
      min-height: 38px;
    }
    .tab-btn.active { color: var(--text); border-bottom-color: transparent; }
    .tab-btn.single { margin-left: 24px; }
    .tab-btn.analyze { margin-left: 24px; }
    .tab-btn.model.active { box-shadow: inset 0 3px 0 var(--red); }
    .tab-btn.loop.active { box-shadow: inset 0 3px 0 var(--green); }
    body.theme-light button.tab-btn.model.active,
    body.theme-light button.tab-btn.loop.active,
    body.theme-light button.active.model,
    body.theme-light button.active.loop { color: var(--text); }
    .tab-btn.db.active { box-shadow: inset 0 3px 0 var(--yellow); }
    .tab-btn.single.active { box-shadow: inset 0 3px 0 var(--danger); }
    .tab-btn.analyze.active { box-shadow: inset 0 3px 0 var(--blue); }
    main { padding: 20px 24px calc(var(--bottom-bar-height) + var(--bottom-bar-gap)); }
    .tab { display: none; }
    .tab.active { display: block; }
    .toolbar {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      margin-bottom: 16px;
    }
    .preset-toolbar {
      position: sticky;
      top: calc(var(--header-height) + var(--tabs-height));
      z-index: 20;
      margin: -20px -24px 16px;
      padding: 12px 24px;
      background: var(--header-bg);
      border-bottom: 1px solid var(--line);
      box-shadow: 0 8px 18px var(--shadow);
    }
    .stack > .toolbar { margin-bottom: 0; }
    .toolbar .muted {
      font-size: var(--font-body);
      font-weight: 650;
    }
    button, input, select, textarea {
      font: inherit;
      color: var(--text);
    }
    button {
      border: 1px solid var(--line);
      background: var(--panel-2);
      border-radius: var(--radius);
      padding: 8px 11px;
      cursor: pointer;
      font-size: var(--font-body);
      min-height: var(--control-height);
    }
    button:hover { border-color: var(--hover-line); }
    button.primary { background: #2b5f3e; border-color: #397a50; }
    button.danger { background: #542b2f; border-color: #8a3d45; }
    button.active.model { border-color: var(--red); color: white; }
    button.active.loop { border-color: var(--green); color: white; }
    input, select, textarea {
      background: var(--input-bg);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      padding: 8px 10px;
      width: 100%;
      font-size: var(--font-body);
      min-height: var(--control-height);
    }
    input:not([type="checkbox"]):not([type="file"]), select {
      height: var(--control-height);
      min-height: var(--control-height);
      line-height: 1.25;
    }
    textarea { min-height: 160px; resize: vertical; line-height: 1.45; }
    label {
      display: grid;
      gap: 6px;
      color: var(--muted);
      font-size: var(--font-label);
      font-weight: 650;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(12, minmax(0, 1fr));
      gap: 14px;
    }
    .stack {
      display: grid;
      gap: 12px;
    }
    .span-3 { grid-column: span 3; }
    .span-4 { grid-column: span 4; }
    .span-6 { grid-column: span 6; }
    .span-8 { grid-column: span 8; }
    .span-12 { grid-column: span 12; }
    .section {
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: var(--radius);
      padding: 16px;
    }
    .section h2 {
      margin: 0 0 12px;
      font-size: var(--font-section);
      letter-spacing: 0;
    }
    .section-title-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      margin-bottom: 10px;
    }
    .section-title-row h2 { margin: 0; }
    .object-row { margin-top: 14px; }
    .loop-card input[id$="Filter"] { margin-bottom: 10px; }
    .object-help { margin-top: 36px; padding-top: 10px; }
    .item-row { margin: 12px 0 0; }
    .selection-actions {
      display: flex;
      gap: 6px;
      flex: 0 0 auto;
    }
    .selection-actions button {
      min-height: 30px;
      padding: 5px 8px;
      font-size: var(--font-label);
    }
    .accent-model { border-top: 3px solid var(--red); }
    .accent-model.alt { border-top-color: var(--purple); }
    .accent-loop { border-top: 3px solid var(--green); }
    .accent-db { border-top: 3px solid var(--yellow); }
    .accent-single { border-top: 3px solid var(--danger); }
    .accent-single.alt { border-top-color: var(--purple); }
    .accent-analyze { border-top: 3px solid var(--blue); }
    .checks {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
      gap: 6px;
      max-height: 420px;
      overflow: auto;
      padding-right: 6px;
    }
    .checks.grouped {
      grid-template-columns: 1fr;
      align-content: start;
    }
    .check-group {
      display: grid;
      gap: 6px;
      border-left: 4px solid var(--group-accent);
      border-radius: 4px 0 0 4px;
      padding: 0 0 4px 8px;
    }
    .check-group.tone-a {
      --group-accent: var(--green);
      --group-tint: rgba(84, 166, 111, .12);
      --group-line: rgba(84, 166, 111, .32);
    }
    .check-group.tone-b {
      --group-accent: var(--blue);
      --group-tint: rgba(93, 161, 217, .12);
      --group-line: rgba(93, 161, 217, .32);
    }
    .check-group-header {
      display: flex;
      align-items: center;
      gap: 8px;
      min-height: 34px;
      padding: 6px 8px;
      border: 1px solid var(--group-line);
      border-radius: 6px;
      background: var(--group-tint);
      color: var(--text);
      font-size: var(--font-body);
      font-weight: 700;
    }
    .check-group-header input { width: auto; }
    .check-group-header small {
      color: var(--muted);
      font-size: var(--font-help);
      font-weight: 650;
    }
    .check-group-list {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
      gap: 6px;
    }
    .check-row {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 7px 8px;
      border: 1px solid var(--row-line);
      border-radius: 6px;
      background: var(--row-bg);
      min-height: 36px;
      color: var(--text);
      font-size: var(--font-body);
    }
    .check-row input { width: auto; }
    .check-row span {
      min-width: 0;
      overflow-wrap: anywhere;
    }
    .switch-row {
      display: flex;
      align-items: center;
      gap: 10px;
      min-height: 38px;
      color: var(--muted);
    }
    .switch-row input { width: auto; }
    .lora-row {
      display: grid;
      grid-template-columns: 28px minmax(180px, 1.2fr) 88px 88px minmax(130px, .85fr) minmax(130px, .85fr);
      gap: 8px;
      align-items: end;
      margin-bottom: 10px;
    }
    .lora-row input[type="checkbox"] { width: auto; }
    .lora-row select,
    .lora-row input,
    .lora-row textarea {
      min-width: 0;
    }
    .lora-row select,
    .lora-row input[type="number"],
    .lora-row textarea {
      height: 36px;
      min-height: 36px;
    }
    .lora-row textarea {
      max-height: 36px;
      resize: none;
      overflow-y: auto;
      padding: 8px 10px;
      font-size: var(--font-body);
      line-height: 1.25;
    }
    .lora-row.lora-disabled .lora-prompt-field {
      opacity: .58;
    }
    .lora-field {
      display: grid;
      gap: 5px;
      min-width: 0;
    }
    .lora-field span {
      color: var(--muted);
      font-size: var(--font-label);
      font-weight: 650;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .model-quadrants,
    .loop-quadrants {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }
    .model-card,
    .loop-card {
      min-height: 265px;
    }
    .db-layout {
      display: grid;
      grid-template-columns: 360px minmax(0, 1fr);
      gap: 14px;
    }
    .db-list {
      max-height: 620px;
      overflow: auto;
      display: grid;
      gap: 6px;
    }
    .db-list.drag-sorting { cursor: grabbing; }
    .group-list { max-height: 210px; }
    .db-item {
      display: flex;
      align-items: center;
      gap: 8px;
      text-align: left;
      white-space: normal;
      line-height: 1.25;
      font-size: var(--font-body);
      width: 100%;
      min-width: 0;
    }
    .db-item.active { border-color: var(--yellow); }
    .db-item.sortable .drag-handle {
      color: var(--muted);
      cursor: grab;
      flex: 0 0 auto;
      font-weight: 800;
      letter-spacing: 0;
      line-height: 1;
      user-select: none;
      width: 18px;
      touch-action: none;
    }
    .db-item.sortable:active .drag-handle { cursor: grabbing; }
    .db-item-label {
      min-width: 0;
      overflow-wrap: anywhere;
    }
    .db-item.dragging {
      opacity: .48;
      border-style: dashed;
    }
    .db-item.drag-over {
      border-color: var(--yellow);
      background: rgba(213,168,77,.08);
      box-shadow: inset 0 0 0 1px rgba(230, 185, 82, .22);
    }
    .bottom-bar {
      position: fixed;
      left: 0;
      right: 0;
      bottom: 0;
      background: var(--input-bg);
      border-top: 1px solid var(--line);
      padding: 12px 24px;
      z-index: 10;
      display: grid;
      grid-template-columns: minmax(280px, 1fr) auto;
      gap: 16px;
      align-items: center;
      max-height: min(46vh, 360px);
      overflow: auto;
    }
    .run-controls {
      display: grid;
      grid-template-columns: 110px repeat(2, auto);
      gap: 8px;
      align-items: end;
    }
    .metric {
      display: flex;
      gap: 18px;
      color: var(--muted);
      font-size: var(--font-body);
      flex-wrap: wrap;
    }
    .metric b { color: var(--text); font-size: var(--font-metric); }
    pre {
      margin: 8px 0 0;
      background: var(--deep-bg);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      padding: 10px;
      max-height: 82px;
      overflow: auto;
      color: var(--muted);
      font-size: var(--font-help);
      white-space: pre-wrap;
    }
    .muted { color: var(--muted); }
    .help-block {
      display: grid;
      gap: 6px;
      margin-top: 12px;
    }
    .help-text {
      margin: 0;
      color: var(--muted);
      font-size: var(--font-help);
      line-height: 1.5;
    }


    .single-alert {
      color: #ff8f8f;
      border: 1px solid rgba(224, 107, 107, .55);
      background: rgba(224, 107, 107, .1);
      border-radius: var(--radius);
      padding: 10px 12px;
      margin: 0 0 14px;
      font-weight: 800;
      line-height: 1.5;
    }
    .single-editor-warning {
      margin: 0 0 14px;
    }
    .single-top-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
      align-items: stretch;
      margin-bottom: 14px;
    }
    .single-top-grid > .section {
      display: flex;
      flex-direction: column;
      min-height: 520px;
    }
    .single-bottom-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
      align-items: stretch;
    }
    .single-bottom-grid > .section {
      height: 100%;
      display: flex;
      flex-direction: column;
    }
    .single-params-section {
      margin-top: 14px;
    }
    .single-mode-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-bottom: 12px;
      flex-wrap: wrap;
      min-height: 38px;
    }
    .single-mode-row h2, .single-mode-row label { margin: 0; }
    .single-mode-inline {
      display: inline-flex;
      align-items: center;
      gap: 8px;
    }
    .single-drop-zone {
      flex: 1 1 auto;
      min-height: 440px;
      height: auto;
      border-width: 2px;
      box-sizing: border-box;
    }
    .single-output-panel {
      flex: 1 1 auto;
      min-height: 440px;
      height: auto;
      border: 2px dashed var(--drop-line);
      box-sizing: border-box;
      border-radius: var(--radius);
      background: var(--input-bg);
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 12px;
      padding: 14px;
      color: var(--muted);
      text-align: center;
      overflow: hidden;
    }
    .single-output-panel.has-image {
      border-style: dashed;
      justify-content: flex-start;
      text-align: left;
    }
    .single-output-panel img {
      display: none;
      width: 100%;
      max-width: 100%;
      max-height: 520px;
      object-fit: contain;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: var(--deep-bg);
      align-self: center;
    }
    .single-output-panel.has-image img { display: block; }
    .single-output-panel.has-image .single-output-empty { display: none; }
    .single-prompt-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
      align-items: start;
    }
    .single-prompt-grid textarea {
      min-height: 160px;
      resize: vertical;
    }
    .single-prompt-grid .span-full {
      grid-column: 1 / -1;
    }
    .single-prompt-card {
      border: 1px solid var(--soft-line);
      border-radius: var(--radius);
      background: var(--overlay-bg);
      padding: 12px 12px 12px 16px;
      display: grid;
      gap: 10px;
      position: relative;
      overflow: hidden;
      align-self: stretch;
    }
    .single-prompt-card::before {
      content: "";
      position: absolute;
      inset: 0 auto 0 0;
      width: 5px;
      background: #e6b952;
    }
    .single-prompt-card.tone-global::before,
    .single-prompt-card.tone-bg::before,
    .single-prompt-card.tone-outfit::before,
    .single-prompt-card.tone-action::before { background: var(--green); }
    .single-prompt-card.tone-view::before,
    .single-prompt-card.tone-character::before,
    .single-prompt-card.tone-object::before { background: var(--blue); }
    .single-prompt-card h3 {
      margin: 0;
      font-size: var(--font-body);
    }
    .single-prompt-card input[type="checkbox"] {
      width: 16px;
      height: 16px;
      min-width: 16px;
      margin: 0 6px 0 0;
      vertical-align: middle;
    }
    .single-inline-check {
      display: inline-flex;
      flex-direction: row;
      align-items: center;
      gap: 6px;
      color: var(--muted);
      min-height: 28px;
      width: auto;
    }
    .single-inline-check input[type="checkbox"] {
      width: 16px;
      min-width: 16px;
      height: 16px;
      margin: 0;
      padding: 0;
    }
    .single-inline-controls {
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }
    .single-number-inline {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      width: auto;
      color: var(--muted);
    }
    .single-number-inline input {
      width: 96px;
    }
    .single-prompt-entity-grid {
      grid-column: 1 / -1;
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
      gap: 14px;
      align-items: start;
    }
    .single-prompt-stack {
      display: grid;
      gap: 14px;
    }
    .single-prompt-entity-grid > .single-prompt-card {
      align-self: start;
    }
    .single-prompt-card .card-grid {
      display: grid;
      gap: 10px;
    }
    .single-prompt-card .card-grid.two {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    #singleActionSelect.single-select-expanded {
      height: auto;
      min-height: calc(var(--input-height) * 2);
      max-height: 240px;
      overflow-y: auto;
      padding-top: 4px;
      padding-bottom: 4px;
    }
    .single-params-grid {
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 12px;
      align-items: end;
    }
    .single-model-toolbar {
      margin: 14px 0 12px;
    }
    .single-editor .toolbar { margin-bottom: 12px; }

    .analyze-layout {
      display: grid;
      grid-template-columns: minmax(320px, .95fr) minmax(0, 1.05fr);
      gap: 14px;
      align-items: start;
    }
    .drop-zone {
      min-height: 520px;
      border: 2px dashed var(--drop-line);
      border-radius: var(--radius);
      background: var(--input-bg);
      display: grid;
      place-items: center;
      padding: 18px;
      text-align: center;
      color: var(--muted);
      cursor: pointer;
      transition: border-color .12s ease, background .12s ease;
    }
    .drop-zone.drag-over {
      border-color: var(--blue);
      background: rgba(93, 161, 217, .08);
    }
    .drop-zone.has-image {
      display: block;
      min-height: 0;
      text-align: left;
    }
    .drop-zone input { display: none; }
    .drop-copy { display: grid; gap: 8px; justify-items: center; }
    .drop-copy strong { color: var(--text); font-size: 16px; }
    .drop-copy span { line-height: 1.5; }
    .image-preview-wrap { display: none; gap: 12px; }
    .drop-zone.has-image .image-preview-wrap { display: grid; }
    .drop-zone.has-image .drop-copy { display: none; }
    .drop-zone.single-drop-zone.has-image {
      display: flex;
      flex-direction: column;
      justify-content: flex-start;
      align-items: stretch;
      min-height: 440px;
      flex: 1 1 auto;
    }
    .drop-zone.single-drop-zone.has-image .image-preview {
      max-height: 520px;
    }
    .image-preview {
      width: 100%;
      max-height: 68vh;
      object-fit: contain;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: var(--deep-bg);
    }
    .image-file-name {
      color: var(--muted);
      overflow-wrap: anywhere;
      font-size: var(--font-help);
    }
    .analysis-panel {
      display: grid;
      gap: 14px;
      align-content: start;
    }
    .analysis-empty,
    .analysis-warning {
      color: var(--muted);
      line-height: 1.6;
      border: 1px dashed var(--line);
      border-radius: var(--radius);
      padding: 14px;
      background: var(--row-bg);
    }
    .analysis-warning { border-color: #645738; background: rgba(213,168,77,.08); }
    .metadata-card {
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: var(--row-bg);
      padding: 14px;
      display: grid;
      gap: 10px;
    }
    .metadata-card h3 {
      margin: 0;
      font-size: 16px;
      color: var(--text);
    }
    .metadata-section {
      border-top: 1px solid var(--line);
      padding-top: 10px;
      display: grid;
      gap: 8px;
    }
    .metadata-title-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
    }
    .metadata-title-row h4 {
      margin: 0;
      color: var(--text);
      font-size: var(--font-section);
    }
    .badges { display: flex; flex-wrap: wrap; gap: 6px; }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border-radius: 6px;
      background: var(--active-control-bg);
      color: var(--blue);
      font-weight: 800;
      letter-spacing: .04em;
      padding: 5px 8px;
      font-size: 12px;
      text-transform: uppercase;
    }
    .badge.soft {
      background: var(--panel-2);
      color: var(--muted);
      text-transform: none;
      letter-spacing: 0;
    }
    .metadata-text {
      margin: 0;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      color: var(--muted);
      line-height: 1.55;
      max-height: none;
      overflow: visible;
    }
    .lora-list {
      display: grid;
      gap: 7px;
    }
    .lora-analysis-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 8px;
      align-items: center;
      border: 1px solid var(--soft-line);
      border-radius: 6px;
      background: var(--input-bg);
      padding: 8px 10px;
    }
    .lora-analysis-name {
      color: var(--text);
      font-weight: 750;
      overflow-wrap: anywhere;
    }
    .lora-analysis-detail {
      color: var(--muted);
      font-size: var(--font-help);
      margin-top: 3px;
      overflow-wrap: anywhere;
    }
    .match-list {
      display: grid;
      gap: 7px;
    }
    .match-row {
      display: grid;
      grid-template-columns: 92px minmax(0, 1fr) auto;
      gap: 8px;
      align-items: center;
      border: 1px solid var(--soft-line);
      border-radius: 6px;
      background: var(--input-bg);
      padding: 8px 10px;
    }
    .match-section { color: var(--blue); font-weight: 800; }
    .match-name { overflow-wrap: anywhere; }
    .match-key { color: var(--muted); font-size: var(--font-help); overflow-wrap: anywhere; }
    .kv-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }
    .kv-item {
      border: 1px solid var(--soft-line);
      border-radius: 6px;
      background: var(--input-bg);
      padding: 8px 10px;
      display: grid;
      gap: 3px;
      min-width: 0;
    }
    .kv-item small { color: var(--muted); font-size: var(--font-help); }
    .kv-item span { overflow-wrap: anywhere; }

    .inline { display: flex; gap: 8px; align-items: center; }
    .inline input { width: auto; }
    .hidden { display: none; }
    body, button, input, select, textarea, label, .help-text, .toolbar .muted, .single-prompt-card h3 {
      font-size: var(--font-body);
    }
    input[type="checkbox"],
    .switch-row input[type="checkbox"],
    .lora-row input[type="checkbox"],
    .single-prompt-card input[type="checkbox"],
    .single-inline-check input[type="checkbox"],
    .inline input[type="checkbox"],
    .check-row input[type="checkbox"],
    .check-group-header input[type="checkbox"] {
      width: var(--checkbox-size);
      height: var(--checkbox-size);
      min-width: var(--checkbox-size);
      min-height: var(--checkbox-size);
      max-width: var(--checkbox-size);
      max-height: var(--checkbox-size);
      flex: 0 0 var(--checkbox-size);
      margin: 0;
      padding: 0;
      accent-color: var(--blue);
    }
    input:not([type="checkbox"]):not([type="file"]), select {
      height: var(--control-height);
      min-height: var(--control-height);
      max-height: var(--control-height);
    }
    .switch-row, .single-inline-check, .check-row, .check-group-header {
      align-items: center;
    }
    .lora-row > input[type="checkbox"] {
      align-self: end;
      justify-self: center;
      margin-bottom: calc((var(--control-height) - var(--checkbox-size)) / 2);
    }
    @media (max-width: 980px) {
      .grid, .db-layout, .bottom-bar, .run-controls, .model-quadrants, .loop-quadrants, .single-top-grid, .single-bottom-grid, .analyze-layout, .kv-grid, .single-prompt-grid, .single-prompt-card .card-grid.two, .single-params-grid, .single-prompt-entity-grid { grid-template-columns: 1fr; }
      .span-3, .span-4, .span-6, .span-8, .span-12 { grid-column: span 1; }
      header { height: auto; min-height: var(--header-height); flex-wrap: wrap; gap: 8px; padding-top: 8px; padding-bottom: 8px; }
      .header-left, .header-right { flex-wrap: wrap; }
      .header-right { margin-left: 0; }
      .single-mode-row { flex-direction: column; align-items: stretch; }
      .single-mode-inline { width: 100%; }
      .match-row { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <header>
    <div class="header-left">
      <div class="header-switch language-switch" aria-label="Language selector">
        <button type="button" data-lang="en">English</button>
        <button type="button" data-lang="zh-Hant">Traditional Chinese</button>
        <button type="button" data-lang="ko">한국어</button>
      </div>
      <h1 id="appTitle">Anima Image Set Generator</h1>
    </div>
    <div class="header-right">
      <div class="header-switch theme-switch" aria-label="Theme selector">
        <button type="button" data-theme="light">Light</button>
        <button type="button" data-theme="dark">Dark</button>
      </div>
      <div class="status"><span id="comfyDot" class="dot"></span><span id="comfyText">Checking ComfyUI...</span></div>
    </div>
  </header>
  <nav>
    <button class="tab-btn model active" data-tab="model">Model parameters</button>
    <button class="tab-btn loop" data-tab="loop">Image set settings</button>
    <button class="tab-btn db" data-tab="db">Data editor</button>
    <button class="tab-btn single" data-tab="single">Tuning comparison</button>
    <button class="tab-btn analyze" data-tab="analyze">Parse image</button>
  </nav>
  <main>
    <section id="tab-model" class="tab active">
      <div class="toolbar preset-toolbar">
        <span id="modelPresetButtons"></span>
        <button id="renameModelPreset">Rename preset</button>
        <button id="refreshModels">Refresh model list</button>
      </div>
      <div class="model-quadrants">
        <div class="section accent-model model-card">
          <h2>Model</h2>
          <div class="grid">
            <label class="span-12">Model/UNET<select id="unetName"></select></label>
            <label class="span-12">Text encoder/CLIP<select id="clipName"></select></label>
            <label class="span-12">VAE<select id="vaeName"></select></label>
            <label class="span-12">Sampler<select id="samplerName"></select></label>
          </div>
        </div>
        <div class="section accent-model alt model-card">
          <h2>LoRA</h2>
          <div id="loraRows"></div>
        </div>
        <div class="section accent-model model-card">
          <h2>Parameters</h2>
          <div class="grid">
            <label class="span-6">Width<input id="width" type="number" min="64"></label>
            <label class="span-6">Height<input id="height" type="number" min="64"></label>
            <label class="span-6">Steps<input id="steps" type="number" min="1"></label>
            <label class="span-6">Prompt guidance/CFG<input id="cfg" type="number" min="0" step="0.1"></label>
            <label class="span-6">Denoise<input id="denoise" type="number" min="0" max="1" step="0.01"></label>
            <label class="span-6">Scheduler<select id="schedulerName"></select></label>
            <label class="span-6">Upscale model<select id="upscaleModel"></select></label>
            <label class="span-6">Upscale scale<input id="upscaleScale" type="number" min="0.1" step="0.1"></label>
          </div>
        </div>
        <div class="section accent-model alt model-card">
          <h2>Seed</h2>
          <div class="grid">
            <label class="span-6">Seed<input id="seed" type="number" min="0"></label>
            <label class="span-6">Seed mode<select id="seedMode"><option value="increment">Increment</option><option value="fixed">Fixed</option><option value="random">Random</option></select></label>
          </div>
        </div>
      </div>
    </section>

    <section id="tab-loop" class="tab">
      <div class="toolbar preset-toolbar">
        <span id="loopPresetButtons"></span>
        <button id="renameLoopPreset">Rename preset</button>
      </div>
      <div class="loop-quadrants">
        <div class="section accent-loop loop-card">
          <div class="section-title-row"><h2>Characters</h2><div class="selection-actions"><button id="selectAllCharacters">Select all</button><button id="clearAllCharacters">Clear all</button></div></div>
          <input id="characterFilter" placeholder="Search characters">
          <div id="characterChecks" class="checks"></div>
        </div>
        <div class="section accent-loop loop-card">
          <div class="section-title-row"><h2>Outfits / Objects</h2><div class="selection-actions"><button id="selectAllOutfits">Select all outfits</button><button id="clearAllOutfits">Clear outfits</button></div></div>
          <input id="outfitFilter" placeholder="Search outfits">
          <div id="outfitChecks" class="checks"></div>
          <div class="section-title-row object-row"><h2>Objects</h2><div class="selection-actions"><button id="selectAllObjects">Select all objects</button><button id="clearAllObjects">Clear objects</button></div></div>
          <input id="objectFilter" placeholder="Search objects" oninput="renderLoopTab()">
          <div id="objectChecks" class="checks"></div>
          <p class="help-text object-help">• <strong>Objects</strong>: Appended directly to the image prompt. When multiple objects are selected, all selected object prompts are inserted into every image; they do not increase the loop multiplier like characters, outfits, and actions.</p>
        </div>
        <div class="section accent-loop loop-card">
          <div class="section-title-row"><h2>Emotion / Action</h2><div class="selection-actions"><button id="selectAllActions">Select all</button><button id="clearAllActions">Clear all</button></div></div>
          <input id="actionFilter" placeholder="Search actions">
          <div id="actionChecks" class="checks"></div>
        </div>
        <div class="section accent-loop loop-card">
          <h2>View / Background / Global prompts</h2>
          <div class="grid">
            <label class="span-12">View<select id="angleSelect"></select></label>
            <label class="span-12">Background<select id="backgroundSelect"></select></label>
            <div class="span-12">
              <label class="switch-row"><input type="checkbox" id="useGlobalPositive"> Enable global positive prompt</label>
              <label class="switch-row"><input type="checkbox" id="useGlobalNegative"> Enable global negative prompt</label>
              <label class="switch-row"><input type="checkbox" id="includeRandom"> Enable random variation</label>
              <label class="switch-row"><input type="checkbox" id="expandRandomPrompts"> Output every variation</label>
              <label class="switch-row"><input type="checkbox" id="useCustomPrompt"> Enable custom field</label>
            </div>
            <p class="span-12 help-text">• Enable custom field: when checked, inserts the custom field from Emotion / Action into the prompt.</p>
          </div>
        </div>
      </div>
    </section>

    <section id="tab-db" class="tab">
      <div class="db-layout">
        <div class="section accent-db">
          <h2>Database</h2>
          <div class="stack">
            <label>Category<select id="dbSection">
              <option value="global_positive">Global Positive</option>
              <option value="global_negative">Global Negative</option>
              <option value="characters">Characters</option>
              <option value="outfits">Outfits</option>
              <option value="objects">Objects</option>
              <option value="actions">Emotion / Action</option>
              <option value="angles">View</option>
              <option value="backgrounds">Background</option>
            </select></label>
            <input id="dbFilter" placeholder="Search data">
            <div id="dbGroupTools" class="stack">
              <div class="section-title-row"><h2>Groups</h2><div class="selection-actions"><button id="dbAddGroup">Add</button><button id="dbRenameGroup">Rename</button><button id="dbDeleteGroup">Delete</button></div></div>
              <div id="dbGroupList" class="db-list group-list"></div>
            </div>
            <div class="section-title-row item-row"><h2>Items</h2><div class="selection-actions">
              <button id="dbAdd">Add item</button>
            </div></div>
            <div id="dbList" class="db-list"></div>
          </div>
        </div>
        <div class="section accent-db">
          <h2>Edit</h2>
          <div class="grid">
            <label class="span-4" id="dbKeyWrap">Key<input id="dbKey"></label>
            <label class="span-8" id="dbDisplayNameWrap">Display name<input id="dbDisplayName"></label>
            <label class="span-12" id="dbGroupWrap">Groups<select id="dbGroupSelect"></select></label>
            <label class="span-12">Positive prompt<textarea id="dbPrompt"></textarea></label>
            <label class="span-12" id="negativeWrap">Negative prompt<textarea id="dbNegativePrompt"></textarea></label>
            <label class="span-12" id="randomWrap">Variation prompt<textarea id="dbRandomPrompt"></textarea></label>
            <label class="span-12" id="customPromptWrap">Custom prompt<textarea id="dbCustomPrompt"></textarea></label>
          </div>
          <div class="help-block">
            <p class="help-text">• Key: final output filename.</p>
            <p class="help-text">• Image filename format:<strong><code>character_outfit_action</code></strong></p>
            <p class="help-text">• Negative prompt: each item has its own negative prompt; it is inserted only when that item is selected.</p>
            <p class="help-text">• Variation prompt: separate entries with Enter. When random variation is enabled, one line is randomly inserted.</p>
            <p class="help-text">• Custom prompt: when the custom field is enabled, this field is appended to each item.</p>
          </div>
        </div>
      </div>
    </section>


    <section id="tab-single" class="tab">
      <p class="single-alert">Generating from this tab ignores image-set selections and outputs a single image only.</p>
      <div class="single-top-grid">
        <div class="section accent-single">
          <div class="single-mode-row">
            <h2>Reference image</h2>
            <label class="single-mode-inline">Mode<select id="singleSourceMode">
              <option value="previous">Previous generated image</option>
              <option value="fixed">Fixed reference image</option>
            </select></label>
          </div>
          <label id="singleImageDropZone" class="drop-zone single-drop-zone">
            <input id="singleImageFileInput" type="file" accept="image/png,image/jpeg,image/webp,image/*">
            <div class="drop-copy">
              <strong>Drop image</strong>
              <span>Click to select an image, or drag the comparison image into this area.</span>
              <span class="help-text">This field is for visual comparison only and is not used for generation.</span>
            </div>
            <div class="image-preview-wrap">
              <img id="singleInputPreview" class="image-preview" alt="Reference image preview">
              <div id="singleInputFileName" class="image-file-name"></div>
            </div>
          </label>
        </div>
        <div class="section accent-single">
          <div class="single-mode-row">
            <h2>Generated image preview</h2>
            <div></div>
          </div>
          <div id="singleOutputPanel" class="single-output-panel">
            <div class="single-output-empty">No image generated yet. The latest result appears after single-image generation finishes.</div>
            <img id="singleOutputPreview" alt="Single image output preview">
            <div id="singleOutputFileName" class="image-file-name"></div>
          </div>
        </div>
      </div>

      <p class="single-alert single-editor-warning">The parameter and prompt edits below sync directly with Model parameters and the Data editor database.</p>

      <div class="single-editor">
        <div class="single-prompt-grid">
            <div class="single-prompt-card tone-global span-full">
              <h3>Global prompts</h3>
              <div class="card-grid two">
                <label class="single-inline-check"><input type="checkbox" id="singleUseGlobalPositive"> Enable global positive prompt</label>
                <label class="single-inline-check"><input type="checkbox" id="singleUseGlobalNegative"> Enable global negative prompt</label>
              </div>
              <div class="card-grid two">
                <label><textarea id="singleGlobalPositive"></textarea></label>
                <label><textarea id="singleGlobalNegative"></textarea></label>
              </div>
            </div>
            <div class="single-prompt-card tone-view">
              <h3>View</h3>
              <div class="card-grid">
                <label>Select view<select id="singleAngleSelect"></select></label>
                <label>Positive prompt<textarea id="singleAnglePrompt"></textarea></label>
                <label>Negative prompt<textarea id="singleAngleNegativePrompt"></textarea></label>
              </div>
            </div>
            <div class="single-prompt-card tone-bg">
              <h3>Background</h3>
              <div class="card-grid">
                <label>Select background<select id="singleBackgroundSelect"></select></label>
                <label>Positive prompt<textarea id="singleBackgroundPrompt"></textarea></label>
                <label>Negative prompt<textarea id="singleBackgroundNegativePrompt"></textarea></label>
              </div>
            </div>
            <div class="single-prompt-entity-grid">
              <div class="single-prompt-stack">
                <div class="single-prompt-card tone-character">
                  <h3>Characters</h3>
                  <div class="card-grid">
                    <label>Select character<select id="singleCharacterSelect"></select></label>
                    <label>Positive prompt<textarea id="singleCharacterPrompt"></textarea></label>
                    <label>Negative prompt<textarea id="singleCharacterNegativePrompt"></textarea></label>
                  </div>
                </div>
                <div class="single-prompt-card tone-outfit">
                  <h3>Outfits</h3>
                  <div class="card-grid">
                    <label>Select outfit<select id="singleOutfitSelect"></select></label>
                    <label>Positive prompt<textarea id="singleOutfitPrompt"></textarea></label>
                    <label>Negative prompt<textarea id="singleOutfitNegativePrompt"></textarea></label>
                  </div>
                </div>
                <div class="single-prompt-card tone-object">
                  <h3>Objects</h3>
                  <div class="card-grid">
                    <label>Select object<select id="singleObjectSelect"></select></label>
                    <label>Positive prompt<textarea id="singleObjectPrompt"></textarea></label>
                    <label>Negative prompt<textarea id="singleObjectNegativePrompt"></textarea></label>
                  </div>
                </div>
              </div>
              <div class="single-prompt-card tone-action">
                <h3>Emotion / Action</h3>
                <div class="card-grid">
                  <input id="singleActionFilter" placeholder="Search actions">
                  <label>Select emotion / action<select id="singleActionSelect"></select></label>
                  <label>Positive prompt<textarea id="singleActionPrompt"></textarea></label>
                  <label>Negative prompt<textarea id="singleActionNegativePrompt"></textarea></label>
                  <div class="single-inline-controls">
                    <label class="single-inline-check"><input type="checkbox" id="singleActionRandomEnabled"> Enable variation prompt</label>
                    <label class="single-number-inline">Index<select id="singleActionRandomIndex"></select></label>
                    <span id="singleActionRandomCount" class="help-text"></span>
                  </div>
                  <label>Variation prompt<textarea id="singleActionRandomPrompt" readonly></textarea></label>
                  <label class="single-inline-check"><input type="checkbox" id="singleActionCustomEnabled"> Enable custom prompt</label>
                  <label>Custom prompt<textarea id="singleActionCustomPrompt"></textarea></label>
                </div>
              </div>
            </div>
        </div>
        <div class="toolbar single-model-toolbar">
          <span id="singleModelPresetButtons"></span>
          <button id="singleRefreshModels">Refresh model list</button>
        </div>
        <div class="single-bottom-grid">
          <div class="section accent-single">
            <h2>Model selection</h2>
            <div class="grid">
              <label class="span-12">Model/UNET<select id="singleUnetName"></select></label>
              <label class="span-12">Text encoder/CLIP<select id="singleClipName"></select></label>
              <label class="span-12">VAE<select id="singleVaeName"></select></label>
              <label class="span-12">Sampler<select id="singleSamplerName"></select></label>
            </div>
          </div>
          <div class="section accent-single alt">
            <h2>LoRA</h2>
            <div id="singleLoraRows"></div>
          </div>
        </div>
        <div class="section accent-single single-params-section">
          <h2>Parameters</h2>
          <div class="single-params-grid">
            <label>Width<input id="singleWidth" type="number" min="64"></label>
            <label>Height<input id="singleHeight" type="number" min="64"></label>
            <label>Steps<input id="singleSteps" type="number" min="1"></label>
            <label>Prompt guidance/CFG<input id="singleCfg" type="number" min="0" step="0.1"></label>
            <label>Denoise<input id="singleDenoise" type="number" min="0" max="1" step="0.01"></label>
            <label>Seed<input id="singleSeed" type="number" min="0"></label>
            <label>Seed mode<select id="singleSeedMode"><option value="increment">Increment</option><option value="fixed">Fixed</option><option value="random">Random</option></select></label>
            <label>Scheduler<select id="singleSchedulerName"></select></label>
            <label>Upscale model<select id="singleUpscaleModel"></select></label>
            <label>Upscale scale<input id="singleUpscaleScale" type="number" min="0.1" step="0.1"></label>
          </div>
        </div>      </div>
    </section>


    <section id="tab-analyze" class="tab">
      <div class="analyze-layout">
        <div class="section accent-analyze">
          <h2>Image input</h2>
          <label id="imageDropZone" class="drop-zone">
            <input id="imageFileInput" type="file" accept="image/png,image/jpeg,image/webp,image/*">
            <div class="drop-copy">
              <strong>Drop image</strong>
              <span>Click to select an image, or drag an AI image into this area.</span>
              <span class="help-text">Reads ComfyUI and parameter metadata embedded in PNG files.</span>
            </div>
            <div class="image-preview-wrap">
              <img id="imagePreview" class="image-preview" alt="Image preview">
              <div id="imageFileName" class="image-file-name"></div>
            </div>
          </label>
        </div>
        <div class="section accent-analyze">
          <h2>Data parsing</h2>
          <div id="imageAnalysis" class="analysis-panel"></div>
        </div>
      </div>
    </section>
  </main>

  <section class="bottom-bar" id="bottomBar">
    <div>
      <div class="metric">
        <span>Total images this run <b id="totalCount">0</b></span>
        <span>Progress <b id="runProgress">0 / 0</b></span>
        <span>Seconds per image <b id="secondsPerImage">--</b></span>
        <span>Status <b id="runStatusText">Idle</b></span>
      </div>
      <pre id="logs"></pre>
    </div>
    <div class="run-controls">
      <label>Run count<input id="repeatCount" type="number" min="1"></label>
      <button class="primary" id="startBtn">Start run</button>
      <button class="danger" id="stopBtn">Stop</button>
    </div>
  </section>

  <script>
    let config = null;
    let library = null;
    let modelLists = {};
    let dbCurrentKey = "";
    let dbCurrentGroupKey = "";
    let dbEditorSection = "global_positive";
    let dbEditorKey = "";
    let dbDirty = false;
    let dbDragJustEnded = false;
    let dbDragContext = null;
    let configSaveTimer = null;
    let librarySaveTimer = null;
    let singleSourceImageData = "";
    let singleSourceFileName = "";
    let lastSinglePreviewName = "";

    const $ = (id) => document.getElementById(id);

        const UI_TRANSLATIONS = {
      "zh-Hant": {
        ": Appended directly to the image prompt. When multiple objects are selected, all selected object prompts are inserted into every image; they do not increase the loop multiplier like characters, outfits, and actions.": "：直接追加至圖片中。多選時，會將所有選取物件的 prompts 插入每張圖，不像角色 / 服裝 / 情緒動作一樣會加入迴圈乘數中",
        "Add": "新增",
        "Add item": "新增條目",
        "Anima Image Set Generator": "Anima套圖產生器",
        "Background": "Background",
        "Category": "分類",
        "Changes saved": "變更已儲存",
        "Characters": "Characters",
        "Checking ComfyUI...": "Checking ComfyUI...",
        "Clear all": "全部取消",
        "Clear objects": "取消物件",
        "Clear outfits": "取消服裝",
        "Click to select an image, or drag an AI image into this area.": "點擊選取圖片，或將 AI 圖片拖曳到此區域。",
        "Click to select an image, or drag the comparison image into this area.": "點擊選取圖片，或將作為比對的圖片拖曳到此區域。",
        "ComfyUI connected": "ComfyUI connected",
        "Custom prompt": "自定義提示詞",
        "Dark": "Dark",
        "Data editor": "資料編輯",
        "Data parsing": "資料解析",
        "Database": "資料庫",
        "Database mapping": "資料庫對應",
        "Delete": "刪除",
        "Denoise": "降噪/Denoise",
        "Display name": "中文名稱",
        "Do not use": "Do not use",
        "Drag to sort": "拖曳排序",
        "Drop image": "Drop image",
        "Edit": "編輯",
        "Emotion / Action": "情緒 / 動作",
        "Enable custom field": "啟用自定義欄位",
        "Enable custom prompt": "自定義提示詞開啟",
        "Enable global negative prompt": "負面全域開啟",
        "Enable global positive prompt": "正面全域開啟",
        "Enable random variation": "啟用隨機差分",
        "Enable variation prompt": "差分提示詞開啟",
        "English": "English",
        "Equipment / Props": "Equipment / Props",
        "Failed to load the model list. Start ComfyUI first.": "模型清單讀取失敗，請先開啟 ComfyUI",
        "Failed to run single-image generation": "單圖執行失敗",
        "Failed to start run": "開始執行失敗",
        "Failed to stop": "停止失敗",
        "Fixed": "固定/Fixed",
        "Fixed reference image": "固定參考圖",
        "Generated image preview": "生成圖片預覽",
        "Generating from this tab ignores image-set selections and outputs a single image only.": "於此分頁生圖時，將會忽略套圖選擇，只進行單圖輸出。",
        "Generation metadata": "生成資料",
        "Global Negative": "Global Negative",
        "Global Positive": "Global Positive",
        "Global prompts": "全域提示詞",
        "Groups": "群組",
        "Height": "高度/Height",
        "Idle": "Idle",
        "Image input": "圖片輸入",
        "Image preview": "圖片預覽",
        "Image set settings": "套圖設定",
        "Increment": "遞增/Increment",
        "Index": "編號",
        "Items": "條目",
        "Light": "Light",
        "Mode": "模式",
        "Model": "模型",
        "Model list refreshed": "模型清單已刷新",
        "Model parameters": "模型參數",
        "Model selection": "模型選擇",
        "Model strength": "模型強度",
        "Model/LoRA model": "模型/LoRA model",
        "Model/UNET": "模型/UNET",
        "Negative": "負面/Negative",
        "Negative prompt": "負面提示詞",
        "New item saved": "新增條目已儲存",
        "No displayable generation-metadata sections were found in this image.": "此圖片沒有析出可顯示的生成資料子區塊。",
        "No image generated yet. The latest result appears after single-image generation finishes.": "尚未生成圖片。完成單圖輸出後，會顯示最新結果。",
        "No image has been loaded. Generation metadata appears after an image is loaded.": "尚未讀取圖片。讀取圖片後，將會顯示生成資料。",
        "No image selected": "尚未選取圖片",
        "No items": "No items",
        "No previous generated image yet.": "尚未有上一張生成圖片。",
        "None": "無",
        "NSFW Display / Invitation": "NSFW Display / Invitation",
        "NSFW Hands / Feet / Breast Interaction": "NSFW Hands / Feet / Breast Interaction",
        "NSFW Lying Positions": "NSFW Lying Positions",
        "NSFW Oral Interaction": "NSFW Oral Interaction",
        "NSFW Riding / Seated": "NSFW Riding / Seated",
        "NSFW Side-Lying / Supported": "NSFW Side-Lying / Supported",
        "NSFW Solo / Toys": "NSFW Solo / Toys",
        "NSFW Standing / Lifted": "NSFW Standing / Lifted",
        "Objects": "物件",
        "Other": "Other",
        "Other data": "其他資料",
        "Outfits": "Outfits",
        "Outfits / Objects": "服裝 / 物件",
        "Output every variation": "差分全輸出",
        "Parameters": "參數",
        "Parse failed:": "解析失敗：",
        "Parse image": "解析圖片",
        "Parsing image metadata...": "正在解析圖片資料...",
        "Positive": "正面/Positive",
        "Positive prompt": "正面提示詞",
        "Previous generated image": "前一張生成的圖",
        "Progress": "執行進度",
        "Prompt": "提示詞",
        "Prompt guidance/CFG": "提示詞權重/CFG",
        "Random": "隨機/Random",
        "Reads ComfyUI and parameter metadata embedded in PNG files.": "系統讀取 PNG 內嵌的 ComfyUI / 參數文字資料",
        "Reference image": "參考圖片",
        "Reference image preview": "參考圖片預覽",
        "Refresh model list": "刷新模型清單",
        "Rename": "改名",
        "Rename preset": "修改預設名稱",
        "Resource usage": "使用資源",
        "Run count": "跑幾次",
        "Running": "Running",
        "Sampler": "採樣器/Sampler",
        "Scheduler": "排程/Scheduler",
        "Search actions": "搜尋動作",
        "Search characters": "搜尋角色",
        "Search data": "搜尋資料",
        "Search objects": "搜尋物件",
        "Search outfits": "搜尋服裝",
        "sec/image": "秒/張",
        "Seconds per image": "出圖秒數",
        "Seed": "種子",
        "Seed mode": "種子模式/Seed mode",
        "Select all": "全選",
        "Select all objects": "全選物件",
        "Select all outfits": "全選服裝",
        "Select background": "背景選擇",
        "Select character": "角色選擇",
        "Select emotion / action": "情緒 / 動作選擇",
        "Select object": "物件選擇",
        "Select outfit": "服裝選擇",
        "Select view": "視圖選擇",
        "SFW Emotion / Action": "SFW Emotion / Action",
        "Single image output preview": "單圖輸出預覽",
        "Start ComfyUI first": "請先開啟 ComfyUI",
        "Start run": "開始執行",
        "Status": "狀態",
        "Steps": "步數/Steps",
        "Stop": "停止",
        "Text encoder/CLIP": "文字編碼/CLIP",
        "Text strength": "文字強度",
        "The parameter and prompt edits below sync directly with Model parameters and the Data editor database.": "以下的參數/prompts調整，將會直接與模型參數/資料編輯的資料庫同步",
        "This field is for visual comparison only and is not used for generation.": "本欄僅供視覺比對，不會參與生圖",
        "Total images this run": "本次總張數",
        "Traditional Chinese": "繁體中文",
        "Tuning comparison": "調校比對",
        "Uncategorized": "Uncategorized",
        "Unknown": "未知",
        "Untitled": "Untitled",
        "Upscale model": "放大模型/Upscale model",
        "Upscale scale": "放大倍率/Upscale scale",
        "Using existing JSON": "沿用現有 JSON",
        "VAE": "變分自編碼器/VAE",
        "Variation prompt": "差分提示詞",
        "View": "View",
        "View / Background / Global prompts": "視圖 / 背景 / 全域",
        "Width": "寬度/Width",
        "• Custom prompt: when the custom field is enabled, this field is appended to each item.": "．自定義提示詞：啟用自定義欄位後，每個條目將會追加此欄位中的內容",
        "• Enable custom field: when checked, inserts the custom field from Emotion / Action into the prompt.": "．啟用自定義欄位：勾選之後，會啟動情緒 / 動作中的自定義欄位，插入提示中",
        "• Image filename format:": "．圖片檔名的格式：",
        "• Key: final output filename.": "．Key值：最後輸出的檔名",
        "• Negative prompt: each item has its own negative prompt; it is inserted only when that item is selected.": "．負面提示詞：每個條目自己的負面提示詞；只有該條目被選用時才會插入",
        "• Variation prompt: separate entries with Enter. When random variation is enabled, one line is randomly inserted.": "．差分提示詞：用Enter分行區隔。啟用隨機差分時，會隨機抽出一行提示詞加進其中",
        "한국어": "한국어"
      },
      "en": {
        ": Appended directly to the image prompt. When multiple objects are selected, all selected object prompts are inserted into every image; they do not increase the loop multiplier like characters, outfits, and actions.": ": Appended directly to the image prompt. When multiple objects are selected, all selected object prompts are inserted into every image; they do not increase the loop multiplier like characters, outfits, and actions.",
        "Add": "Add",
        "Add item": "Add item",
        "Anima Image Set Generator": "Anima Image Set Generator",
        "Background": "Background",
        "Category": "Category",
        "Changes saved": "Changes saved",
        "Characters": "Characters",
        "Checking ComfyUI...": "Checking ComfyUI...",
        "Clear all": "Clear all",
        "Clear objects": "Clear objects",
        "Clear outfits": "Clear outfits",
        "Click to select an image, or drag an AI image into this area.": "Click to select an image, or drag an AI image into this area.",
        "Click to select an image, or drag the comparison image into this area.": "Click to select an image, or drag the comparison image into this area.",
        "ComfyUI connected": "ComfyUI connected",
        "Custom prompt": "Custom prompt",
        "Dark": "Dark",
        "Data editor": "Data editor",
        "Data parsing": "Data parsing",
        "Database": "Database",
        "Database mapping": "Database mapping",
        "Delete": "Delete",
        "Denoise": "Denoise",
        "Display name": "Display name",
        "Do not use": "Do not use",
        "Drag to sort": "Drag to sort",
        "Drop image": "Drop image",
        "Edit": "Edit",
        "Emotion / Action": "Emotion / Action",
        "Enable custom field": "Enable custom field",
        "Enable custom prompt": "Enable custom prompt",
        "Enable global negative prompt": "Enable global negative prompt",
        "Enable global positive prompt": "Enable global positive prompt",
        "Enable random variation": "Enable random variation",
        "Enable variation prompt": "Enable variation prompt",
        "English": "English",
        "Equipment / Props": "Equipment props",
        "Failed to load the model list. Start ComfyUI first.": "Failed to load the model list. Start ComfyUI first.",
        "Failed to run single-image generation": "Failed to run single-image generation",
        "Failed to start run": "Failed to start run",
        "Failed to stop": "Failed to stop",
        "Fixed": "Fixed",
        "Fixed reference image": "Fixed reference image",
        "Generated image preview": "Generated image preview",
        "Generating from this tab ignores image-set selections and outputs a single image only.": "Generating from this tab ignores image-set selections and outputs a single image only.",
        "Generation metadata": "Generation metadata",
        "Global Negative": "Global negative",
        "Global Positive": "Global positive",
        "Global prompts": "Global prompts",
        "Groups": "Groups",
        "Height": "Height",
        "Idle": "Idle",
        "Image input": "Image input",
        "Image preview": "Image preview",
        "Image set settings": "Image set settings",
        "Increment": "Increment",
        "Index": "Index",
        "Items": "Items",
        "Light": "Light",
        "Mode": "Mode",
        "Model": "Model",
        "Model list refreshed": "Model list refreshed",
        "Model parameters": "Model parameters",
        "Model selection": "Model selection",
        "Model strength": "Model strength",
        "Model/LoRA model": "Model/LoRA model",
        "Model/UNET": "Model/UNET",
        "Negative": "Negative",
        "Negative prompt": "Negative prompt",
        "New item saved": "New item saved",
        "No displayable generation-metadata sections were found in this image.": "No displayable generation-metadata sections were found in this image.",
        "No image generated yet. The latest result appears after single-image generation finishes.": "No image generated yet. The latest result appears after single-image generation finishes.",
        "No image has been loaded. Generation metadata appears after an image is loaded.": "No image has been loaded. Generation metadata appears after an image is loaded.",
        "No image selected": "No image selected",
        "No items": "No items",
        "No previous generated image yet.": "No previous generated image yet.",
        "None": "None",
        "NSFW Display / Invitation": "NSFW display/invitation",
        "NSFW Hands / Feet / Breast Interaction": "NSFW hands/feet/breast",
        "NSFW Lying Positions": "NSFW lying positions",
        "NSFW Oral Interaction": "NSFW oral interaction",
        "NSFW Riding / Seated": "NSFW riding/seated",
        "NSFW Side-Lying / Supported": "NSFW side/support",
        "NSFW Solo / Toys": "NSFW solo/toys",
        "NSFW Standing / Lifted": "NSFW standing/lifted",
        "Objects": "Objects",
        "Other": "Other",
        "Other data": "Other data",
        "Outfits": "Outfits",
        "Outfits / Objects": "Outfits / Objects",
        "Output every variation": "Output every variation",
        "Parameters": "Parameters",
        "Parse failed:": "Parse failed: ",
        "Parse image": "Parse image",
        "Parsing image metadata...": "Parsing image metadata...",
        "Positive": "Positive",
        "Positive prompt": "Positive prompt",
        "Previous generated image": "Previous generated image",
        "Progress": "Progress",
        "Prompt": "Prompt",
        "Prompt guidance/CFG": "Prompt guidance/CFG",
        "Random": "Random",
        "Reads ComfyUI and parameter metadata embedded in PNG files.": "Reads ComfyUI and parameter metadata embedded in PNG files.",
        "Reference image": "Reference image",
        "Reference image preview": "Reference image preview",
        "Refresh model list": "Refresh model list",
        "Rename": "Rename",
        "Rename preset": "Rename preset",
        "Resource usage": "Resource usage",
        "Run count": "Run count",
        "Running": "Running",
        "Sampler": "Sampler",
        "Scheduler": "Scheduler",
        "Search actions": "Search actions",
        "Search characters": "Search characters",
        "Search data": "Search data",
        "Search objects": "Search objects",
        "Search outfits": "Search outfits",
        "sec/image": "sec/image",
        "Seconds per image": "Seconds per image",
        "Seed": "Seed",
        "Seed mode": "Seed mode",
        "Select all": "Select all",
        "Select all objects": "Select all objects",
        "Select all outfits": "Select all outfits",
        "Select background": "Select background",
        "Select character": "Select character",
        "Select emotion / action": "Select emotion / action",
        "Select object": "Select object",
        "Select outfit": "Select outfit",
        "Select view": "Select view",
        "SFW Emotion / Action": "SFW emotion/action",
        "Single image output preview": "Single image output preview",
        "Start ComfyUI first": "Start ComfyUI first",
        "Start run": "Start run",
        "Status": "Status",
        "Steps": "Steps",
        "Stop": "Stop",
        "Text encoder/CLIP": "Text encoder/CLIP",
        "Text strength": "Text strength",
        "The parameter and prompt edits below sync directly with Model parameters and the Data editor database.": "The parameter and prompt edits below sync directly with Model parameters and the Data editor database.",
        "This field is for visual comparison only and is not used for generation.": "This field is for visual comparison only and is not used for generation.",
        "Total images this run": "Total images this run",
        "Traditional Chinese": "Traditional Chinese",
        "Tuning comparison": "Tuning comparison",
        "Uncategorized": "Uncategorized",
        "Unknown": "Unknown",
        "Untitled": "Untitled",
        "Upscale model": "Upscale model",
        "Upscale scale": "Upscale scale",
        "Using existing JSON": "Using existing JSON",
        "VAE": "VAE",
        "Variation prompt": "Variation prompt",
        "View": "View",
        "View / Background / Global prompts": "View / Background / Global prompts",
        "Width": "Width",
        "• Custom prompt: when the custom field is enabled, this field is appended to each item.": "• Custom prompt: when the custom field is enabled, this field is appended to each item.",
        "• Enable custom field: when checked, inserts the custom field from Emotion / Action into the prompt.": "• Enable custom field: when checked, inserts the custom field from Emotion / Action into the prompt.",
        "• Image filename format:": "• Image filename format:",
        "• Key: final output filename.": "• Key: final output filename.",
        "• Negative prompt: each item has its own negative prompt; it is inserted only when that item is selected.": "• Negative prompt: each item has its own negative prompt; it is inserted only when that item is selected.",
        "• Variation prompt: separate entries with Enter. When random variation is enabled, one line is randomly inserted.": "• Variation prompt: separate entries with Enter. When random variation is enabled, one line is randomly inserted.",
        "한국어": "한국어"
      },
      "ko": {
        ": Appended directly to the image prompt. When multiple objects are selected, all selected object prompts are inserted into every image; they do not increase the loop multiplier like characters, outfits, and actions.": ": 이미지 프롬프트에 직접 추가됩니다. 여러 오브젝트를 선택하면 선택한 모든 오브젝트 프롬프트가 모든 이미지에 삽입되며, 캐릭터 / 의상 / 감정 동작처럼 반복 배수에 포함되지 않습니다.",
        "Add": "추가",
        "Add item": "항목 추가",
        "Anima Image Set Generator": "Anima 이미지 세트 생성기",
        "Background": "배경",
        "Category": "분류",
        "Changes saved": "변경 사항이 저장되었습니다",
        "Characters": "캐릭터",
        "Checking ComfyUI...": "ComfyUI 확인 중...",
        "Clear all": "모두 해제",
        "Clear objects": "오브젝트 선택 해제",
        "Clear outfits": "의상 선택 해제",
        "Click to select an image, or drag an AI image into this area.": "이미지를 선택하거나 AI 이미지를 이 영역으로 드래그하세요.",
        "Click to select an image, or drag the comparison image into this area.": "이미지를 선택하거나 비교할 이미지를 이 영역으로 드래그하세요.",
        "ComfyUI connected": "ComfyUI 연결됨",
        "Custom prompt": "사용자 지정 프롬프트",
        "Dark": "다크",
        "Data editor": "데이터 편집",
        "Data parsing": "생성 정보 파싱",
        "Database": "데이터베이스",
        "Database mapping": "데이터베이스 매핑",
        "Delete": "삭제",
        "Denoise": "디노이즈",
        "Display name": "표시 이름",
        "Do not use": "사용 안 함",
        "Drag to sort": "드래그하여 정렬",
        "Drop image": "이미지 놓기",
        "Edit": "편집",
        "Emotion / Action": "감정 / 동작",
        "Enable custom field": "사용자 지정 필드 사용",
        "Enable custom prompt": "사용자 지정 프롬프트 사용",
        "Enable global negative prompt": "공통 네거티브 사용",
        "Enable global positive prompt": "공통 포지티브 사용",
        "Enable random variation": "랜덤 변형 사용",
        "Enable variation prompt": "변형 프롬프트 사용",
        "English": "English",
        "Equipment / Props": "장비/소품",
        "Failed to load the model list. Start ComfyUI first.": "모델 목록을 불러오지 못했습니다. 먼저 ComfyUI를 실행하세요.",
        "Failed to run single-image generation": "단일 이미지 생성 실행 실패",
        "Failed to start run": "실행 시작 실패",
        "Failed to stop": "중지 실패",
        "Fixed": "고정",
        "Fixed reference image": "고정 참조 이미지",
        "Generated image preview": "생성 이미지 미리보기",
        "Generating from this tab ignores image-set selections and outputs a single image only.": "이 탭에서 생성하면 이미지 세트 선택을 무시하고 단일 이미지만 출력합니다.",
        "Generation metadata": "생성 정보",
        "Global Negative": "공통 네거티브",
        "Global Positive": "공통 포지티브",
        "Global prompts": "공통 프롬프트",
        "Groups": "그룹",
        "Height": "높이",
        "Idle": "대기 중",
        "Image input": "이미지 입력",
        "Image preview": "이미지 미리보기",
        "Image set settings": "이미지 세트 설정",
        "Increment": "순차 증가",
        "Index": "번호",
        "Items": "항목",
        "Light": "라이트",
        "Mode": "모드",
        "Model": "모델",
        "Model list refreshed": "모델 목록이 새로 고침되었습니다",
        "Model parameters": "모델 파라미터",
        "Model selection": "모델 선택",
        "Model strength": "모델 강도",
        "Model/LoRA model": "모델/LoRA 모델",
        "Model/UNET": "모델/UNET",
        "Negative": "네거티브",
        "Negative prompt": "네거티브 프롬프트",
        "New item saved": "새 항목이 저장되었습니다",
        "No displayable generation-metadata sections were found in this image.": "이 이미지에서 표시할 생성 정보 섹션을 찾지 못했습니다.",
        "No image generated yet. The latest result appears after single-image generation finishes.": "아직 생성된 이미지가 없습니다. 단일 이미지 생성이 완료되면 최신 결과가 표시됩니다.",
        "No image has been loaded. Generation metadata appears after an image is loaded.": "아직 이미지를 불러오지 않았습니다. 이미지를 불러오면 생성 정보가 표시됩니다.",
        "No image selected": "선택된 이미지 없음",
        "No items": "항목 없음",
        "No previous generated image yet.": "이전 생성 이미지가 아직 없습니다.",
        "None": "없음",
        "NSFW Display / Invitation": "NSFW 노출/유도",
        "NSFW Hands / Feet / Breast Interaction": "NSFW 손/발/가슴 상호작용",
        "NSFW Lying Positions": "NSFW 누운 자세",
        "NSFW Oral Interaction": "NSFW 구강 상호작용",
        "NSFW Riding / Seated": "NSFW 올라탄/앉은 자세",
        "NSFW Side-Lying / Supported": "NSFW 옆으로 누운/지탱한 자세",
        "NSFW Solo / Toys": "NSFW 솔로/토이",
        "NSFW Standing / Lifted": "NSFW 선 자세/들어 올림",
        "Objects": "오브젝트",
        "Other": "기타",
        "Other data": "기타 데이터",
        "Outfits": "의상",
        "Outfits / Objects": "의상 / 오브젝트",
        "Output every variation": "모든 변형 출력",
        "Parameters": "파라미터",
        "Parse failed:": "파싱 실패: ",
        "Parse image": "이미지 파싱",
        "Parsing image metadata...": "이미지 정보를 파싱하는 중...",
        "Positive": "포지티브",
        "Positive prompt": "포지티브 프롬프트",
        "Previous generated image": "이전 생성 이미지",
        "Progress": "진행률",
        "Prompt": "프롬프트",
        "Prompt guidance/CFG": "프롬프트 가이던스/CFG",
        "Random": "랜덤",
        "Reads ComfyUI and parameter metadata embedded in PNG files.": "PNG에 내장된 ComfyUI 및 파라미터 메타데이터를 읽습니다.",
        "Reference image": "참조 이미지",
        "Reference image preview": "참조 이미지 미리보기",
        "Refresh model list": "모델 목록 새로 고침",
        "Rename": "이름 변경",
        "Rename preset": "프리셋 이름 변경",
        "Resource usage": "리소스 사용량",
        "Run count": "실행 횟수",
        "Running": "실행 중",
        "Sampler": "샘플러",
        "Scheduler": "스케줄러",
        "Search actions": "동작 검색",
        "Search characters": "캐릭터 검색",
        "Search data": "데이터 검색",
        "Search objects": "오브젝트 검색",
        "Search outfits": "의상 검색",
        "sec/image": "초/장",
        "Seconds per image": "이미지당 소요 시간",
        "Seed": "시드",
        "Seed mode": "시드 모드",
        "Select all": "모두 선택",
        "Select all objects": "오브젝트 모두 선택",
        "Select all outfits": "의상 모두 선택",
        "Select background": "배경 선택",
        "Select character": "캐릭터 선택",
        "Select emotion / action": "감정 / 동작 선택",
        "Select object": "오브젝트 선택",
        "Select outfit": "의상 선택",
        "Select view": "시점 선택",
        "SFW Emotion / Action": "SFW 감정/동작",
        "Single image output preview": "단일 이미지 출력 미리보기",
        "Start ComfyUI first": "먼저 ComfyUI를 실행하세요",
        "Start run": "실행 시작",
        "Status": "상태",
        "Steps": "스텝",
        "Stop": "중지",
        "Text encoder/CLIP": "텍스트 인코더/CLIP",
        "Text strength": "텍스트 강도",
        "The parameter and prompt edits below sync directly with Model parameters and the Data editor database.": "아래 파라미터와 프롬프트 변경 사항은 모델 파라미터 및 데이터 편집 데이터베이스와 바로 동기화됩니다.",
        "This field is for visual comparison only and is not used for generation.": "이 항목은 시각적 비교용이며 이미지 생성에는 사용되지 않습니다.",
        "Total images this run": "이번 실행 총 이미지 수",
        "Traditional Chinese": "번체 중국어",
        "Tuning comparison": "튜닝 비교",
        "Uncategorized": "미분류",
        "Unknown": "알 수 없음",
        "Untitled": "이름 없음",
        "Upscale model": "업스케일 모델",
        "Upscale scale": "업스케일 배율",
        "Using existing JSON": "기존 JSON 사용 중",
        "VAE": "VAE",
        "Variation prompt": "변형 프롬프트",
        "View": "시점",
        "View / Background / Global prompts": "시점 / 배경 / 공통 프롬프트",
        "Width": "너비",
        "• Custom prompt: when the custom field is enabled, this field is appended to each item.": "• 사용자 지정 프롬프트: 사용자 지정 필드를 사용하면 각 항목에 이 필드의 내용이 추가됩니다.",
        "• Enable custom field: when checked, inserts the custom field from Emotion / Action into the prompt.": "• 사용자 지정 필드 사용: 체크하면 감정 / 동작의 사용자 지정 필드가 프롬프트에 삽입됩니다.",
        "• Image filename format:": "• 이미지 파일명 형식:",
        "• Key: final output filename.": "• Key 값: 최종 출력 파일명입니다.",
        "• Negative prompt: each item has its own negative prompt; it is inserted only when that item is selected.": "• 네거티브 프롬프트: 각 항목에 개별 네거티브 프롬프트를 설정합니다. 해당 항목이 선택될 때만 삽입됩니다.",
        "• Variation prompt: separate entries with Enter. When random variation is enabled, one line is randomly inserted.": "• 변형 프롬프트: Enter로 줄을 구분합니다. 랜덤 변형을 사용하면 한 줄을 무작위로 골라 삽입합니다.",
        "한국어": "한국어"
      }
    };
    const UI_LANGS = ["en", "zh-Hant", "ko"];
    const UI_THEMES = ["light", "dark"];
    let currentLanguage = localStorage.getItem("anima_language_clean") || "en";
    let currentTheme = localStorage.getItem("anima_theme_clean") || "dark";
    const i18nTextSources = new WeakMap();

    function uiText(source) {
      const table = UI_TRANSLATIONS[currentLanguage] || UI_TRANSLATIONS["zh-Hant"];
      return table[source] || source;
    }

    function uiRuntimeText(value) {
      let text = String(value || "");
      const table = UI_TRANSLATIONS[currentLanguage] || UI_TRANSLATIONS["zh-Hant"];
      if (table[text]) return table[text];
      ["sec/image", "Parse failed:"].forEach((source) => {
        if (table[source]) text = text.split(source).join(table[source]);
      });
      return text;
    }

    function sourceForText(value) {
      const source = String(value || "").trim();
      return Object.prototype.hasOwnProperty.call(UI_TRANSLATIONS["zh-Hant"], source) ? source : "";
    }

    function translateTextNode(node) {
      const parent = node.parentElement;
      if (!parent || ["SCRIPT", "STYLE", "TEXTAREA", "PRE", "CODE"].includes(parent.tagName)) return;
      const raw = node.nodeValue || "";
      const trimmed = raw.trim();
      if (!trimmed) return;
      let source = i18nTextSources.get(node);
      if (!source) {
        source = sourceForText(trimmed);
        if (!source) return;
        i18nTextSources.set(node, source);
      }
      const prefix = raw.match(/^\s*/)?.[0] || "";
      const suffix = raw.match(/\s*$/)?.[0] || "";
      node.nodeValue = `${prefix}${uiText(source)}${suffix}`;
    }

    function translateAttributes(root = document.body) {
      const attrs = ["placeholder", "title", "alt", "aria-label"];
      const nodes = [root, ...root.querySelectorAll("*")].filter(Boolean);
      nodes.forEach((el) => {
        attrs.forEach((attr) => {
          if (!el.hasAttribute || !el.hasAttribute(attr)) return;
          const dataName = `i18n${attr.replace(/(^|-)([a-z])/g, (_m, _d, ch) => ch.toUpperCase())}Source`;
          let source = el.dataset?.[dataName];
          if (!source) {
            source = sourceForText(el.getAttribute(attr));
            if (!source || !el.dataset) return;
            el.dataset[dataName] = source;
          }
          el.setAttribute(attr, uiText(source));
        });
      });
    }

    function applyI18n(root = document.body) {
      if (!root) return;
      if (!UI_LANGS.includes(currentLanguage)) currentLanguage = "zh-Hant";
      document.documentElement.lang = currentLanguage;
      document.title = uiText("Anima Image Set Generator");
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      for (let node = walker.nextNode(); node; node = walker.nextNode()) translateTextNode(node);
      translateAttributes(root);
      updateHeaderControls();
    }

    function updateHeaderControls() {
      document.querySelectorAll("[data-lang]").forEach((button) => button.classList.toggle("active", button.dataset.lang === currentLanguage));
      document.querySelectorAll("[data-theme]").forEach((button) => button.classList.toggle("active", button.dataset.theme === currentTheme));
    }

    function setLanguage(lang) {
      if (!UI_LANGS.includes(lang)) return;
      currentLanguage = lang;
      localStorage.setItem("anima_language_clean", lang);
      applyI18n();
      updateComfyStatus().catch(() => {});
      updateRunStatus().catch(() => {});
    }

    function applyTheme(theme) {
      if (!UI_THEMES.includes(theme)) theme = "dark";
      currentTheme = theme;
      localStorage.setItem("anima_theme_clean", theme);
      document.body.classList.toggle("theme-light", theme === "light");
      document.body.classList.toggle("theme-dark", theme === "dark");
      updateHeaderControls();
    }

    function bindUiChromeControls() {
      document.querySelectorAll("[data-lang]").forEach((button) => button.onclick = () => setLanguage(button.dataset.lang));
      document.querySelectorAll("[data-theme]").forEach((button) => button.onclick = () => applyTheme(button.dataset.theme));
      applyTheme(currentTheme);
      applyI18n();
    }

    const GLOBAL_SECTIONS = {
      global_positive: "Global Positive",
      global_negative: "Global Negative"
    };
    const ACTION_GROUP_LABELS = {
      0: "SFW Emotion / Action",
      1: "SFW Emotion / Action",
      2: "SFW Emotion / Action",
      3: "NSFW Display / Invitation",
      4: "NSFW Solo / Toys",
      5: "NSFW Oral Interaction",
      6: "NSFW Hands / Feet / Breast Interaction",
      7: "NSFW Lying Positions",
      8: "NSFW Riding / Seated",
      9: "NSFW Standing / Lifted",
      10: "NSFW Side-Lying / Supported"
    };
    const DEFAULT_GROUP_LABELS = {
      characters: "Characters",
      outfits: "Outfits",
      objects: "Equipment / Props",
      actions: "SFW Emotion / Action",
      angles: "View",
      backgrounds: "Background"
    };

    async function api(path, options = {}) {
      const response = await fetch(path, {
        headers: {"Content-Type": "application/json"},
        ...options
      });
      const data = await response.json();
      if (!response.ok || data.ok === false) throw new Error(data.error || response.statusText);
      return data;
    }

    function activeModelPreset() { return config.model_presets[config.active_model_preset]; }
    function activeLoopPreset() { return library.loop_presets[config.active_loop_preset]; }
    function loopPresetName(index) {
      return library.loop_presets?.[index]?.name || `Preset ${index + 1}`;
    }

    function setMessage(message) {
      const logs = $("logs");
      if (!logs) return;
      const previous = logs.textContent ? "\n" + logs.textContent : "";
      logs.textContent = uiRuntimeText(message) + previous;
    }

    function syncModelInputsFromDom() {
      if (!config || !Array.isArray(config.model_presets)) return;
      const preset = activeModelPreset();
      const s = preset?.settings;
      if (!s) return;
      const singleMode = activeTabName() === "single";
      const ids = singleMode
        ? {
            unet: "singleUnetName", clip: "singleClipName", vae: "singleVaeName",
            sampler: "singleSamplerName", scheduler: "singleSchedulerName", upscale: "singleUpscaleModel",
            width: "singleWidth", height: "singleHeight", steps: "singleSteps", cfg: "singleCfg",
            denoise: "singleDenoise", seed: "singleSeed", seedMode: "singleSeedMode", upscaleScale: "singleUpscaleScale"
          }
        : {
            unet: "unetName", clip: "clipName", vae: "vaeName",
            sampler: "samplerName", scheduler: "schedulerName", upscale: "upscaleModel",
            width: "width", height: "height", steps: "steps", cfg: "cfg",
            denoise: "denoise", seed: "seed", seedMode: "seedMode", upscaleScale: "upscaleScale"
          };
      const read = (id) => { const el = $(id); return el ? el.value : undefined; };
      const readNumber = (id, fallback) => {
        const raw = read(id);
        if (raw === undefined) return fallback;
        if (String(raw).trim() === "") return "";
        const value = Number(raw);
        return Number.isFinite(value) ? value : fallback;
      };
      const unet = read(ids.unet);
      const clip = read(ids.clip);
      const vae = read(ids.vae);
      const sampler = read(ids.sampler);
      const scheduler = read(ids.scheduler);
      const upscale = read(ids.upscale);
      if (unet !== undefined) s.unet_name = unet;
      if (clip !== undefined) s.clip_name = clip;
      if (vae !== undefined) s.vae_name = vae;
      if (sampler !== undefined) s.sampler_name = sampler;
      if (scheduler !== undefined) s.scheduler = scheduler;
      if (upscale !== undefined) ensureUpscale(s).model_name = upscale;
      s.width = readNumber(ids.width, s.width);
      s.height = readNumber(ids.height, s.height);
      s.steps = readNumber(ids.steps, s.steps);
      s.cfg = readNumber(ids.cfg, s.cfg);
      s.denoise = readNumber(ids.denoise, s.denoise ?? "");
      s.seed = readNumber(ids.seed, s.seed);
      const seedMode = read(ids.seedMode);
      if (seedMode !== undefined) s.seed_mode = seedMode;
      ensureUpscale(s).scale_by = readNumber(ids.upscaleScale, s.upscale?.scale_by ?? "");
    }

    function currentModelOverrideForRun() {
      syncModelInputsFromDom();
      const preset = activeModelPreset();
      return {
        active_model_preset: config.active_model_preset,
        settings: JSON.parse(JSON.stringify(preset?.settings || {}))
      };
    }

    function debounceSaveConfig() {
      clearTimeout(configSaveTimer);
      configSaveTimer = setTimeout(() => saveConfig(), 350);
    }

    function debounceSaveLibrary() {
      clearTimeout(librarySaveTimer);
      librarySaveTimer = setTimeout(saveLibraryData, 350);
    }

    async function saveConfig(options = {}) {
      try {
        syncModelInputsFromDom();
        await api("/api/config", {method: "POST", body: JSON.stringify(config)});
        return true;
      } catch (err) {
        const message = "Failed to save settings: " + err.message;
        $("logs").textContent = message;
        if (options.raise) throw new Error(message);
        return false;
      }
    }

    async function saveLibraryData() {
      try {
        await api("/api/library", {method: "POST", body: JSON.stringify(library)});
      } catch (err) {
        $("logs").textContent = "Failed to save database: " + err.message;
      }
    }

    function sortedItems(section) {
      return Object.entries(library[section]).sort((a, b) => {
        const an = a[1].number || "9999";
        const bn = b[1].number || "9999";
        return an.localeCompare(bn, undefined, {numeric: true}) || a[0].localeCompare(b[0]);
      });
    }

    function label(record, key) {
      return record.name || record.display_name || record.zh_name || key;
    }

    function defaultActionGroupTag(record) {
      const sortGroup = Number(record.sort_group ?? 9999);
      return ACTION_GROUP_LABELS[sortGroup] || "Other";
    }

    function normalizeGroupLabel(value) {
      return String(value || "").replaceAll("adult", "NSFW").trim();
    }

    function ensureGroups(section) {
      if (!library.groups) library.groups = {};
      if (!library.groups[section]) library.groups[section] = {};
      const groups = library.groups[section];
      Object.entries(groups).forEach(([key, group]) => {
        group.name = normalizeGroupLabel(group.name || group.display_name || group.name || key);
        delete group.key;
        delete group.display_name;
      });
      const records = library[section] || {};
      Object.values(records).forEach((record) => {
        if (!record.group) {
          record.group = record.group_key || (section === "objects" ? "equipment" : "default");
          if (section === "actions" && !record.group_key) record.group = safeKey(actionGroupTag(record));
        }
        record.group = safeKey(record.group);
        const legacyGroupTag = record.group_tag;
        record.name = record.name || record.display_name || record.zh_name || "Untitled";
        delete record.key;
        delete record.zh_name;
        delete record.display_name;
        delete record.group_key;
        delete record.group_tag;
        delete record.sort_group;
        delete record.sort_category;
        if (!groups[record.group]) {
          groups[record.group] = {
            name: normalizeGroupLabel(legacyGroupTag || DEFAULT_GROUP_LABELS[section] || "Uncategorized"),
            sort_index: Object.keys(groups).length + 1
          };
        }
      });
      if (!Object.keys(groups).length) {
        const key = section === "objects" ? "equipment" : "default";
        groups[key] = {name: DEFAULT_GROUP_LABELS[section] || "Uncategorized", sort_index: 1};
      }
      return groups;
    }

    function groupEntries(section) {
      const groups = ensureGroups(section);
      return Object.entries(groups).sort((a, b) => {
        const ai = Number(a[1].sort_index ?? 9999);
        const bi = Number(b[1].sort_index ?? 9999);
        return ai - bi || groupLabel(section, a[0]).localeCompare(groupLabel(section, b[0]));
      });
    }

    function groupLabel(section, groupKey, record = null) {
      const group = library.groups?.[section]?.[groupKey];
      const raw = group?.name || group?.display_name || record?.group_tag || DEFAULT_GROUP_LABELS[section] || groupKey || "Uncategorized";
      return normalizeGroupLabel(raw);
    }

    function groupSortIndex(section, groupKey) {
      const group = ensureGroups(section)[groupKey];
      const index = Number(group?.sort_index);
      return Number.isFinite(index) ? index : 9999;
    }

    function recordKeysForGroup(section, groupKey) {
      return sortedRecordEntries(library[section] || {}, section)
        .filter(([_key, record]) => recordGroupKey(section, record) === groupKey)
        .map(([key]) => key);
    }

    function nextRecordSortIndex(section, groupKey) {
      return Math.max(
        0,
        ...Object.values(library[section] || {})
          .filter((record) => recordGroupKey(section, record) === groupKey)
          .map((record) => Number(record.sort_index || 0))
          .filter((index) => Number.isFinite(index))
      );
    }

    function applyRecordOrderFields(section, record, groupKey, sortIndex = null) {
      record.group = groupKey;
      delete record.key;
      delete record.zh_name;
      delete record.display_name;
      delete record.group_key;
      delete record.group_tag;
      delete record.sort_group;
      delete record.sort_category;
      if (sortIndex !== null) record.sort_index = sortIndex;
      else if (!Number.isFinite(Number(record.sort_index))) {
        record.sort_index = nextRecordSortIndex(section, groupKey) + 1;
      }
    }

    function reindexRecordsInGroup(section, groupKey, orderedKeys = null) {
      const currentKeys = recordKeysForGroup(section, groupKey);
      const currentSet = new Set(currentKeys);
      const keys = uniqueKeys([...(orderedKeys || []), ...currentKeys]).filter((key) => currentSet.has(key));
      keys.forEach((key, index) => {
        const record = library[section]?.[key];
        if (record && recordGroupKey(section, record) === groupKey) {
          applyRecordOrderFields(section, record, groupKey, index + 1);
        }
      });
    }

    function reindexSectionRecordsByGroups(section) {
      groupEntries(section).forEach(([groupKey]) => reindexRecordsInGroup(section, groupKey));
    }

    function uniqueKeys(keys) {
      const seen = new Set();
      return (keys || []).filter((key) => {
        if (!key || seen.has(key)) return false;
        seen.add(key);
        return true;
      });
    }

    function reorderKeys(keys, sourceKey, targetKey, placeAfter) {
      const base = uniqueKeys(keys);
      if (sourceKey === targetKey || !base.includes(sourceKey) || !base.includes(targetKey)) return base;
      const ordered = base.filter((key) => key !== sourceKey);
      const targetIndex = ordered.indexOf(targetKey);
      if (targetIndex < 0) return base;
      ordered.splice(targetIndex + (placeAfter ? 1 : 0), 0, sourceKey);
      return uniqueKeys(ordered);
    }

    function mergeOrderedSubset(currentKeys, orderedSubsetKeys) {
      const current = uniqueKeys(currentKeys);
      const currentSet = new Set(current);
      const subset = uniqueKeys(orderedSubsetKeys).filter((key) => currentSet.has(key));
      if (!subset.length) return current;
      const subsetSet = new Set(subset);
      let subsetIndex = 0;
      return current.map((key) => subsetSet.has(key) ? subset[subsetIndex++] : key);
    }

    function dragPlaceAfter(event, target) {
      const rect = target.getBoundingClientRect();
      return event.clientY > rect.top + rect.height / 2;
    }

    function markDbDragEnded() {
      dbDragJustEnded = true;
      window.setTimeout(() => { dbDragJustEnded = false; }, 160);
    }

    function setDbItemContent(button, text, draggable = false) {
      button.innerHTML = "";
      if (draggable) {
        const handle = document.createElement("span");
        handle.className = "drag-handle";
        handle.textContent = "::";
        handle.title = uiText("Drag to sort");
        button.appendChild(handle);
      }
      const labelEl = document.createElement("span");
      labelEl.className = "db-item-label";
      labelEl.textContent = text;
      button.appendChild(labelEl);
    }

    function dbDragOrderFrom(container, dragScope) {
      if (!container) return [];
      return uniqueKeys(Array.from(container.children)
        .filter((child) => child?.dataset?.dbDragScope === dragScope && child.dataset.dbDragKey)
        .map((child) => child.dataset.dbDragKey));
    }

    function dbDragTargetFromPoint(clientX, clientY, container, dragScope, sourceEl) {
      if (!container || typeof document.elementFromPoint !== "function") return null;
      let target = document.elementFromPoint(clientX, clientY)?.closest?.(".db-item[data-db-drag-key]");
      if (target === sourceEl) {
        const hidden = sourceEl.style.pointerEvents;
        sourceEl.style.pointerEvents = "none";
        target = document.elementFromPoint(clientX, clientY)?.closest?.(".db-item[data-db-drag-key]");
        sourceEl.style.pointerEvents = hidden;
      }
      if (!target || target === sourceEl || target.parentElement !== container || target.dataset.dbDragScope !== dragScope) return null;
      return target;
    }

    function clearDbDragOver(container) {
      container?.querySelectorAll?.(".db-item.drag-over")?.forEach((item) => item.classList.remove("drag-over"));
    }

    function moveDbDraggedItem(event, container, dragScope) {
      const context = dbDragContext;
      if (!context || context.scope !== dragScope || context.parent !== container) return false;
      const sourceEl = context.element;
      if (!sourceEl || sourceEl.parentElement !== container) return false;
      event.preventDefault();
      const target = dbDragTargetFromPoint(event.clientX, event.clientY, container, dragScope, sourceEl);
      clearDbDragOver(container);
      if (!target) return true;
      target.classList.add("drag-over");
      const placeAfter = dragPlaceAfter(event, target);
      const reference = placeAfter ? target.nextElementSibling : target;
      if (reference !== sourceEl && sourceEl.nextElementSibling !== reference) {
        container.insertBefore(sourceEl, reference);
        context.moved = true;
      }
      return true;
    }

    function commitDbDragOrder() {
      const context = dbDragContext;
      if (!context || context.done) return false;
      const orderedKeys = dbDragOrderFrom(context.parent, context.scope);
      if (!orderedKeys.length || !orderedKeys.includes(context.key)) return false;
      const originalKeys = uniqueKeys(context.originalKeys || []);
      const unchanged = orderedKeys.length === originalKeys.length && orderedKeys.every((key, index) => key === originalKeys[index]);
      context.done = true;
      if (!unchanged) context.onReorder(context.key, "", false, orderedKeys);
      return !unchanged;
    }

    function cleanupDbPointerDrag(markEnded = true) {
      const context = dbDragContext;
      if (!context) return;
      if (context.moveHandler) document.removeEventListener("pointermove", context.moveHandler, true);
      if (context.upHandler) document.removeEventListener("pointerup", context.upHandler, true);
      if (context.cancelHandler) document.removeEventListener("pointercancel", context.cancelHandler, true);
      try { context.handle?.releasePointerCapture?.(context.pointerId); } catch (_err) {}
      context.element?.classList?.remove("dragging", "drag-over");
      context.parent?.classList?.remove("drag-sorting");
      clearDbDragOver(context.parent);
      dbDragContext = null;
      if (markEnded && context.active) markDbDragEnded();
    }

    function bindDbDragContainer(container, dragScope, onReorder) {
      if (!container) return;
      container._dbDragScope = dragScope;
      container._dbDragReorder = onReorder;
      if (container._dbDragOverHandler) container.removeEventListener("dragover", container._dbDragOverHandler);
      if (container._dbDropHandler) container.removeEventListener("drop", container._dbDropHandler);
      if (container._dbDragLeaveHandler) container.removeEventListener("dragleave", container._dbDragLeaveHandler);
      container._dbDragOverHandler = null;
      container._dbDropHandler = null;
      container._dbDragLeaveHandler = null;
    }

    function bindDbDragSort(button, key, onReorder, dragScope = "db-item") {
      button.draggable = false;
      button.classList.add("sortable");
      button.dataset.dbDragKey = key;
      button.dataset.dbDragScope = dragScope;
      const handle = button.querySelector(".drag-handle") || button;
      handle.addEventListener("pointerdown", (event) => {
        if (event.button !== 0 || dbDragContext) return;
        if (!applyDbEditor({rerender: false, silent: true})) return;
        const parent = button.parentElement;
        if (!parent) return;
        event.preventDefault();
        event.stopPropagation();
        dbDragContext = {
          scope: dragScope,
          key,
          element: button,
          parent,
          handle,
          pointerId: event.pointerId,
          startX: event.clientX,
          startY: event.clientY,
          onReorder,
          originalKeys: dbDragOrderFrom(parent, dragScope),
          moved: false,
          active: false,
          done: false,
          moveHandler: null,
          upHandler: null,
          cancelHandler: null,
        };
        try { handle.setPointerCapture?.(event.pointerId); } catch (_err) {}
        dbDragContext.moveHandler = (moveEvent) => {
          const context = dbDragContext;
          if (!context || context.pointerId !== moveEvent.pointerId) return;
          const movedFarEnough = Math.abs(moveEvent.clientY - context.startY) > 3 || Math.abs(moveEvent.clientX - context.startX) > 3;
          if (!context.active && !movedFarEnough) return;
          if (!context.active) {
            context.active = true;
            context.element.classList.add("dragging");
            context.parent.classList.add("drag-sorting");
          }
          moveDbDraggedItem(moveEvent, context.parent, context.scope);
        };
        dbDragContext.upHandler = (upEvent) => {
          const context = dbDragContext;
          if (!context || context.pointerId !== upEvent.pointerId) return;
          upEvent.preventDefault();
          if (context.active) commitDbDragOrder();
          cleanupDbPointerDrag(true);
        };
        dbDragContext.cancelHandler = (cancelEvent) => {
          const context = dbDragContext;
          if (!context || context.pointerId !== cancelEvent.pointerId) return;
          cleanupDbPointerDrag(true);
        };
        document.addEventListener("pointermove", dbDragContext.moveHandler, true);
        document.addEventListener("pointerup", dbDragContext.upHandler, true);
        document.addEventListener("pointercancel", dbDragContext.cancelHandler, true);
      });
    }

    function actionGroupTag(record) {
      const tag = normalizeGroupLabel(record.group_tag || record.group || "");
      if (tag) return tag;
      return defaultActionGroupTag(record);
    }

    function isGlobalSection(section) {
      return Object.prototype.hasOwnProperty.call(GLOBAL_SECTIONS, section);
    }

    function usesEditableKey(section) {
      return !isGlobalSection(section) && !["angles", "backgrounds"].includes(section);
    }

    function numericOrBlank(value) {
      if (value === undefined || value === null || String(value).trim() === "") return "";
      const number = Number(value);
      return Number.isFinite(number) ? number : "";
    }

    function positiveInt(value, fallback = 0) {
      const number = Math.trunc(Number(value));
      return Number.isFinite(number) && number > 0 ? number : fallback;
    }

    function selectedLibraryCount(section, selectedKeys) {
      const selected = new Set(selectedKeys || []);
      return Object.keys(library?.[section] || {}).filter((key) => selected.has(key)).length;
    }

    function randomPromptLines(record) {
      return String(record?.random_prompt || "").split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
    }

    function randomPromptChoiceCount(record) {
      return randomPromptLines(record).length;
    }

    function computeRawTotal() {
      const loop = activeLoopPreset().settings;
      const repeat = positiveInt(config.run.repeat_count, 1);
      const characters = selectedLibraryCount("characters", loop.characters);
      const outfits = selectedLibraryCount("outfits", loop.outfits);
      const selectedActions = new Set(loop.actions || []);
      const actionUnits = Object.entries(library?.actions || {}).reduce((total, [key, record]) => {
        if (!selectedActions.has(key)) return total;
        if (loop.include_random !== false && loop.random_prompt_mode === "all") {
          return total + Math.max(1, randomPromptChoiceCount(record));
        }
        return total + 1;
      }, 0);
      return characters * outfits * actionUnits * repeat;
    }

    function computeTotal() {
      const rawTotal = computeRawTotal();
      const startIndex = positiveInt(config.run.start_index, 1);
      const limit = positiveInt(config.run.limit, 0);
      const available = Math.max(0, rawTotal - startIndex + 1);
      return limit ? Math.min(available, limit) : available;
    }

    function renderPresetButtons(kind) {
      const holder = kind === "model" ? $("modelPresetButtons") : $("loopPresetButtons");
      const presets = kind === "model" ? config.model_presets : library.loop_presets;
      const active = kind === "model" ? config.active_model_preset : config.active_loop_preset;
      holder.innerHTML = "";
      presets.forEach((preset, index) => {
        const button = document.createElement("button");
        button.textContent = kind === "model" ? preset.name : loopPresetName(index);
        button.className = index === active ? `active ${kind}` : "";
        button.onclick = () => {
          if (kind === "model") config.active_model_preset = index;
          else config.active_loop_preset = index;
          debounceSaveConfig();
          renderAll();
        };
        holder.appendChild(button);
      });
    }

    function renderModelTab() {
      renderPresetButtons("model");
      const preset = activeModelPreset();
      const s = preset.settings;
      renderRequiredModelSelect("unetName", ["diffusion_models"], s.unet_name || "", (value) => { s.unet_name = value; debounceSaveConfig(); });
      renderRequiredModelSelect("clipName", ["text_encoders", "clip"], s.clip_name || "", (value) => { s.clip_name = value; debounceSaveConfig(); });
      renderRequiredModelSelect("vaeName", ["vae"], s.vae_name || "", (value) => { s.vae_name = value; debounceSaveConfig(); });
      renderModelSelect("samplerName", (modelLists._samplers || []).length ? modelLists._samplers : fallbackSamplers(), s.sampler_name || "", (value) => { s.sampler_name = value; debounceSaveConfig(); }, true, false);
      renderModelSelect("schedulerName", (modelLists._schedulers || []).length ? modelLists._schedulers : fallbackSchedulers(), s.scheduler || "", (value) => { s.scheduler = value; debounceSaveConfig(); }, true, false);
      renderOptionalModelSelect("upscaleModel", ["upscale_models"], s.upscale?.model_name || "", (value) => { ensureUpscale(s).model_name = value; debounceSaveConfig(); });
      $("upscaleScale").value = s.upscale?.scale_by ?? "";
      $("width").value = s.width;
      $("height").value = s.height;
      $("steps").value = s.steps;
      $("cfg").value = s.cfg;
      $("denoise").value = s.denoise ?? "";
      $("seed").value = s.seed;
      $("seedMode").value = s.seed_mode;
      $("loraRows").innerHTML = "";
      s.loras.forEach((lora, index) => {
        const row = document.createElement("div");
        row.className = "lora-row";
        lora.positive_prompt = lora.positive_prompt || "";
        lora.negative_prompt = lora.negative_prompt || "";
        row.classList.toggle("lora-disabled", !lora.enabled);
        row.innerHTML = `
          <input type="checkbox" ${lora.enabled ? "checked" : ""}>
          <label class="lora-field"><span>Model/LoRA model</span><select></select></label>
          <label class="lora-field"><span>Model strength</span><input type="number" step="0.05" value="${lora.strength_model}"></label>
          <label class="lora-field"><span>Text strength</span><input type="number" step="0.05" value="${lora.strength_clip}"></label>
          <label class="lora-field lora-prompt-field"><span>Positive</span><textarea>${escapeHtml(lora.positive_prompt)}</textarea></label>
          <label class="lora-field lora-prompt-field"><span>Negative</span><textarea>${escapeHtml(lora.negative_prompt)}</textarea></label>
        `;
        const inputs = row.querySelectorAll("input");
        const textareas = row.querySelectorAll("textarea");
        const select = row.querySelector("select");
        fillSelect(select, modelValues(["loras"]), lora.lora_name || "", true);
        inputs[0].onchange = () => {
          lora.enabled = inputs[0].checked;
          row.classList.toggle("lora-disabled", !lora.enabled);
          debounceSaveConfig();
        };
        select.onchange = () => { lora.lora_name = select.value; debounceSaveConfig(); };
        inputs[1].oninput = () => { lora.strength_model = numericOrBlank(inputs[1].value); debounceSaveConfig(); };
        inputs[2].oninput = () => { lora.strength_clip = numericOrBlank(inputs[2].value); debounceSaveConfig(); };
        textareas[0].oninput = () => { lora.positive_prompt = textareas[0].value; debounceSaveConfig(); };
        textareas[1].oninput = () => { lora.negative_prompt = textareas[1].value; debounceSaveConfig(); };
        $("loraRows").appendChild(row);
      });
    }

    function ensureUpscale(settings) {
      if (!settings.upscale) settings.upscale = {enabled: false, model_name: ""};
      return settings.upscale;
    }

    function singleSettings() {
      if (!config.single_image) {
        config.single_image = {
          source_mode: "previous",
          use_global_positive: false,
          use_global_negative: false,
          use_action_random_prompt: false,
          action_random_index: 1,
          use_action_custom_prompt: false,
          character: "",
          outfit: "",
          action: "",
          angle: "",
          background: "",
          object: ""
        };
      }
      const single = config.single_image;
      single.source_mode = single.source_mode || "previous";
      delete single.positive_prompt;
      delete single.negative_prompt;
      delete single.filename_prefix;
      if (single.use_global_positive === undefined) single.use_global_positive = false;
      if (single.use_global_negative === undefined) single.use_global_negative = false;
      if (single.use_action_random_prompt === undefined) single.use_action_random_prompt = false;
      if (single.use_action_custom_prompt === undefined) single.use_action_custom_prompt = false;
      single.action_random_index = positiveInt(single.action_random_index, 1);
      const ensureKey = (field, section, allowBlank = false) => {
        const records = library?.[section] || {};
        if (single[field] && records[single[field]]) return;
        const keys = Object.keys(records);
        single[field] = allowBlank ? (single[field] || "") : (keys[0] || "");
      };
      ensureKey("character", "characters");
      ensureKey("outfit", "outfits");
      ensureKey("action", "actions");
      ensureKey("angle", "angles");
      ensureKey("background", "backgrounds");
      ensureKey("object", "objects", true);
      return single;
    }

    function renderSinglePresetButtons() {
      const holder = $("singleModelPresetButtons");
      if (!holder) return;
      holder.innerHTML = "";
      config.model_presets.forEach((preset, index) => {
        const button = document.createElement("button");
        button.textContent = preset.name;
        button.className = index === config.active_model_preset ? "active model" : "";
        button.onclick = () => {
          config.active_model_preset = index;
          debounceSaveConfig();
          renderAll();
        };
        holder.appendChild(button);
      });
    }

    function renderLoraEditorRows(holderId, settings) {
      const holder = $(holderId);
      if (!holder) return;
      holder.innerHTML = "";
      if (!Array.isArray(settings.loras)) settings.loras = [];
      while (settings.loras.length < 5) {
        settings.loras.push({enabled: false, lora_name: "", strength_model: 0.8, strength_clip: 0.8, positive_prompt: "", negative_prompt: ""});
      }
      settings.loras.forEach((lora) => {
        const row = document.createElement("div");
        row.className = "lora-row";
        lora.positive_prompt = lora.positive_prompt || "";
        lora.negative_prompt = lora.negative_prompt || "";
        row.classList.toggle("lora-disabled", !lora.enabled);
        row.innerHTML = `
          <input type="checkbox" ${lora.enabled ? "checked" : ""}>
          <label class="lora-field"><span>Model/LoRA model</span><select></select></label>
          <label class="lora-field"><span>Model strength</span><input type="number" step="0.05" value="${lora.strength_model}"></label>
          <label class="lora-field"><span>Text strength</span><input type="number" step="0.05" value="${lora.strength_clip}"></label>
          <label class="lora-field lora-prompt-field"><span>Positive</span><textarea>${escapeHtml(lora.positive_prompt)}</textarea></label>
          <label class="lora-field lora-prompt-field"><span>Negative</span><textarea>${escapeHtml(lora.negative_prompt)}</textarea></label>
        `;
        const inputs = row.querySelectorAll("input");
        const textareas = row.querySelectorAll("textarea");
        const select = row.querySelector("select");
        fillSelect(select, modelValues(["loras"]), lora.lora_name || "", true);
        inputs[0].onchange = () => {
          lora.enabled = inputs[0].checked;
          row.classList.toggle("lora-disabled", !lora.enabled);
          debounceSaveConfig();
        };
        select.onchange = () => { lora.lora_name = select.value; debounceSaveConfig(); };
        inputs[1].oninput = () => { lora.strength_model = numericOrBlank(inputs[1].value); debounceSaveConfig(); };
        inputs[2].oninput = () => { lora.strength_clip = numericOrBlank(inputs[2].value); debounceSaveConfig(); };
        textareas[0].oninput = () => { lora.positive_prompt = textareas[0].value; debounceSaveConfig(); };
        textareas[1].oninput = () => { lora.negative_prompt = textareas[1].value; debounceSaveConfig(); };
        holder.appendChild(row);
      });
    }

    function singleRecord(section, key) {
      const records = library?.[section] || {};
      return records?.[key] || {};
    }

    function renderSingleActionSelect(single, forceOpen = false) {
      const select = $("singleActionSelect");
      if (!select) return;
      const filterInput = $("singleActionFilter");
      const filter = (filterInput?.value || "").trim().toLowerCase();
      const isFiltering = !!filter;
      let entries = sortedRecordEntries(library.actions || {}, "actions").filter(([key, record]) => {
        if (!filter) return true;
        const text = [
          key,
          label(record, key),
          record.name || "",
          record.display_name || "",
          record.group || "",
          record.prompt || "",
          record.negative_prompt || "",
          record.random_prompt || "",
          record.custom_prompt || "",
        ].join(" ").toLowerCase();
        return text.includes(filter);
      });
      if (!isFiltering && single.action && library.actions?.[single.action] && !entries.some(([key]) => key === single.action)) {
        entries = [[single.action, library.actions[single.action]], ...entries];
      }
      select.innerHTML = "";
      entries.forEach(([key, record]) => {
        const option = document.createElement("option");
        option.value = key;
        option.textContent = label(record, key);
        option.selected = key === single.action;
        select.appendChild(option);
      });
      const shouldOpen = forceOpen || isFiltering;
      if (shouldOpen) {
        select.size = String(Math.max(2, Math.min(entries.length || 1, 8)));
        select.classList.add("single-select-expanded");
        if (!entries.some(([key]) => key === single.action)) select.selectedIndex = -1;
      } else {
        select.size = 1;
        select.classList.remove("single-select-expanded");
      }
      select.onchange = () => {
        single.action = select.value;
        if (filterInput) filterInput.value = "";
        debounceSaveConfig();
        renderSinglePromptEditor();
      };
    }

    function renderSinglePromptEditor() {
      const single = singleSettings();
      $("singleUseGlobalPositive").checked = !!single.use_global_positive;
      $("singleUseGlobalNegative").checked = !!single.use_global_negative;
      $("singleGlobalPositive").value = library.defaults?.global_positive || "";
      $("singleGlobalNegative").value = library.defaults?.global_negative || "";

      renderSelect("singleAngleSelect", library.angles, single.angle, (value) => { single.angle = value; debounceSaveConfig(); renderSinglePromptEditor(); });
      renderSelect("singleBackgroundSelect", library.backgrounds, single.background, (value) => { single.background = value; debounceSaveConfig(); renderSinglePromptEditor(); });
      renderSelect("singleCharacterSelect", library.characters, single.character, (value) => { single.character = value; debounceSaveConfig(); renderSinglePromptEditor(); });
      renderSingleActionSelect(single);
      renderSelect("singleOutfitSelect", library.outfits, single.outfit, (value) => { single.outfit = value; debounceSaveConfig(); renderSinglePromptEditor(); });
      renderSelect("singleObjectSelect", library.objects || {}, single.object || "", (value) => { single.object = value; debounceSaveConfig(); renderSinglePromptEditor(); }, true);

      const angle = singleRecord("angles", single.angle);
      const background = singleRecord("backgrounds", single.background);
      const character = singleRecord("characters", single.character);
      const action = singleRecord("actions", single.action);
      const outfit = singleRecord("outfits", single.outfit);
      const objectRecord = single.object ? singleRecord("objects", single.object) : {};

      $("singleAnglePrompt").value = angle.prompt || "";
      $("singleAngleNegativePrompt").value = angle.negative_prompt || "";
      $("singleBackgroundPrompt").value = background.prompt || "";
      $("singleBackgroundNegativePrompt").value = background.negative_prompt || "";
      $("singleCharacterPrompt").value = character.prompt || "";
      $("singleCharacterNegativePrompt").value = character.negative_prompt || "";
      $("singleActionPrompt").value = action.prompt || "";
      $("singleActionNegativePrompt").value = action.negative_prompt || "";
      const actionRandomLines = randomPromptLines(action);
      const actionRandomCount = actionRandomLines.length;
      if (actionRandomCount) {
        single.action_random_index = Math.max(1, Math.min(positiveInt(single.action_random_index, 1), actionRandomCount));
      } else {
        single.action_random_index = 1;
      }
      $("singleActionRandomEnabled").checked = !!single.use_action_random_prompt;
      const randomIndexSelect = $("singleActionRandomIndex");
      randomIndexSelect.innerHTML = "";
      if (actionRandomCount) {
        for (let index = 1; index <= actionRandomCount; index += 1) {
          const option = document.createElement("option");
          option.value = String(index);
          option.textContent = String(index);
          option.selected = index === single.action_random_index;
          randomIndexSelect.appendChild(option);
        }
        randomIndexSelect.disabled = false;
      } else {
        const option = document.createElement("option");
        option.value = "1";
        option.textContent = uiText("None");
        randomIndexSelect.appendChild(option);
        randomIndexSelect.disabled = true;
      }
      $("singleActionRandomCount").textContent = actionRandomCount ? `/ ${actionRandomCount}` : "/ 0";
      $("singleActionRandomPrompt").value = single.use_action_random_prompt && actionRandomCount ? actionRandomLines[single.action_random_index - 1] : "";
      $("singleActionCustomEnabled").checked = !!single.use_action_custom_prompt;
      $("singleActionCustomPrompt").value = action.custom_prompt || "";
      $("singleOutfitPrompt").value = outfit.prompt || "";
      $("singleOutfitNegativePrompt").value = outfit.negative_prompt || "";
      $("singleObjectPrompt").value = objectRecord.prompt || "";
      $("singleObjectNegativePrompt").value = objectRecord.negative_prompt || "";
    }

    function bindSinglePromptLibraryFields() {
      const bindRecord = (section, field, inputId) => {
        const el = $(inputId);
        if (!el) return;
        el.oninput = () => {
          const key = singleSettings()[field];
          if (!key) return;
          const record = library[section]?.[key];
          if (!record) return;
          if (inputId.endsWith("NegativePrompt")) record.negative_prompt = el.value;
          else if (inputId === "singleActionRandomPrompt") record.random_prompt = el.value;
          else if (inputId === "singleActionCustomPrompt") record.custom_prompt = el.value;
          else record.prompt = el.value;
          debounceSaveLibrary();
        };
      };
      $("singleUseGlobalPositive").onchange = () => { singleSettings().use_global_positive = $("singleUseGlobalPositive").checked; debounceSaveConfig(); };
      $("singleUseGlobalNegative").onchange = () => { singleSettings().use_global_negative = $("singleUseGlobalNegative").checked; debounceSaveConfig(); };
      $("singleGlobalPositive").oninput = () => { library.defaults.global_positive = $("singleGlobalPositive").value; debounceSaveLibrary(); };
      $("singleGlobalNegative").oninput = () => { library.defaults.global_negative = $("singleGlobalNegative").value; debounceSaveLibrary(); };
      if ($("singleActionFilter")) $("singleActionFilter").oninput = () => {
        const hasFilter = $("singleActionFilter").value.trim().length > 0;
        renderSingleActionSelect(singleSettings(), hasFilter);
      };
      bindRecord("angles", "angle", "singleAnglePrompt");
      bindRecord("angles", "angle", "singleAngleNegativePrompt");
      bindRecord("backgrounds", "background", "singleBackgroundPrompt");
      bindRecord("backgrounds", "background", "singleBackgroundNegativePrompt");
      bindRecord("characters", "character", "singleCharacterPrompt");
      bindRecord("characters", "character", "singleCharacterNegativePrompt");
      bindRecord("actions", "action", "singleActionPrompt");
      bindRecord("actions", "action", "singleActionNegativePrompt");
      if ($("singleActionRandomEnabled")) $("singleActionRandomEnabled").onchange = () => {
        singleSettings().use_action_random_prompt = $("singleActionRandomEnabled").checked;
        debounceSaveConfig();
        renderSinglePromptEditor();
      };
      if ($("singleActionRandomIndex")) $("singleActionRandomIndex").onchange = () => {
        singleSettings().action_random_index = positiveInt($("singleActionRandomIndex").value, 1);
        debounceSaveConfig();
        renderSinglePromptEditor();
      };
      if ($("singleActionCustomEnabled")) $("singleActionCustomEnabled").onchange = () => {
        singleSettings().use_action_custom_prompt = $("singleActionCustomEnabled").checked;
        debounceSaveConfig();
      };
      bindRecord("actions", "action", "singleActionCustomPrompt");
      bindRecord("outfits", "outfit", "singleOutfitPrompt");
      bindRecord("outfits", "outfit", "singleOutfitNegativePrompt");
      bindRecord("objects", "object", "singleObjectPrompt");
      bindRecord("objects", "object", "singleObjectNegativePrompt");
    }

    function renderSingleTab() {
      if (!$("tab-single")) return;
      const single = singleSettings();
      const preset = activeModelPreset();
      const s = preset.settings;
      renderSinglePresetButtons();
      $("singleSourceMode").value = single.source_mode || "previous";
      renderRequiredModelSelect("singleUnetName", ["diffusion_models"], s.unet_name || "", (value) => { s.unet_name = value; debounceSaveConfig(); });
      renderRequiredModelSelect("singleClipName", ["text_encoders", "clip"], s.clip_name || "", (value) => { s.clip_name = value; debounceSaveConfig(); });
      renderRequiredModelSelect("singleVaeName", ["vae"], s.vae_name || "", (value) => { s.vae_name = value; debounceSaveConfig(); });
      renderModelSelect("singleSamplerName", (modelLists._samplers || []).length ? modelLists._samplers : fallbackSamplers(), s.sampler_name || "", (value) => { s.sampler_name = value; debounceSaveConfig(); }, true, false);
      renderModelSelect("singleSchedulerName", (modelLists._schedulers || []).length ? modelLists._schedulers : fallbackSchedulers(), s.scheduler || "", (value) => { s.scheduler = value; debounceSaveConfig(); }, true, false);
      renderOptionalModelSelect("singleUpscaleModel", ["upscale_models"], s.upscale?.model_name || "", (value) => { ensureUpscale(s).model_name = value; debounceSaveConfig(); });
      $("singleWidth").value = s.width;
      $("singleHeight").value = s.height;
      $("singleSteps").value = s.steps;
      $("singleCfg").value = s.cfg;
      $("singleDenoise").value = s.denoise ?? "";
      $("singleSeed").value = s.seed;
      $("singleSeedMode").value = s.seed_mode;
      $("singleUpscaleScale").value = s.upscale?.scale_by ?? "";
      renderSinglePromptEditor();
      renderLoraEditorRows("singleLoraRows", s);
      bindSinglePromptLibraryFields();
    }

    function setSingleSourceImage(file) {
      if (!file) return;
      const reader = new FileReader();
      reader.onload = () => {
        singleSourceImageData = String(reader.result || "");
        singleSourceFileName = file.name || "single_input.png";
        const zone = $("singleImageDropZone");
        if (zone) zone.classList.add("has-image");
        if ($("singleInputPreview")) $("singleInputPreview").src = singleSourceImageData;
        if ($("singleInputFileName")) $("singleInputFileName").textContent = singleSourceFileName;
      };
      reader.readAsDataURL(file);
    }

    function bindSingleImageInputs() {
      const dropZone = $("singleImageDropZone");
      const input = $("singleImageFileInput");
      if (!dropZone || !input) return;
      input.onchange = () => setSingleSourceImage(input.files?.[0]);
      ["dragenter", "dragover"].forEach((eventName) => {
        dropZone.addEventListener(eventName, (event) => {
          event.preventDefault();
          event.stopPropagation();
          dropZone.classList.add("drag-over");
        });
      });
      ["dragleave", "dragend", "drop"].forEach((eventName) => {
        dropZone.addEventListener(eventName, (event) => {
          event.preventDefault();
          event.stopPropagation();
          if (eventName !== "drop") dropZone.classList.remove("drag-over");
        });
      });
      dropZone.addEventListener("drop", (event) => {
        dropZone.classList.remove("drag-over");
        const file = Array.from(event.dataTransfer?.files || []).find((item) => item.type.startsWith("image/"));
        if (file) setSingleSourceImage(file);
      });
    }

    function clearSingleReferenceImage(message = uiText("No previous generated image yet.")) {
      singleSourceImageData = "";
      singleSourceFileName = "";
      const zone = $("singleImageDropZone");
      const preview = $("singleInputPreview");
      const filename = $("singleInputFileName");
      if (zone) zone.classList.remove("has-image");
      if (preview) preview.removeAttribute("src");
      if (filename) filename.textContent = message;
    }

    function renderSingleReferenceFromOutput(imageName) {
      if (!imageName) return;
      const sourceMode = $("singleSourceMode")?.value || singleSettings().source_mode || "previous";
      if (sourceMode !== "previous") return;
      const zone = $("singleImageDropZone");
      const preview = $("singleInputPreview");
      const filename = $("singleInputFileName");
      const imageUrl = `/api/comfy/view?name=${encodeURIComponent(imageName)}&cache=${Date.now()}`;
      singleSourceImageData = "";
      singleSourceFileName = imageName;
      if (zone) zone.classList.add("has-image");
      if (preview) preview.src = imageUrl;
      if (filename) filename.textContent = `${imageName} (previous)`;
    }

    function renderSingleOutputPreview(imageName) {
      if (!imageName) return;
      if (imageName === lastSinglePreviewName) return;
      lastSinglePreviewName = imageName;
      const panel = $("singleOutputPanel");
      const image = $("singleOutputPreview");
      if (!panel || !image) return;
      panel.classList.add("has-image");
      image.src = `/api/comfy/view?name=${encodeURIComponent(imageName)}&cache=${Date.now()}`;
      if ($("singleOutputFileName")) $("singleOutputFileName").textContent = imageName;
    }

    function bindSingleEditorInputs() {
      if (!$("singleSourceMode")) return;
      $("singleSourceMode").onchange = () => {
        singleSettings().source_mode = $("singleSourceMode").value;
        debounceSaveConfig();
        if ($("singleSourceMode").value === "previous") {
          if (lastSinglePreviewName) renderSingleReferenceFromOutput(lastSinglePreviewName);
          else clearSingleReferenceImage();
        }
      };
      $("singleWidth").oninput = () => { activeModelPreset().settings.width = numericOrBlank($("singleWidth").value); debounceSaveConfig(); renderBottom(); };
      $("singleHeight").oninput = () => { activeModelPreset().settings.height = numericOrBlank($("singleHeight").value); debounceSaveConfig(); renderBottom(); };
      $("singleSteps").oninput = () => { activeModelPreset().settings.steps = numericOrBlank($("singleSteps").value); debounceSaveConfig(); };
      $("singleCfg").oninput = () => { activeModelPreset().settings.cfg = numericOrBlank($("singleCfg").value); debounceSaveConfig(); };
      $("singleDenoise").oninput = () => { activeModelPreset().settings.denoise = numericOrBlank($("singleDenoise").value); debounceSaveConfig(); };
      $("singleSeed").oninput = () => { activeModelPreset().settings.seed = numericOrBlank($("singleSeed").value); debounceSaveConfig(); };
      $("singleSeedMode").onchange = () => { activeModelPreset().settings.seed_mode = $("singleSeedMode").value; debounceSaveConfig(); };
      $("singleUpscaleScale").oninput = () => { ensureUpscale(activeModelPreset().settings).scale_by = numericOrBlank($("singleUpscaleScale").value); debounceSaveConfig(); };
      $("singleRefreshModels").onclick = refreshModels;
    }


    function fallbackSamplers() {
      return ["euler_ancestral", "euler", "dpmpp_2m", "dpmpp_2m_sde", "dpmpp_3m_sde", "ddim"];
    }

    function fallbackSchedulers() {
      return ["normal", "karras", "exponential", "sgm_uniform", "simple", "ddim_uniform", "beta"];
    }

    function modelValues(folders) {
      return [...new Set(folders.flatMap((folder) => modelLists[folder] || []))];
    }

    function renderModelSelect(id, values, current, onChange, allowBlank = false, keepMissing = true) {
      const select = $(id);
      fillSelect(select, values, current, allowBlank, keepMissing);
      const selectedValue = select.value || "";
      if (selectedValue !== (current || "")) onChange(selectedValue);
      select.onchange = () => onChange(select.value);
    }

    function renderRequiredModelSelect(id, folders, current, onChange) {
      const values = modelValues(folders);
      renderModelSelect(id, values, current, onChange, true, values.length === 0);
    }

    function renderOptionalModelSelect(id, folders, current, onChange) {
      const values = modelValues(folders);
      renderModelSelect(id, values, current, onChange, true, values.length === 0);
    }

    function fillSelect(select, values, current, allowBlank = false, keepMissing = true) {
      const unique = [...new Set(values.filter(Boolean))];
      if (current && !unique.includes(current) && keepMissing) unique.unshift(current);
      select.innerHTML = "";
      if (allowBlank) {
        const blank = document.createElement("option");
        blank.value = "";
        blank.textContent = uiText("Do not use");
        blank.selected = !current || (!keepMissing && !unique.includes(current));
        select.appendChild(blank);
      }
      unique.forEach((value) => {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = value;
        option.selected = value === current;
        select.appendChild(option);
      });
    }

    function renderLoopTab() {
      renderPresetButtons("loop");
      const preset = activeLoopPreset();
      const s = preset.settings;
      renderSelect("angleSelect", library.angles, s.angle, (value) => { s.angle = value; debounceSaveLibrary(); renderAll(); });
      renderSelect("backgroundSelect", library.backgrounds, s.background, (value) => { s.background = value; debounceSaveLibrary(); renderAll(); });
      $("useGlobalPositive").checked = s.use_global_positive ?? false;
      $("useGlobalNegative").checked = s.use_global_negative ?? false;
      $("useCustomPrompt").checked = s.use_custom_prompt ?? false;
      $("includeRandom").checked = s.include_random ?? false;
      $("expandRandomPrompts").checked = s.random_prompt_mode === "all";
      $("expandRandomPrompts").disabled = !$("includeRandom").checked;
      renderChecks("characterChecks", "characterFilter", library.characters, s.characters);
      renderChecks("outfitChecks", "outfitFilter", library.outfits, s.outfits);
      if (!Array.isArray(s.objects)) s.objects = [];
      renderChecks("objectChecks", "objectFilter", library.objects || {}, s.objects, {section: "objects", includeTextFields: true});
      renderChecks("actionChecks", "actionFilter", library.actions, s.actions, {grouped: true, section: "actions"});
    }

    function renderSelect(id, records, selected, onChange, allowBlank = false) {
      const select = $(id);
      select.innerHTML = "";
      if (allowBlank) {
        const blank = document.createElement("option");
        blank.value = "";
        blank.textContent = uiText("Do not use");
        blank.selected = !selected;
        select.appendChild(blank);
      }
      sortedRecordEntries(records, id === "angleSelect" || id === "singleAngleSelect" ? "angles" : id === "backgroundSelect" || id === "singleBackgroundSelect" ? "backgrounds" : id === "singleActionSelect" ? "actions" : "").forEach(([key, record]) => {
        const option = document.createElement("option");
        option.value = key;
        option.textContent = label(record, key);
        option.selected = key === selected;
        select.appendChild(option);
      });
      select.onchange = () => onChange(select.value);
    }

    function sortedRecordEntries(records, section = "") {
      return Object.entries(records).sort((a, b) => {
        const ag = section ? groupSortIndex(section, recordGroupKey(section, a[1])) : 9999;
        const bg = section ? groupSortIndex(section, recordGroupKey(section, b[1])) : 9999;
        if (ag !== bg) return ag - bg;
        const ai = Number(a[1].sort_index ?? 9999);
        const bi = Number(b[1].sort_index ?? 9999);
        if (ai !== bi) return ai - bi;
        const an = a[1].number || "9999";
        const bn = b[1].number || "9999";
        const numberCompare = String(an).localeCompare(String(bn), undefined, {numeric: true});
        if (numberCompare !== 0) return numberCompare;
        const av = a[1].source_node || 999999;
        const bv = b[1].source_node || 999999;
        return av - bv || a[0].localeCompare(b[0]);
      });
    }

    function matchesFilter(record, key, filter, includeGroup = false, section = "", includeTextFields = false) {
      if (!filter) return true;
      const haystack = [
        label(record, key),
        key,
        section ? groupLabel(section, recordGroupKey(section, record), record) : "",
      ];
      if (includeTextFields) {
        haystack.push(
          record?.prompt || "",
          record?.negative_prompt || "",
          record?.random_prompt || "",
          record?.custom_prompt || "",
        );
      }
      return haystack.some((value) => String(value || "").toLowerCase().includes(filter));
    }

    function syncSelection(selectedKeys, keys, checked) {
      const keySet = new Set(keys);
      if (checked) {
        keys.forEach((key) => {
          if (!selectedKeys.includes(key)) selectedKeys.push(key);
        });
      } else {
        selectedKeys.splice(0, selectedKeys.length, ...selectedKeys.filter((item) => !keySet.has(item)));
      }
    }

    function renderCheckRow(key, record, selectedKeys, afterChange = null) {
      const row = document.createElement("label");
      row.className = "check-row";
      row.innerHTML = `<input type="checkbox" ${selectedKeys.includes(key) ? "checked" : ""}><span>${escapeHtml(label(record, key))}</span>`;
      const input = row.querySelector("input");
      input.onchange = () => {
        syncSelection(selectedKeys, [key], input.checked);
        debounceSaveLibrary();
        if (afterChange) afterChange();
        renderBottom();
      };
      return row;
    }

    function renderGroupedChecks(holder, entries, selectedKeys, section) {
      holder.classList.add("grouped");
      const groups = new Map();
      entries.forEach(([key, record]) => {
        const groupKey = recordGroupKey(section, record);
        const tag = groupLabel(section, groupKey, record);
        if (!groups.has(tag)) groups.set(tag, []);
        groups.get(tag).push([key, record]);
      });
      Array.from(groups.entries()).forEach(([groupName, items], groupIndex) => {
        const keys = items.map(([key]) => key);
        const selectedCount = keys.filter((key) => selectedKeys.includes(key)).length;
        const group = document.createElement("div");
        group.className = `check-group ${groupIndex % 2 === 0 ? "tone-a" : "tone-b"}`;
        const header = document.createElement("label");
        header.className = "check-group-header";
        header.innerHTML = `<input type="checkbox"><span>${escapeHtml(groupName)}</span><small>${selectedCount}/${keys.length}</small>`;
        const groupInput = header.querySelector("input");
        groupInput.checked = selectedCount === keys.length && keys.length > 0;
        groupInput.indeterminate = selectedCount > 0 && selectedCount < keys.length;
        groupInput.onchange = () => {
          syncSelection(selectedKeys, keys, groupInput.checked);
          debounceSaveLibrary();
          renderLoopTab();
          renderBottom();
        };
        const list = document.createElement("div");
        list.className = "check-group-list";
        items.forEach(([key, record]) => list.appendChild(renderCheckRow(key, record, selectedKeys, renderLoopTab)));
        group.appendChild(header);
        group.appendChild(list);
        holder.appendChild(group);
      });
    }

    function renderChecks(holderId, filterId, records, selectedKeys, options = {}) {
      const holder = $(holderId);
      const filter = ($(filterId).value || "").toLowerCase();
      holder.innerHTML = "";
      holder.classList.toggle("grouped", Boolean(options.grouped));
      const section = options.section || "";
      const entries = sortedRecordEntries(records, section).filter(([key, record]) => matchesFilter(record, key, filter, options.grouped, section, options.includeTextFields));
      if (options.grouped) {
        renderGroupedChecks(holder, entries, selectedKeys, section);
        return;
      }
      entries.forEach(([key, record]) => holder.appendChild(renderCheckRow(key, record, selectedKeys)));
    }

    function setVisibleSelection(section, filterId, selectedKeys, checked, grouped = false) {
      const filter = ($(filterId).value || "").toLowerCase();
      const keys = sortedRecordEntries(library[section], section)
        .filter(([key, record]) => matchesFilter(record, key, filter, grouped, section, section === "objects"))
        .map(([key]) => key);
      syncSelection(selectedKeys, keys, checked);
      debounceSaveLibrary();
      renderLoopTab();
      renderBottom();
    }

    function recordGroupKey(section, record) {
      ensureGroups(section);
      const fallback = groupEntries(section)[0]?.[0] || "default";
      const key = record?.group || record?.group_key || fallback;
      return library.groups?.[section]?.[key] ? key : fallback;
    }

    function reorderCurrentSectionGroups(sourceKey, targetKey, placeAfter, orderedKeysOverride = null) {
      const section = $("dbSection").value;
      if (isGlobalSection(section)) return;
      const groups = ensureGroups(section);
      if (!groups[sourceKey]) return;
      const currentGroupBefore = dbCurrentGroupKey;
      const currentKeyBefore = dbCurrentKey;
      const editorKeyBefore = dbEditorKey;
      const currentKeys = groupEntries(section).map(([key]) => key);
      const orderedKeys = Array.isArray(orderedKeysOverride)
        ? mergeOrderedSubset(currentKeys, orderedKeysOverride)
        : (groups[targetKey] ? reorderKeys(currentKeys, sourceKey, targetKey, placeAfter) : currentKeys);
      orderedKeys.forEach((groupKey, index) => {
        if (groups[groupKey]) groups[groupKey].sort_index = index + 1;
      });
      reindexSectionRecordsByGroups(section);
      if (groups[currentGroupBefore]) dbCurrentGroupKey = currentGroupBefore;
      if (library[section]?.[currentKeyBefore]) dbCurrentKey = currentKeyBefore;
      if (library[section]?.[editorKeyBefore]) dbEditorKey = editorKeyBefore;
      dbDirty = true;
      debounceSaveLibrary();
      renderAll();
    }

    function reorderCurrentGroupItems(sourceKey, targetKey, placeAfter, orderedKeysOverride = null) {
      const section = $("dbSection").value;
      if (isGlobalSection(section) || !dbCurrentGroupKey) return;
      const records = library[section] || {};
      if (!records[sourceKey] || recordGroupKey(section, records[sourceKey]) !== dbCurrentGroupKey) return;
      const currentKeyBefore = dbCurrentKey;
      const editorKeyBefore = dbEditorKey;
      const currentKeys = recordKeysForGroup(section, dbCurrentGroupKey);
      const orderedKeys = Array.isArray(orderedKeysOverride)
        ? mergeOrderedSubset(currentKeys, orderedKeysOverride)
        : ((records[targetKey] && recordGroupKey(section, records[targetKey]) === dbCurrentGroupKey)
          ? reorderKeys(currentKeys, sourceKey, targetKey, placeAfter)
          : currentKeys);
      reindexRecordsInGroup(section, dbCurrentGroupKey, orderedKeys);
      if (records[currentKeyBefore] && recordGroupKey(section, records[currentKeyBefore]) === dbCurrentGroupKey) {
        dbCurrentKey = currentKeyBefore;
      }
      if (records[editorKeyBefore] && recordGroupKey(section, records[editorKeyBefore]) === dbCurrentGroupKey) {
        dbEditorKey = editorKeyBefore;
      }
      dbDirty = true;
      debounceSaveLibrary();
      renderAll();
    }

    function renderDbGroups(section) {
      const groupList = $("dbGroupList");
      groupList.innerHTML = "";
      bindDbDragContainer(groupList, `db-group:${section}`, reorderCurrentSectionGroups);
      groupEntries(section).forEach(([groupKey, group]) => {
        const count = Object.values(library[section] || {}).filter((record) => recordGroupKey(section, record) === groupKey).length;
        const button = document.createElement("button");
        button.className = "db-item" + (groupKey === dbCurrentGroupKey ? " active" : "");
        setDbItemContent(button, `${groupLabel(section, groupKey)} (${count})`, true);
        bindDbDragSort(button, groupKey, reorderCurrentSectionGroups, `db-group:${section}`);
        button.onclick = () => {
          if (dbDragJustEnded) return;
          if (!applyDbEditor({rerender: false, silent: true})) return;
          dbCurrentGroupKey = groupKey;
          dbCurrentKey = "";
          renderDatabaseTab();
        };
        groupList.appendChild(button);
      });
    }

    function populateGroupSelect(section, selectedGroupKey) {
      const select = $("dbGroupSelect");
      select.innerHTML = "";
      groupEntries(section).forEach(([groupKey]) => {
        const option = document.createElement("option");
        option.value = groupKey;
        option.textContent = groupLabel(section, groupKey);
        option.selected = groupKey === selectedGroupKey;
        select.appendChild(option);
      });
    }

    function renderDatabaseTab() {
      const section = $("dbSection").value;
      const filter = ($("dbFilter").value || "").toLowerCase();
      const list = $("dbList");
      list.innerHTML = "";
      const globalSection = isGlobalSection(section);
      const editableKey = usesEditableKey(section);
      $("dbGroupTools").classList.toggle("hidden", globalSection);
      $("dbGroupWrap").classList.toggle("hidden", globalSection);
      $("dbKeyWrap").classList.toggle("hidden", !editableKey);
      $("dbKey").disabled = !editableKey;
      $("dbDisplayNameWrap").classList.toggle("span-8", editableKey);
      $("dbDisplayNameWrap").classList.toggle("span-12", !editableKey);
      $("dbDisplayName").disabled = globalSection;
      $("dbAdd").disabled = globalSection;
      if ($("dbDuplicate")) $("dbDuplicate").disabled = globalSection;
      if ($("dbDelete")) $("dbDelete").disabled = globalSection;
      $("negativeWrap").classList.toggle("hidden", globalSection);
      $("randomWrap").classList.toggle("hidden", section !== "actions");
      $("customPromptWrap").classList.toggle("hidden", section !== "actions");
      if (globalSection) {
        dbCurrentKey = section;
        dbCurrentGroupKey = "";
        const button = document.createElement("button");
        button.className = "db-item active";
        setDbItemContent(button, GLOBAL_SECTIONS[section]);
        button.onclick = () => loadDbEditor();
        list.appendChild(button);
        loadDbEditor();
        return;
      }
      ensureGroups(section);
      if (!dbCurrentGroupKey || !library.groups[section][dbCurrentGroupKey]) {
        dbCurrentGroupKey = groupEntries(section)[0]?.[0] || "";
      }
      renderDbGroups(section);
      bindDbDragContainer(list, `db-record:${section}:${dbCurrentGroupKey}`, reorderCurrentGroupItems);
      sortedRecordEntries(library[section], section).forEach(([key, record]) => {
        if (recordGroupKey(section, record) !== dbCurrentGroupKey) return;
        const text = label(record, key);
        if (filter && !text.toLowerCase().includes(filter) && !key.toLowerCase().includes(filter)) return;
        const button = document.createElement("button");
        button.className = "db-item" + (key === dbCurrentKey ? " active" : "");
        setDbItemContent(button, text, true);
        bindDbDragSort(button, key, reorderCurrentGroupItems, `db-record:${section}:${dbCurrentGroupKey}`);
        button.onclick = () => {
          if (dbDragJustEnded) return;
          if (!applyDbEditor({rerender: false, silent: true})) return;
          debounceSaveLibrary();
          dbCurrentKey = key;
          loadDbEditor();
          renderDatabaseTab();
        };
        list.appendChild(button);
      });
      if (!dbCurrentKey || !library[section][dbCurrentKey] || recordGroupKey(section, library[section][dbCurrentKey]) !== dbCurrentGroupKey) {
        dbCurrentKey = sortedRecordEntries(library[section], section).find(([_key, record]) => recordGroupKey(section, record) === dbCurrentGroupKey)?.[0] || "";
        loadDbEditor();
      }
    }

    function loadDbEditor() {
      const section = $("dbSection").value;
      dbEditorSection = section;
      dbEditorKey = dbCurrentKey;
      if (isGlobalSection(section)) {
        dbEditorKey = section;
        $("dbKey").value = section;
        $("dbDisplayName").value = GLOBAL_SECTIONS[section];
        $("dbGroupSelect").innerHTML = "";
        $("dbPrompt").value = library.defaults?.[section] || "";
        $("dbNegativePrompt").value = "";
        $("dbRandomPrompt").value = "";
        $("dbCustomPrompt").value = "";
        return;
      }
      const record = library[section][dbEditorKey] || {};
      const groupKey = recordGroupKey(section, record);
      $("dbKey").value = dbEditorKey;
      $("dbDisplayName").value = label(record, dbEditorKey);
      populateGroupSelect(section, groupKey);
      $("dbPrompt").value = record.prompt || "";
      $("dbNegativePrompt").value = record.negative_prompt || "";
      $("dbRandomPrompt").value = record.random_prompt || "";
      $("dbCustomPrompt").value = record.custom_prompt || "";
    }

    function applyDbEditor(options = {}) {
      const {rerender = true, silent = false} = options;
      const section = dbEditorSection || $("dbSection").value;
      if (isGlobalSection(section)) {
        if (!library.defaults) library.defaults = {};
        library.defaults[section] = $("dbPrompt").value;
        dbDirty = true;
        if (rerender) renderAll();
        return true;
      }
      const oldKey = dbEditorKey || dbCurrentKey;
      if (!oldKey || !library[section]) return true;
      if (!library[section][oldKey]) {
        dbEditorKey = dbCurrentKey;
        return true;
      }
      const newKey = usesEditableKey(section) ? safeKey($("dbKey").value || oldKey) : oldKey;
      if (!newKey) {
        if (!silent) alert("Key cannot be empty.");
        return false;
      }
      if (newKey !== oldKey && Object.prototype.hasOwnProperty.call(library[section], newKey)) {
        if (!silent) alert(`Key "${newKey}" already exists. Use another key.`);
        const keyInput = $("dbKey");
        if (keyInput) keyInput.value = oldKey;
        return false;
      }
      const oldRecord = library[section][oldKey] || {};
      const record = {...oldRecord};
      const previousGroupKey = recordGroupKey(section, oldRecord);
      record.name = $("dbDisplayName").value || newKey;
      record.prompt = $("dbPrompt").value;
      const selectedGroupKey = $("dbGroupSelect").value || dbCurrentGroupKey || groupEntries(section)[0]?.[0] || "default";
      const nextSortIndex = selectedGroupKey !== previousGroupKey ? nextRecordSortIndex(section, selectedGroupKey) + 1 : null;
      applyRecordOrderFields(section, record, selectedGroupKey, nextSortIndex);
      record.negative_prompt = $("dbNegativePrompt").value;
      if (section === "actions") {
        record.random_prompt = $("dbRandomPrompt").value;
        record.custom_prompt = $("dbCustomPrompt").value;
      }
      delete library[section][oldKey];
      library[section][newKey] = record;
      dbCurrentKey = newKey;
      dbEditorKey = newKey;
      dbCurrentGroupKey = selectedGroupKey;
      dbDirty = true;
      if (rerender) renderAll();
      return true;
    }

    function autoSaveDbEditor() {
      if (!applyDbEditor({rerender: false, silent: true})) return;
      debounceSaveLibrary();
    }

    function uniqueGroupKey(section, displayName) {
      ensureGroups(section);
      const groups = library.groups[section];
      const base = safeKey(displayName) || "group";
      let key = base;
      let n = 1;
      while (groups[key]) key = `${base}_${n++}`;
      return key;
    }

    function addCurrentSectionGroup() {
      const section = $("dbSection").value;
      if (isGlobalSection(section)) return;
      if (!applyDbEditor({rerender: false, silent: true})) return;
      const name = prompt("New group name", "New group");
      if (!name || !name.trim()) return;
      const groups = ensureGroups(section);
      const key = uniqueGroupKey(section, name.trim());
      const maxSort = Math.max(0, ...Object.values(groups).map((group) => Number(group.sort_index || 0)));
      groups[key] = {name: normalizeGroupLabel(name), sort_index: maxSort + 1};
      dbCurrentGroupKey = key;
      dbCurrentKey = "";
      debounceSaveLibrary();
      renderAll();
    }

    function renameCurrentSectionGroup() {
      const section = $("dbSection").value;
      if (isGlobalSection(section)) return;
      const groups = ensureGroups(section);
      const group = groups[dbCurrentGroupKey];
      if (!group) return;
      const name = prompt("Rename group", group.name || dbCurrentGroupKey);
      if (!name || !name.trim()) return;
      group.name = normalizeGroupLabel(name);
      debounceSaveLibrary();
      renderAll();
    }

    function deleteCurrentSectionGroup() {
      const section = $("dbSection").value;
      if (isGlobalSection(section)) return;
      const groups = ensureGroups(section);
      const entries = groupEntries(section);
      if (entries.length <= 1) {
        alert("At least one group must remain.");
        return;
      }
      const group = groups[dbCurrentGroupKey];
      if (!group) return;
      const targetKey = entries.find(([key]) => key !== dbCurrentGroupKey)?.[0];
      const itemCount = Object.values(library[section] || {}).filter((record) => recordGroupKey(section, record) === dbCurrentGroupKey).length;
      const targetName = groupLabel(section, targetKey);
      const message = itemCount
        ? `Delete group "${group.name}"?\n\n${itemCount} item(s) will be moved to "${targetName}".`
        : `Delete group "${group.name}"?`;
      if (!confirm(message)) return;
      Object.values(library[section] || {}).forEach((record) => {
        if (recordGroupKey(section, record) === dbCurrentGroupKey) {
          record.group = targetKey;
        }
      });
      delete groups[dbCurrentGroupKey];
      groupEntries(section).forEach(([groupKey], index) => {
        groups[groupKey].sort_index = index + 1;
      });
      reindexSectionRecordsByGroups(section);
      dbCurrentGroupKey = targetKey;
      dbCurrentKey = "";
      debounceSaveLibrary();
      renderAll();
    }

    function activeTabName() {
      return document.querySelector(".tab-btn.active")?.dataset.tab || "model";
    }

    function renderBottom() {
      const singleMode = activeTabName() === "single";
      $("totalCount").textContent = singleMode ? 1 : computeTotal();
      $("repeatCount").value = config.run.repeat_count;
      $("repeatCount").disabled = singleMode;
    }



    function normalizePromptText(value) {
      return String(value || "")
        .replace(/\r\n/g, "\n")
        .replace(/[ \t]+/g, " ")
        .replace(/\s*,\s*/g, ", ")
        .trim()
        .toLowerCase();
    }

    function promptContains(haystack, needle) {
      const target = normalizePromptText(needle);
      if (!target || target.length < 3) return false;
      return normalizePromptText(haystack).includes(target);
    }

    function latin1BytesToString(bytes) {
      let output = "";
      for (let i = 0; i < bytes.length; i += 1) output += String.fromCharCode(bytes[i]);
      try {
        return decodeURIComponent(escape(output));
      } catch {
        return output;
      }
    }

    function readPngTextChunks(buffer) {
      const bytes = new Uint8Array(buffer);
      const signature = [137, 80, 78, 71, 13, 10, 26, 10];
      if (bytes.length < 8 || signature.some((value, index) => bytes[index] !== value)) {
        return {ok: false, error: "This is not a PNG file; embedded PNG metadata cannot be read.", chunks: {}};
      }
      const decoder = new TextDecoder("utf-8", {fatal: false});
      const chunks = {};
      let offset = 8;
      while (offset + 12 <= bytes.length) {
        const length = ((bytes[offset] << 24) | (bytes[offset + 1] << 16) | (bytes[offset + 2] << 8) | bytes[offset + 3]) >>> 0;
        const type = String.fromCharCode(bytes[offset + 4], bytes[offset + 5], bytes[offset + 6], bytes[offset + 7]);
        const start = offset + 8;
        const end = start + length;
        if (end + 4 > bytes.length) break;
        const data = bytes.slice(start, end);
        if (type === "tEXt") {
          const zero = data.indexOf(0);
          if (zero > 0) {
            const key = latin1BytesToString(data.slice(0, zero));
            const value = decoder.decode(data.slice(zero + 1));
            chunks[key] = value;
          }
        } else if (type === "iTXt") {
          const parts = [];
          let last = 0;
          for (let i = 0; i < data.length && parts.length < 5; i += 1) {
            if (data[i] === 0) {
              parts.push(data.slice(last, i));
              last = i + 1;
            }
          }
          if (parts.length >= 5) {
            const key = latin1BytesToString(parts[0]);
            const compressed = parts[1]?.[0] === 1;
            chunks[key] = compressed ? "[iTXt compressed data is not supported]" : decoder.decode(data.slice(last));
          }
        }
        offset = end + 4;
      }
      return {ok: true, chunks};
    }

    function tryParseJson(value) {
      if (!value) return null;
      try {
        return JSON.parse(value);
      } catch {
        return null;
      }
    }

    function normalizeLoraName(value) {
      return String(value || "").trim().replace(/^[\s\"']+|[\s\"']+$/g, "");
    }

    function addLoraRecord(target, data = {}) {
      const name = normalizeLoraName(data.name || data.lora_name || data.model_name || data.modelName || data.filename || data.file || "");
      if (!name) return;
      const key = name.toLowerCase();
      const existing = target.find((item) => normalizeLoraName(item.name).toLowerCase() === key);
      const next = {
        name,
        strength_model: data.strength_model ?? data.model_strength ?? data.strength ?? data.weight ?? data.modelWeight ?? "",
        strength_clip: data.strength_clip ?? data.clip_strength ?? data.clipStrength ?? "",
        version: data.version || data.modelVersionName || data.model_version || data.version_name || "",
        source: data.source || ""
      };
      if (existing) {
        Object.entries(next).forEach(([field, value]) => {
          if ((existing[field] === undefined || existing[field] === null || String(existing[field]).trim() === "") && value !== undefined && value !== null && String(value).trim() !== "") {
            existing[field] = value;
          }
        });
        return;
      }
      target.push(next);
    }

    function addAnalysisRecord(target, data = {}, nameCandidates = [], fallbackName = "") {
      const name = normalizeLoraName(nameCandidates.find((value) => value !== undefined && value !== null && String(value).trim() !== "") || fallbackName);
      if (!name) return null;
      const signature = [name, data.class_type || data.classType || "", data.source || "", data.method || data.upscale_method || "", data.strength || data.weight || "", data.scale_by || data.scale || "", data.start_percent || "", data.end_percent || ""].join("|").toLowerCase();
      const existing = target.find((item) => item.signature === signature || (normalizeLoraName(item.name).toLowerCase() === name.toLowerCase() && String(item.source || "") === String(data.source || "")));
      const next = {
        ...data,
        name,
        signature
      };
      if (existing) {
        Object.entries(next).forEach(([field, value]) => {
          if (field === "signature") return;
          if ((existing[field] === undefined || existing[field] === null || String(existing[field]).trim() === "") && value !== undefined && value !== null && String(value).trim() !== "") {
            existing[field] = value;
          }
        });
        return existing;
      }
      target.push(next);
      return next;
    }

    function addEmbeddingRecord(target, data = {}) {
      return addAnalysisRecord(target, {
        strength: data.strength ?? data.weight ?? data.model_strength ?? data.strength_model ?? "",
        version: data.version || data.modelVersionName || data.model_version || data.version_name || "",
        source: data.source || data.type || data.modelType || data.resourceType || ""
      }, [data.embedding_name, data.embedding, data.name, data.model_name, data.modelName, data.filename, data.file]);
    }

    function addUpscaleRecord(target, data = {}) {
      const classType = data.class_type || data.classType || "";
      return addAnalysisRecord(target, {
        class_type: classType,
        method: data.method || data.upscale_method || data.upscaler || "",
        scale_by: data.scale_by ?? data.scale ?? data.upscale_by ?? data.factor ?? "",
        width: data.width ?? "",
        height: data.height ?? "",
        crop: data.crop ?? "",
        source: data.source || ""
      }, [data.model_name, data.upscale_model_name, data.upscale_model, data.upscaler_name, data.upscaler, data.name, data.model, data.filename, data.file], classType ? classType : "Upscale");
    }

    function addControlNetRecord(target, data = {}) {
      const classType = data.class_type || data.classType || "";
      return addAnalysisRecord(target, {
        class_type: classType,
        strength: data.strength ?? data.weight ?? data.control_net_strength ?? "",
        start_percent: data.start_percent ?? data.startPercent ?? data.start ?? "",
        end_percent: data.end_percent ?? data.endPercent ?? data.end ?? "",
        preprocessor: data.preprocessor || data.preprocessor_name || data.processor || data.detectmap || "",
        source: data.source || ""
      }, [data.control_net_name, data.controlnet_name, data.control_net, data.controlnet, data.model_name, data.modelName, data.name, data.filename, data.file], classType ? classType : "ControlNet");
    }

    function extractLoraTagsFromText(text) {
      const loras = [];
      const value = String(text || "");
      const tagPattern = /<lora:([^:>]+)(?::([^>]+))?>/gi;
      let match;
      while ((match = tagPattern.exec(value))) {
        addLoraRecord(loras, {name: match[1], strength_model: match[2] || "", source: "Prompt tag"});
      }
      return loras;
    }

    function extractEmbeddingTagsFromText(text) {
      const embeddings = [];
      const value = String(text || "");
      const angledPattern = /<embedding:([^:>]+)(?::([^>]+))?>/gi;
      let match;
      while ((match = angledPattern.exec(value))) {
        addEmbeddingRecord(embeddings, {name: match[1], strength: match[2] || "", source: "Prompt tag"});
      }
      const inlinePattern = /(?:^|[\s,(])embedding:([A-Za-z0-9_.\-\/]+)(?::([+-]?\d*\.?\d+))?/gi;
      while ((match = inlinePattern.exec(value))) {
        addEmbeddingRecord(embeddings, {name: match[1], strength: match[2] || "", source: "Prompt text"});
      }
      return embeddings;
    }

    function collectLorasFromValue(value, target, parentKey = "") {
      if (value === null || value === undefined) return;
      if (typeof value === "string") {
        extractLoraTagsFromText(value).forEach((item) => addLoraRecord(target, item));
        if (/lora/i.test(parentKey) && value.trim() && value.length < 260) addLoraRecord(target, {name: value, source: parentKey});
        return;
      }
      if (Array.isArray(value)) {
        value.forEach((item) => collectLorasFromValue(item, target, parentKey));
        return;
      }
      if (typeof value !== "object") return;

      const objectType = String(value.type || value.modelType || value.resourceType || value.kind || value.class_type || "").toLowerCase();
      const hasLoraType = objectType.includes("lora") || /lora/i.test(parentKey);
      const directName = value.lora_name || value.lora || value.name || value.model_name || value.modelName || value.filename || value.file;
      if (directName && hasLoraType) {
        addLoraRecord(target, {
          ...value,
          name: directName,
          source: value.source || value.type || value.modelType || parentKey
        });
      }
      Object.entries(value).forEach(([key, nested]) => {
        collectLorasFromValue(nested, target, key);
      });
    }

    function collectEmbeddingsFromValue(value, target, parentKey = "") {
      if (value === null || value === undefined) return;
      if (typeof value === "string") {
        extractEmbeddingTagsFromText(value).forEach((item) => addEmbeddingRecord(target, item));
        if (/(embedding|textual.?inversion)/i.test(parentKey) && value.trim() && value.length < 260) addEmbeddingRecord(target, {name: value, source: parentKey});
        return;
      }
      if (Array.isArray(value)) {
        value.forEach((item) => collectEmbeddingsFromValue(item, target, parentKey));
        return;
      }
      if (typeof value !== "object") return;

      const objectType = String(value.type || value.modelType || value.resourceType || value.kind || value.class_type || "").toLowerCase().replace(/\s+/g, "");
      const hasEmbeddingType = objectType.includes("embedding") || objectType.includes("textualinversion") || /(embedding|textual.?inversion)/i.test(parentKey);
      const directName = value.embedding_name || value.embedding || value.name || value.model_name || value.modelName || value.filename || value.file;
      if (directName && hasEmbeddingType) {
        addEmbeddingRecord(target, {
          ...value,
          name: directName,
          source: value.source || value.type || value.modelType || parentKey
        });
      }
      Object.entries(value).forEach(([key, nested]) => {
        collectEmbeddingsFromValue(nested, target, key);
      });
    }

    function collectUpscalesFromValue(value, target, parentKey = "") {
      if (value === null || value === undefined) return;
      if (typeof value === "string") {
        if (/(upscale|upscaler|hires)/i.test(parentKey) && value.trim() && value.length < 260) addUpscaleRecord(target, {name: value, source: parentKey});
        return;
      }
      if (Array.isArray(value)) {
        value.forEach((item) => collectUpscalesFromValue(item, target, parentKey));
        return;
      }
      if (typeof value !== "object") return;
      const objectType = String(value.type || value.modelType || value.resourceType || value.kind || value.class_type || "").toLowerCase();
      const hasUpscaleType = objectType.includes("upscale") || objectType.includes("upscaler") || objectType.includes("hires") || /(upscale|upscaler|hires)/i.test(parentKey);
      if (hasUpscaleType) {
        addUpscaleRecord(target, {
          ...value,
          name: value.model_name || value.upscale_model_name || value.upscale_model || value.upscaler_name || value.upscaler || value.name || value.model || value.filename || value.file || value.class_type || value.type,
          source: value.source || value.type || value.modelType || parentKey
        });
      }
      Object.entries(value).forEach(([key, nested]) => {
        collectUpscalesFromValue(nested, target, key);
      });
    }

    function collectControlNetsFromValue(value, target, parentKey = "") {
      if (value === null || value === undefined) return;
      if (typeof value === "string") {
        if (/control.?net/i.test(parentKey) && value.trim() && value.length < 260) addControlNetRecord(target, {name: value, source: parentKey});
        return;
      }
      if (Array.isArray(value)) {
        value.forEach((item) => collectControlNetsFromValue(item, target, parentKey));
        return;
      }
      if (typeof value !== "object") return;
      const objectType = String(value.type || value.modelType || value.resourceType || value.kind || value.class_type || "").toLowerCase();
      const hasControlNetType = objectType.includes("controlnet") || /control.?net/i.test(parentKey);
      if (hasControlNetType) {
        addControlNetRecord(target, {
          ...value,
          name: value.control_net_name || value.controlnet_name || value.control_net || value.controlnet || value.model_name || value.modelName || value.name || value.filename || value.file || value.class_type || value.type,
          source: value.source || value.type || value.modelType || parentKey
        });
      }
      Object.entries(value).forEach(([key, nested]) => {
        collectControlNetsFromValue(nested, target, key);
      });
    }

    function extractLorasFromPromptGraph(promptGraph) {
      const loras = [];
      if (!promptGraph || typeof promptGraph !== "object") return loras;
      Object.values(promptGraph).forEach((node) => {
        if (!node || typeof node !== "object") return;
        const classType = String(node.class_type || "");
        const inputs = node.inputs || {};
        if (/lora/i.test(classType) || Object.keys(inputs).some((key) => /lora/i.test(key))) {
          if (inputs.lora_name || inputs.lora || inputs.name) {
            addLoraRecord(loras, {
              name: inputs.lora_name || inputs.lora || inputs.name,
              strength_model: inputs.strength_model ?? inputs.model_strength ?? inputs.strength ?? inputs.weight ?? "",
              strength_clip: inputs.strength_clip ?? inputs.clip_strength ?? "",
              source: classType || "ComfyUI"
            });
          }
          collectLorasFromValue(inputs, loras, classType);
        }
      });
      return loras;
    }

    function extractEmbeddingsFromPromptGraph(promptGraph) {
      const embeddings = [];
      if (!promptGraph || typeof promptGraph !== "object") return embeddings;
      Object.values(promptGraph).forEach((node) => {
        if (!node || typeof node !== "object") return;
        const classType = String(node.class_type || "");
        const inputs = node.inputs || {};
        if (/(embedding|textual.?inversion)/i.test(classType) || Object.keys(inputs).some((key) => /(embedding|textual.?inversion)/i.test(key))) {
          addEmbeddingRecord(embeddings, {
            name: inputs.embedding_name || inputs.embedding || inputs.name || inputs.model_name,
            strength: inputs.strength ?? inputs.weight ?? "",
            source: classType || "ComfyUI"
          });
          collectEmbeddingsFromValue(inputs, embeddings, classType);
        }
      });
      return embeddings;
    }

    function extractUpscalesFromPromptGraph(promptGraph) {
      const upscales = [];
      if (!promptGraph || typeof promptGraph !== "object") return upscales;
      Object.entries(promptGraph).forEach(([nodeId, node]) => {
        if (!node || typeof node !== "object") return;
        const classType = String(node.class_type || "");
        const inputs = node.inputs || {};
        const isUpscaleNode = /(upscale|upscaler|hires)/i.test(classType) || Object.keys(inputs).some((key) => /(upscale|upscaler|scale_by|hires)/i.test(key));
        if (!isUpscaleNode) return;
        let linkedModelName = "";
        if (Array.isArray(inputs.upscale_model)) {
          const linked = nodeFromLink(promptGraph, inputs.upscale_model);
          linkedModelName = linked?.inputs?.model_name || linked?.inputs?.upscale_model_name || "";
        }
        addUpscaleRecord(upscales, {
          name: inputs.model_name || inputs.upscale_model_name || linkedModelName || inputs.upscaler_name || inputs.upscaler || inputs.name || classType,
          class_type: classType,
          method: inputs.upscale_method || inputs.method || inputs.upscaler || "",
          scale_by: inputs.scale_by ?? inputs.scale ?? inputs.upscale_by ?? inputs.factor ?? "",
          width: inputs.width ?? "",
          height: inputs.height ?? "",
          crop: inputs.crop ?? "",
          source: `ComfyUI #${nodeId}`
        });
      });
      return upscales;
    }

    function extractControlNetsFromPromptGraph(promptGraph) {
      const controlnets = [];
      if (!promptGraph || typeof promptGraph !== "object") return controlnets;
      Object.entries(promptGraph).forEach(([nodeId, node]) => {
        if (!node || typeof node !== "object") return;
        const classType = String(node.class_type || "");
        const inputs = node.inputs || {};
        const isControlNetNode = /control.?net/i.test(classType) || Object.keys(inputs).some((key) => /control.?net/i.test(key));
        if (!isControlNetNode) return;
        let linkedModelName = "";
        if (Array.isArray(inputs.control_net)) {
          const linked = nodeFromLink(promptGraph, inputs.control_net);
          linkedModelName = linked?.inputs?.control_net_name || linked?.inputs?.controlnet_name || linked?.inputs?.model_name || "";
        }
        addControlNetRecord(controlnets, {
          name: inputs.control_net_name || inputs.controlnet_name || linkedModelName || inputs.model_name || inputs.name || classType,
          class_type: classType,
          strength: inputs.strength ?? inputs.weight ?? inputs.control_net_strength ?? "",
          start_percent: inputs.start_percent ?? inputs.startPercent ?? inputs.start ?? "",
          end_percent: inputs.end_percent ?? inputs.endPercent ?? inputs.end ?? "",
          preprocessor: inputs.preprocessor || inputs.preprocessor_name || inputs.processor || "",
          source: `ComfyUI #${nodeId}`
        });
      });
      return controlnets;
    }

    function extractImageMetadataFromChunks(chunks) {
      const textChunks = chunks || {};
      const promptGraph = tryParseJson(textChunks.prompt);
      let metadata = extractComfyMetadata(promptGraph);
      if (!metadata && textChunks.parameters) metadata = parseParametersText(textChunks.parameters);

      const jsonValues = Object.values(textChunks)
        .map((value) => tryParseJson(value))
        .filter(Boolean);
      const allLoras = [];
      const allEmbeddings = [];
      const allUpscales = [];
      const allControlNets = [];
      if (metadata?.loras) metadata.loras.forEach((item) => addLoraRecord(allLoras, item));
      if (metadata?.embeddings) metadata.embeddings.forEach((item) => addEmbeddingRecord(allEmbeddings, item));
      if (metadata?.upscales) metadata.upscales.forEach((item) => addUpscaleRecord(allUpscales, item));
      if (metadata?.controlnets) metadata.controlnets.forEach((item) => addControlNetRecord(allControlNets, item));
      jsonValues.forEach((value) => {
        collectLorasFromValue(value, allLoras);
        collectEmbeddingsFromValue(value, allEmbeddings);
        collectUpscalesFromValue(value, allUpscales);
        collectControlNetsFromValue(value, allControlNets);
      });
      extractLoraTagsFromText(metadata?.positive || "").forEach((item) => addLoraRecord(allLoras, item));
      extractLoraTagsFromText(metadata?.negative || "").forEach((item) => addLoraRecord(allLoras, item));
      extractEmbeddingTagsFromText(metadata?.positive || "").forEach((item) => addEmbeddingRecord(allEmbeddings, item));
      extractEmbeddingTagsFromText(metadata?.negative || "").forEach((item) => addEmbeddingRecord(allEmbeddings, item));
      if (textChunks.parameters && !metadata) {
        extractLoraTagsFromText(textChunks.parameters).forEach((item) => addLoraRecord(allLoras, item));
        extractEmbeddingTagsFromText(textChunks.parameters).forEach((item) => addEmbeddingRecord(allEmbeddings, item));
      }
      if (!metadata && (allLoras.length || allEmbeddings.length || allUpscales.length || allControlNets.length)) {
        metadata = {source: "Metadata", positive: "", negative: ""};
      }
      if (metadata) {
        metadata.loras = allLoras;
        metadata.embeddings = allEmbeddings;
        metadata.upscales = allUpscales;
        metadata.controlnets = allControlNets;
      }
      return metadata;
    }

    function firstNodeByClass(graph, matcher) {
      if (!graph || typeof graph !== "object") return ["", null];
      return Object.entries(graph).find(([_id, node]) => node && matcher(String(node.class_type || ""))) || ["", null];
    }

    function nodeFromLink(graph, link) {
      if (!Array.isArray(link) || !link.length) return null;
      return graph?.[String(link[0])] || null;
    }

    function extractComfyMetadata(promptGraph) {
      if (!promptGraph || typeof promptGraph !== "object") return null;
      const [samplerId, sampler] = firstNodeByClass(promptGraph, (type) => type.includes("KSampler"));
      const positiveNode = nodeFromLink(promptGraph, sampler?.inputs?.positive);
      const negativeNode = nodeFromLink(promptGraph, sampler?.inputs?.negative);
      const latentNode = nodeFromLink(promptGraph, sampler?.inputs?.latent_image);
      const [_saveId, saveNode] = firstNodeByClass(promptGraph, (type) => type === "SaveImage" || type.includes("Save"));
      const [_unetId, unetNode] = firstNodeByClass(promptGraph, (type) => type === "UNETLoader");
      const [_clipId, clipNode] = firstNodeByClass(promptGraph, (type) => type === "CLIPLoader" || type === "DualCLIPLoader");
      const [_vaeId, vaeNode] = firstNodeByClass(promptGraph, (type) => type === "VAELoader");
      const clipTextNodes = Object.values(promptGraph).filter((node) => node?.class_type === "CLIPTextEncode");
      const positive = positiveNode?.inputs?.text || clipTextNodes[0]?.inputs?.text || "";
      const negative = negativeNode?.inputs?.text || clipTextNodes[1]?.inputs?.text || "";
      const loras = extractLorasFromPromptGraph(promptGraph);
      const embeddings = extractEmbeddingsFromPromptGraph(promptGraph);
      extractEmbeddingTagsFromText(positive).forEach((item) => addEmbeddingRecord(embeddings, item));
      extractEmbeddingTagsFromText(negative).forEach((item) => addEmbeddingRecord(embeddings, item));
      const upscales = extractUpscalesFromPromptGraph(promptGraph);
      const controlnets = extractControlNetsFromPromptGraph(promptGraph);
      return {
        source: "ComfyUI",
        positive,
        negative,
        sampler_id: samplerId,
        seed: sampler?.inputs?.seed,
        steps: sampler?.inputs?.steps,
        cfg: sampler?.inputs?.cfg,
        sampler_name: sampler?.inputs?.sampler_name,
        scheduler: sampler?.inputs?.scheduler,
        denoise: sampler?.inputs?.denoise,
        width: latentNode?.inputs?.width,
        height: latentNode?.inputs?.height,
        batch_size: latentNode?.inputs?.batch_size,
        filename_prefix: saveNode?.inputs?.filename_prefix,
        unet_name: unetNode?.inputs?.unet_name,
        clip_name: clipNode?.inputs?.clip_name,
        clip_type: clipNode?.inputs?.type,
        vae_name: vaeNode?.inputs?.vae_name,
        loras,
        embeddings,
        upscales,
        controlnets
      };
    }

    function parseParametersText(parameters) {
      if (!parameters) return null;
      const text = String(parameters);
      let positive = text;
      let negative = "";
      let settings = "";
      const negativeMarker = "\nNegative prompt:";
      const negativeIndex = text.indexOf(negativeMarker);
      if (negativeIndex >= 0) {
        positive = text.slice(0, negativeIndex).trim();
        const afterNegative = text.slice(negativeIndex + negativeMarker.length).trim();
        const settingsMatch = afterNegative.match(/\n(Steps:|Sampler:|CFG scale:|Seed:|Size:|Model:|Denoising strength:|Hires)/s);
        if (settingsMatch) {
          negative = afterNegative.slice(0, settingsMatch.index).trim();
          settings = settingsMatch[0].trim();
        } else {
          negative = afterNegative;
        }
      }
      const positiveSettingsMatch = positive.match(/\n(Steps:|Sampler:|CFG scale:|Seed:|Size:|Model:|Denoising strength:|Hires)/s);
      if (positiveSettingsMatch) {
        settings = positive.slice(positiveSettingsMatch.index).trim();
        positive = positive.slice(0, positiveSettingsMatch.index).trim();
      }
      const getSetting = (name) => {
        const match = settings.match(new RegExp(`${name}:\s*([^,]+)`));
        return match ? match[1].trim() : "";
      };
      const size = getSetting("Size");
      const sizeParts = size.match(/(\d+)\s*x\s*(\d+)/i);
      const upscales = [];
      const hiresUpscaler = getSetting("Hires upscaler") || getSetting("Hires upscale") || getSetting("Upscaler");
      const hiresScale = getSetting("Hires upscale") || getSetting("Hires scale");
      const denoise = getSetting("Denoising strength") || getSetting("Hires denoising strength");
      if (hiresUpscaler || hiresScale || denoise) {
        addUpscaleRecord(upscales, {
          name: hiresUpscaler || "Hires fix / Upscale",
          method: hiresUpscaler,
          scale_by: hiresScale,
          source: "Parameters"
        });
      }
      const embeddings = [];
      extractEmbeddingTagsFromText(positive).forEach((item) => addEmbeddingRecord(embeddings, item));
      extractEmbeddingTagsFromText(negative).forEach((item) => addEmbeddingRecord(embeddings, item));
      return {
        source: "Parameters",
        positive,
        negative,
        steps: getSetting("Steps"),
        sampler_name: getSetting("Sampler"),
        cfg: getSetting("CFG scale"),
        seed: getSetting("Seed"),
        width: sizeParts ? sizeParts[1] : "",
        height: sizeParts ? sizeParts[2] : "",
        denoise,
        raw_settings: settings,
        embeddings,
        upscales,
        controlnets: []
      };
    }

    function sectionLabel(section) {
      const names = {
        defaults: "Global",
        characters: "Characters",
        outfits: "Outfits",
        objects: "Objects",
        actions: "Emotion / Action",
        angles: "View",
        backgrounds: "Background",
        loras: "LoRA",
        embeddings: "Embedding",
        upscale: "Upscale",
        controlnet: "ControlNet"
      };
      return names[section] || section;
    }

    function addMatch(matches, section, key, name, field, detail = "") {
      if (!key && !name) return;
      const id = `${section}:${key}:${field}:${detail}`;
      if (matches.some((item) => item.id === id)) return;
      matches.push({id, section, key, name, field, detail});
    }

    function matchPromptLibrary(positive, negative, metadata) {
      const matches = [];
      if (!library) return matches;
      const defaults = library.defaults || {};
      if (promptContains(positive, defaults.global_positive)) addMatch(matches, "defaults", "global_positive", "Global Positive", "Prompt");
      if (promptContains(negative, defaults.global_negative)) addMatch(matches, "defaults", "global_negative", "Global Negative", "Negative Prompt");
      ["characters", "outfits", "objects", "actions", "angles", "backgrounds"].forEach((section) => {
        Object.entries(library[section] || {}).forEach(([key, record]) => {
          const displayName = label(record, key);
          if (promptContains(positive, record.prompt)) addMatch(matches, section, key, displayName, "Prompt");
          if (promptContains(negative, record.negative_prompt)) addMatch(matches, section, key, displayName, "Negative Prompt");
          if (section === "actions") {
            const randomLines = String(record.random_prompt || "").split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
            randomLines.forEach((line, index) => {
              if (promptContains(positive, line)) addMatch(matches, section, key, displayName, "Variation prompt", `#${index + 1}`);
            });
            if (promptContains(positive, record.custom_prompt)) addMatch(matches, section, key, displayName, "Custom prompt", "");
          }
        });
      });
      const loraNames = new Set((metadata?.loras || []).map((item) => String(item.name || "").trim().toLowerCase()).filter(Boolean));
      const upscaleNames = new Set((metadata?.upscales || []).map((item) => String(item.name || "").trim().toLowerCase()).filter(Boolean));
      (config?.model_presets || []).forEach((preset) => {
        (preset.settings?.loras || []).forEach((lora, index) => {
          const name = String(lora.lora_name || "").trim();
          if (name && loraNames.has(name.toLowerCase())) addMatch(matches, "loras", `model_preset:${preset.name}:${index + 1}`, name, "LoRA");
          if (promptContains(positive, lora.positive_prompt)) addMatch(matches, "loras", `model_preset:${preset.name}:${index + 1}`, name || `LoRA ${index + 1}`, "LoRA positive prompt");
          if (promptContains(negative, lora.negative_prompt)) addMatch(matches, "loras", `model_preset:${preset.name}:${index + 1}`, name || `LoRA ${index + 1}`, "LoRA negative prompt");
        });
        const upscaleModel = String(preset.settings?.upscale?.model_name || "").trim();
        if (upscaleModel && upscaleNames.has(upscaleModel.toLowerCase())) {
          addMatch(matches, "upscale", `model_preset:${preset.name}:upscale`, upscaleModel, "Upscale model");
        }
      });
      return matches;
    }

    function hasRenderableValue(value) {
      return value !== undefined && value !== null && String(value).trim() !== "";
    }

    function renderTextBlock(title, text, badges = []) {
      const textValue = String(text || "").trim();
      if (!textValue) return "";
      const safeText = escapeHtml(textValue);
      const badgeHtml = badges.length ? `<div class="badges">${badges.map((badge) => `<span class="badge">${escapeHtml(badge)}</span>`).join("")}</div>` : "";
      return `
        <div class="metadata-section">
          <div class="metadata-title-row"><h4>${escapeHtml(title)}</h4>${badgeHtml}</div>
          <pre class="metadata-text">${safeText}</pre>
        </div>`;
    }

    function renderMetadataSection(title, bodyHtml, badges = []) {
      const content = String(bodyHtml || "").trim();
      if (!content) return "";
      const badgeHtml = badges.length ? `<div class="badges">${badges.map((badge) => `<span class="badge">${escapeHtml(badge)}</span>`).join("")}</div>` : "";
      return `
        <div class="metadata-section">
          <div class="metadata-title-row"><h4>${escapeHtml(title)}</h4>${badgeHtml}</div>
          ${content}
        </div>`;
    }

    function renderKeyValueGrid(items) {
      const visible = items.filter(([_label, value]) => hasRenderableValue(value));
      if (!visible.length) return "";
      return `<div class="kv-grid">${visible.map(([labelName, value]) => `
        <div class="kv-item"><small>${escapeHtml(labelName)}</small><span>${escapeHtml(value)}</span></div>
      `).join("")}</div>`;
    }

    function renderAnalysisList(items, emptyText, badgeLabel, detailBuilder) {
      if (!items.length) return "";
      return `<div class="lora-list">${items.map((item, index) => {
        const details = detailBuilder(item, index).filter(Boolean).join(" · ");
        return `
          <div class="lora-analysis-row">
            <div><div class="lora-analysis-name">${escapeHtml(item.name || `${badgeLabel} ${index + 1}`)}</div>${details ? `<div class="lora-analysis-detail">${escapeHtml(details)}</div>` : ""}</div>
            <span class="badge">${escapeHtml(badgeLabel)}</span>
          </div>`;
      }).join("")}</div>`;
    }

    function renderLoraList(loras) {
      return renderAnalysisList(loras, "", "LoRA", (lora) => {
        const strengths = [lora.strength_model, lora.strength_clip].filter((value) => hasRenderableValue(value)).join(" / ");
        return [
          lora.version ? `Version: ${lora.version}` : "",
          strengths ? `Strength: ${strengths}` : "",
          lora.source ? `Source: ${lora.source}` : ""
        ];
      });
    }

    function renderEmbeddingList(embeddings) {
      return renderAnalysisList(embeddings, "", "Embedding", (embedding) => [
        embedding.version ? `Version: ${embedding.version}` : "",
        embedding.strength ? `Strength: ${embedding.strength}` : "",
        embedding.source ? `Source: ${embedding.source}` : ""
      ]);
    }

    function renderUpscaleList(upscales) {
      return renderAnalysisList(upscales, "", "Upscale", (upscale) => [
        upscale.class_type ? `Node: ${upscale.class_type}` : "",
        upscale.method ? `Method: ${upscale.method}` : "",
        upscale.scale_by ? `Scale: ${upscale.scale_by}` : "",
        upscale.width || upscale.height ? `Size: ${[upscale.width, upscale.height].filter(Boolean).join(" x ")}` : "",
        upscale.crop ? `Crop: ${upscale.crop}` : "",
        upscale.source ? `Source: ${upscale.source}` : ""
      ]);
    }

    function renderControlNetList(controlnets) {
      return renderAnalysisList(controlnets, "", "ControlNet", (controlnet) => [
        controlnet.class_type ? `Node: ${controlnet.class_type}` : "",
        controlnet.strength ? `Strength: ${controlnet.strength}` : "",
        controlnet.start_percent || controlnet.end_percent ? `Range: ${controlnet.start_percent || "0"} - ${controlnet.end_percent || "1"}` : "",
        controlnet.preprocessor ? `Preprocessor: ${controlnet.preprocessor}` : "",
        controlnet.source ? `Source: ${controlnet.source}` : ""
      ]);
    }

    function renderImageAnalysis(metadata = {}, textChunks = {}, matches = [], warning = "") {
      const target = $("imageAnalysis");
      if (!target) return;
      const loras = Array.isArray(metadata?.loras) ? metadata.loras : [];
      const embeddings = Array.isArray(metadata?.embeddings) ? metadata.embeddings : [];
      const upscales = Array.isArray(metadata?.upscales) ? metadata.upscales : [];
      const controlnets = Array.isArray(metadata?.controlnets) ? metadata.controlnets : [];
      const isInitial = metadata?.source === "No image selected";
      const resourceBadges = [];
      if (metadata?.source && !isInitial) resourceBadges.push(metadata.source);
      if (loras.length) resourceBadges.push(`${loras.length} LoRA`);
      if (embeddings.length) resourceBadges.push(`${embeddings.length} Embedding`);
      if (upscales.length) resourceBadges.push(`${upscales.length} Upscale`);
      if (controlnets.length) resourceBadges.push(`${controlnets.length} ControlNet`);
      const resourceRows = [];
      if (metadata?.unet_name) resourceRows.push(["Model / UNET", metadata.unet_name]);
      if (metadata?.clip_name) resourceRows.push(["Text encoder / CLIP", metadata.clip_name]);
      if (metadata?.vae_name) resourceRows.push(["VAE", metadata.vae_name]);
      const otherRows = renderKeyValueGrid([
        ["Dimensions", metadata?.width && metadata?.height ? `${metadata.width} x ${metadata.height}` : ""],
        ["Steps", metadata?.steps],
        ["CFG", metadata?.cfg],
        ["Sampler", [metadata?.sampler_name, metadata?.scheduler].filter(Boolean).join(" / ")],
        ["Seed", metadata?.seed],
        ["Denoise", metadata?.denoise],
        ["Batch", metadata?.batch_size],
        ["Filename prefix", metadata?.filename_prefix],
        ["Text chunks", Object.keys(textChunks || {}).join(", ")]
      ]);
      const matchListHtml = (!isInitial && matches.length) ? `
        <p class="help-text">Compares the image-embedded prompts, LoRA names, and upscale model against the current <code>prompt_library.json</code> and <code>app_config.json</code>. Embedding and ControlNet data are parsed and displayed, but a database match is created only when the existing prompt-set text contains the same content. This process is read-only.</p>
        <div class="match-list">
          ${matches.map((item) => `
            <div class="match-row">
              <div class="match-section">${escapeHtml(sectionLabel(item.section))}</div>
              <div><div class="match-name">${escapeHtml(item.name)}</div><div class="match-key">${escapeHtml(item.key)}</div></div>
              <span class="badge soft">${escapeHtml([item.field, item.detail].filter(Boolean).join(" "))}</span>
            </div>
          `).join("")}
        </div>` : "";
      const blocks = [
        renderMetadataSection("Resource usage", renderKeyValueGrid(resourceRows), resourceBadges),
        loras.length ? renderMetadataSection("LoRA", renderLoraList(loras), [`${loras.length}`]) : "",
        embeddings.length ? renderMetadataSection("Embedding", renderEmbeddingList(embeddings), [`${embeddings.length}`]) : "",
        upscales.length ? renderMetadataSection("Upscale", renderUpscaleList(upscales), [`${upscales.length}`]) : "",
        controlnets.length ? renderMetadataSection("ControlNet", renderControlNetList(controlnets), [`${controlnets.length}`]) : "",
        renderTextBlock("Prompt", metadata?.positive || "", [metadata?.source && !isInitial ? metadata.source : ""].filter(Boolean)),
        renderTextBlock("Negative prompt", metadata?.negative || ""),
        renderMetadataSection("Other data", otherRows),
        matchListHtml ? renderMetadataSection("Database mapping", matchListHtml, ["Using existing JSON"]) : ""
      ].filter(Boolean).join("");
      const emptyMessage = isInitial
        ? "No image has been loaded. Generation metadata appears after an image is loaded."
        : "No displayable generation-metadata sections were found in this image.";
      target.innerHTML = `
        ${warning ? `<div class="analysis-warning">${escapeHtml(warning)}</div>` : ""}
        <div class="metadata-card">
          <h3>Generation metadata</h3>
          ${blocks || `<div class="analysis-empty">${escapeHtml(emptyMessage)}</div>`}
        </div>`;
      applyI18n(target);
      updateBottomBarSpace();
    }

    async function analyzeImageFile(file) {
      if (!file) return;
      const dropZone = $("imageDropZone");
      const preview = $("imagePreview");
      const fileName = $("imageFileName");
      const target = $("imageAnalysis");
      if (dropZone && preview) {
        dropZone.classList.add("has-image");
        preview.src = URL.createObjectURL(file);
        fileName.textContent = `${file.name} · ${Math.round(file.size / 1024)} KB`;
      }
      if (target) { target.innerHTML = '<div class="analysis-empty">Parsing image metadata...</div>'; applyI18n(target); }
      try {
        const buffer = await file.arrayBuffer();
        const png = readPngTextChunks(buffer);
        let metadata = null;
        let warning = "";
        if (png.ok) {
          metadata = extractImageMetadataFromChunks(png.chunks);
          if (!metadata) warning = Object.keys(png.chunks).length ? "Image text chunks were read, but no recognizable ComfyUI prompt or parameter format was found." : "This PNG does not contain recognizable AI-generation metadata text chunks.";
        } else {
          warning = png.error;
          metadata = null;
        }
        if (!metadata) {
          renderImageAnalysis({source: "Unknown", positive: "", negative: "", loras: [], embeddings: [], upscales: [], controlnets: []}, png.chunks || {}, [], warning);
          return;
        }
        const matches = matchPromptLibrary(metadata.positive || "", metadata.negative || "", metadata);
        renderImageAnalysis(metadata, png.chunks || {}, matches, warning);
      } catch (err) {
        if (target) { target.innerHTML = `<div class="analysis-warning">Parse failed:${escapeHtml(err.message || String(err))}</div>`; applyI18n(target); }
      }
    }

    function bindImageAnalyzeInputs() {
      const dropZone = $("imageDropZone");
      const input = $("imageFileInput");
      if (!dropZone || !input) return;
      renderImageAnalysis({source: "No image selected", positive: "", negative: "", loras: [], embeddings: [], upscales: [], controlnets: []}, {}, [], "");
      input.onchange = () => analyzeImageFile(input.files?.[0]);
      ["dragenter", "dragover"].forEach((eventName) => {
        dropZone.addEventListener(eventName, (event) => {
          event.preventDefault();
          event.stopPropagation();
          dropZone.classList.add("drag-over");
        });
      });
      ["dragleave", "dragend", "drop"].forEach((eventName) => {
        dropZone.addEventListener(eventName, (event) => {
          event.preventDefault();
          event.stopPropagation();
          if (eventName !== "drop") dropZone.classList.remove("drag-over");
        });
      });
      dropZone.addEventListener("drop", (event) => {
        dropZone.classList.remove("drag-over");
        const file = Array.from(event.dataTransfer?.files || []).find((item) => item.type.startsWith("image/"));
        if (file) analyzeImageFile(file);
      });
    }

    function renderAll() {
      renderModelTab();
      renderLoopTab();
      renderDatabaseTab();
      renderSingleTab();
      renderBottom();
      applyI18n();
      updateBottomBarSpace();
    }

    function updateBottomBarSpace() {
      const bottomBar = $("bottomBar");
      if (!bottomBar) return;
      const height = Math.ceil(bottomBar.getBoundingClientRect().height);
      document.documentElement.style.setProperty("--bottom-bar-height", `${height}px`);
    }

    function bindLayoutObservers() {
      updateBottomBarSpace();
      const bottomBar = $("bottomBar");
      if (!bottomBar) return;
      if ("ResizeObserver" in window) {
        const observer = new ResizeObserver(updateBottomBarSpace);
        observer.observe(bottomBar);
      }
      window.addEventListener("resize", updateBottomBarSpace);
      window.addEventListener("orientationchange", updateBottomBarSpace);
    }

    function bindInputs() {
      document.querySelectorAll(".tab-btn").forEach((button) => {
        button.onclick = () => {
          const previousTab = document.querySelector(".tab-btn.active")?.dataset.tab || "";
          const nextTab = button.dataset.tab || "";
          const touchesSingle = previousTab === "single" || nextTab === "single";
          if (touchesSingle) {
            clearTimeout(configSaveTimer);
            clearTimeout(librarySaveTimer);
            saveConfig();
            saveLibraryData();
          }
          document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
          document.querySelectorAll(".tab").forEach((tab) => tab.classList.remove("active"));
          button.classList.add("active");
          $(`tab-${nextTab}`).classList.add("active");
          if (touchesSingle) {
            renderAll();
          } else {
            renderBottom();
            updateBottomBarSpace();
          }
        };
      });
      bindImageAnalyzeInputs();
      bindSingleImageInputs();
      bindSingleEditorInputs();

      const modelFields = {
        width: (v) => activeModelPreset().settings.width = numericOrBlank(v),
        height: (v) => activeModelPreset().settings.height = numericOrBlank(v),
        steps: (v) => activeModelPreset().settings.steps = numericOrBlank(v),
        cfg: (v) => activeModelPreset().settings.cfg = numericOrBlank(v),
        denoise: (v) => activeModelPreset().settings.denoise = numericOrBlank(v),
        seed: (v) => activeModelPreset().settings.seed = numericOrBlank(v),
        seedMode: (v) => activeModelPreset().settings.seed_mode = v
      };
      Object.entries(modelFields).forEach(([id, setter]) => {
        $(id).oninput = () => { setter($(id).value); debounceSaveConfig(); renderPresetButtons("model"); renderBottom(); };
        $(id).onchange = $(id).oninput;
      });
      $("upscaleScale").oninput = () => { ensureUpscale(activeModelPreset().settings).scale_by = numericOrBlank($("upscaleScale").value); debounceSaveConfig(); };
      $("renameModelPreset").onclick = () => {
        const preset = activeModelPreset();
        const nextName = prompt(uiText("Rename preset"), preset.name);
        if (nextName && nextName.trim()) {
          preset.name = nextName.trim();
          debounceSaveConfig();
          renderPresetButtons("model");
        }
      };

      $("renameLoopPreset").onclick = () => {
        const index = config.active_loop_preset;
        const nextName = prompt(uiText("Rename preset"), loopPresetName(index));
        if (nextName && nextName.trim()) {
          activeLoopPreset().name = nextName.trim();
          debounceSaveLibrary();
          renderPresetButtons("loop");
        }
      };
      $("useGlobalPositive").onchange = () => { activeLoopPreset().settings.use_global_positive = $("useGlobalPositive").checked; debounceSaveLibrary(); };
      $("useGlobalNegative").onchange = () => { activeLoopPreset().settings.use_global_negative = $("useGlobalNegative").checked; debounceSaveLibrary(); };
      $("useCustomPrompt").onchange = () => { activeLoopPreset().settings.use_custom_prompt = $("useCustomPrompt").checked; debounceSaveLibrary(); };
      $("includeRandom").onchange = () => {
        activeLoopPreset().settings.include_random = $("includeRandom").checked;
        debounceSaveLibrary();
        renderLoopTab();
        renderBottom();
      };
      $("expandRandomPrompts").onchange = () => {
        activeLoopPreset().settings.random_prompt_mode = $("expandRandomPrompts").checked ? "all" : "random";
        debounceSaveLibrary();
        renderBottom();
      };

      const selectionButtons = [
        ["selectAllCharacters", "characters", "characterFilter", "characters", true, false],
        ["clearAllCharacters", "characters", "characterFilter", "characters", false, false],
        ["selectAllOutfits", "outfits", "outfitFilter", "outfits", true, false],
        ["clearAllOutfits", "outfits", "outfitFilter", "outfits", false, false],
        ["selectAllObjects", "objects", "objectFilter", "objects", true, false],
        ["clearAllObjects", "objects", "objectFilter", "objects", false, false],
        ["selectAllActions", "actions", "actionFilter", "actions", true, true],
        ["clearAllActions", "actions", "actionFilter", "actions", false, true],
      ];
      selectionButtons.forEach(([buttonId, section, filterId, settingKey, checked, grouped]) => {
        $(buttonId).onclick = () => setVisibleSelection(
          section,
          filterId,
          activeLoopPreset().settings[settingKey],
          checked,
          grouped,
        );
      });

      ["characterFilter", "outfitFilter", "objectFilter", "actionFilter"].forEach((id) => {
        const input = $(id);
        if (!input) return;
        input.oninput = renderLoopTab;
        input.addEventListener("input", renderLoopTab);
      });
      $("dbSection").onchange = () => {
        applyDbEditor({rerender: false, silent: true});
        debounceSaveLibrary();
        dbCurrentKey = "";
        dbCurrentGroupKey = "";
        dbEditorKey = "";
        renderDatabaseTab();
      };
      $("dbFilter").oninput = renderDatabaseTab;
      $("dbAddGroup").onclick = addCurrentSectionGroup;
      $("dbRenameGroup").onclick = renameCurrentSectionGroup;
      $("dbDeleteGroup").onclick = deleteCurrentSectionGroup;
      $("dbGroupSelect").onchange = () => {
        if (!applyDbEditor({rerender: false})) return;
        renderDatabaseTab();
        debounceSaveLibrary();
      };
      ["dbKey", "dbDisplayName", "dbPrompt", "dbNegativePrompt", "dbRandomPrompt", "dbCustomPrompt"].forEach((id) => {
        const field = $(id);
        if (!field) return;
        field.oninput = autoSaveDbEditor;
        field.onchange = autoSaveDbEditor;
      });
      $("dbAdd").onclick = async () => {
        if (!applyDbEditor({rerender: false, silent: true})) return;
        const section = $("dbSection").value;
        if (isGlobalSection(section)) return;
        const groupKey = dbCurrentGroupKey || groupEntries(section)[0]?.[0] || "default";
        let key = "new_item";
        let n = 1;
        while (library[section][key]) key = `new_item_${n++}`;
        library[section][key] = {
          name: "New item",
          group: groupKey,
          prompt: "",
          negative_prompt: ""
        };
        applyRecordOrderFields(section, library[section][key], groupKey, nextRecordSortIndex(section, groupKey) + 1);
        if (section === "actions") {
          library[section][key].random_prompt = "";
          library[section][key].custom_prompt = "";
        }
        dbCurrentKey = key;
        dbCurrentGroupKey = groupKey;
        dbDirty = true;
        renderAll();
        loadDbEditor();
        await saveLibrary({applyCurrent: false, message: uiText("New item saved")});
      };
      // The data editor now autosaves; copy, delete, and manual-save buttons have been removed.
      $("refreshModels").onclick = refreshModels;

      $("repeatCount").oninput = () => { config.run.repeat_count = Number($("repeatCount").value); debounceSaveConfig(); renderBottom(); };
      $("startBtn").onclick = startRun;
      $("stopBtn").onclick = stopRun;
    }

    async function saveLibrary(options = {}) {
      const {applyCurrent = true, message = uiText("Changes saved")} = options;
      if (applyCurrent && !applyDbEditor({rerender: false})) return;
      await saveLibraryData();
      dbDirty = false;
      renderAll();
      setMessage(message);
    }

    async function buildPrompts() {
      await saveConfig();
      await saveLibraryData();
      const result = await api("/api/build", {method: "POST"});
      if (result.config) {
        config = result.config;
        renderAll();
      }
      let message = `Generated prompts.json with ${result.count} image(s)`;
      if (result.seed_info?.mode === "random" && result.seed_info.updated) {
        message += `, random seed updated to ${result.seed_info.seed}`;
      }
      setMessage(message);
      await updateRunStatus();
    }

    async function dryRun() {
      await saveConfig();
      await saveLibraryData();
      const result = await api("/api/build", {method: "POST"});
      if (result.config) {
        config = result.config;
        renderAll();
      }
      const preview = result.preview.map((item) => {
        const objectPart = item.object ? ` / ${item.object}` : "";
        return `${String(item.index).padStart(5, "0")} ${item.character} / ${item.outfit}${objectPart} / ${item.action}`;
      }).join("\n");
      $("logs").textContent = preview || uiText("No items");
    }

    async function startRun() {
      const activeTab = document.querySelector(".tab-btn.active")?.dataset.tab || "model";
      if (activeTab === "single") {
        await startSingleRun();
        return;
      }
      try {
        $("startBtn").disabled = true;
        const modelOverride = currentModelOverrideForRun();
        await saveConfig({raise: true});
        await saveLibraryData();
        const result = await api("/api/run/start", {
          method: "POST",
          body: JSON.stringify({model_override: modelOverride})
        });
        if (result.config) {
          config = result.config;
          renderAll();
        }
        setMessage(result.message);
      } catch (err) {
        setMessage(err.message || uiText("Failed to start run"));
      } finally {
        await updateRunStatus();
      }
    }

    async function startSingleRun() {
      try {
        $("startBtn").disabled = true;
        syncModelInputsFromDom();
        await saveConfig({raise: true});
        await saveLibraryData();
        const single = singleSettings();
        if ((single.source_mode || "previous") === "previous") {
          if (lastSinglePreviewName) renderSingleReferenceFromOutput(lastSinglePreviewName);
          else clearSingleReferenceImage();
        }
        const modelOverride = currentModelOverrideForRun();
        const result = await api("/api/single/run/start", {
          method: "POST",
          body: JSON.stringify({
            source_mode: single.source_mode || "previous",
            model_override: modelOverride
          })
        });
        if (result.config) {
          config = result.config;
          renderAll();
        }
        setMessage(result.message);
      } catch (err) {
        setMessage(err.message || uiText("Failed to run single-image generation"));
      } finally {
        await updateRunStatus();
      }
    }

    async function stopRun() {
      try {
        const result = await api("/api/run/stop", {method: "POST"});
        setMessage(result.message);
      } catch (err) {
        setMessage(err.message || uiText("Failed to stop"));
      } finally {
        await updateRunStatus();
      }
    }

    async function refreshModels() {
      try {
        syncModelInputsFromDom();
        const result = await api("/api/comfy/models");
        modelLists = result.models || {};
        renderModelTab();
        renderSingleTab();
        applyI18n(document.body);
        setMessage(uiText("Model list refreshed"));
      } catch (err) {
        setMessage(uiText("Failed to load the model list. Start ComfyUI first."));
      }
    }

    async function updateComfyStatus() {
      try {
        const result = await api("/api/comfy/status");
        $("comfyDot").classList.toggle("ok", !!result.connected);
        $("comfyText").textContent = result.connected ? uiText("ComfyUI connected") : uiText("Start ComfyUI first");
      } catch {
        $("comfyDot").classList.remove("ok");
        $("comfyText").textContent = uiText("Start ComfyUI first");
      }
    }

    async function updateRunStatus() {
      const result = await api("/api/run/status");
      $("runProgress").textContent = `${result.current} / ${result.total}`;
      const seconds = Number(result.average_duration || result.last_duration || 0);
      $("secondsPerImage").textContent = seconds > 0 ? `${seconds.toFixed(1)}${uiText("sec/image")}` : "--";
      $("runStatusText").textContent = result.status_message ? uiRuntimeText(result.status_message) : (result.running ? uiText("Running") : uiText("Idle"));
      $("startBtn").disabled = !!result.running;
      $("stopBtn").disabled = !result.running;
      $("logs").textContent = (result.logs || []).map(uiRuntimeText).join("\n");
      if (!result.running && Array.isArray(result.last_outputs) && result.last_outputs.length) renderSingleOutputPreview(result.last_outputs[0]);
      updateBottomBarSpace();
    }

    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, (ch) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[ch]));
    }

    function safeKey(value) {
      return String(value || "").trim().replace(/\s+/g, "_").replace(/[^A-Za-z0-9_.-]/g, "_").replace(/_+/g, "_").replace(/^_+|_+$/g, "");
    }

    async function init() {
      bindUiChromeControls();
      bindLayoutObservers();
      bindInputs();
      const result = await api("/api/state");
      config = result.config;
      library = result.library;
      renderAll();
      await updateComfyStatus();
      await refreshModels();
      await updateRunStatus();
      setInterval(updateComfyStatus, 5000);
      setInterval(updateRunStatus, 2000);
    }

    init().catch((err) => {
      document.body.innerHTML = `<pre>${escapeHtml(err.stack || err.message)}</pre>`;
    });
  </script>
</body>
</html>"""


HTML_BYTES = HTML.encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    server_version = "ComfyBatchWeb/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def read_body(self) -> Any:
        length = int(self.headers.get("Content-Length", "0"))
        if not length:
            return None
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw) if raw else None

    def send_data(self, data: Any, status: int = 200) -> None:
        payload = json.dumps(data, ensure_ascii=False, separators=JSON_RESPONSE_SEPARATORS).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def send_binary(self, content: bytes, content_type: str = "application/octet-stream") -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def send_html(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(HTML_BYTES)))
        self.end_headers()
        self.wfile.write(HTML_BYTES)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/":
                self.send_html()
            elif path == "/api/state":
                config, library = load_state()
                self.send_data({"ok": True, "config": config, "library": library})
            elif path == "/api/comfy/status":
                self.send_data({"ok": True, **get_comfy_status(load_config(write_back=False))})
            elif path == "/api/comfy/models":
                self.send_data({"ok": True, "models": get_comfy_models(load_config(write_back=False))})
            elif path == "/api/comfy/view":
                query = parse_qs(urlparse(self.path).query)
                image_name = (query.get("name") or query.get("filename") or [""])[0]
                content, content_type = download_comfy_output_image(load_config(write_back=False)["comfy_url"], image_name)
                self.send_binary(content, content_type)
            elif path == "/api/run/status":
                self.send_data({"ok": True, **run_state_snapshot()})
            else:
                self.send_error(404)
        except Exception as exc:  # noqa: BLE001
            self.send_data({"ok": False, "error": str(exc)}, status=500)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/api/config":
                config = self.read_body()
                config.pop("loop_presets", None)
                config.pop("loop_preset_names", None)
                migrate_config(config)
                write_json(CONFIG_PATH, config)
                self.send_data({"ok": True})
            elif path == "/api/library":
                library = normalize_library(self.read_body())
                if not library.get("loop_presets"):
                    library["loop_presets"] = default_loop_presets(library)
                    library = normalize_library(library)
                write_json(LIBRARY_PATH, library)
                self.send_data({"ok": True})
            elif path == "/api/build":
                config, library = load_state()
                payload = build_prompt_payload(library, config)
                seed_info = sync_seed_setting_after_payload(config, payload, advance_increment=False)
                if config["run"].get("save_prompts_json", True):
                    prompts_path = BASE_DIR / config["run"].get("prompts_file", "prompts.json")
                    write_json(prompts_path, payload)
                if seed_info.get("updated"):
                    write_json(CONFIG_PATH, config)
                self.send_data(
                    {
                        "ok": True,
                        "count": payload["count"],
                        "preview": payload["items"][:20],
                        "config": config,
                        "seed_info": seed_info,
                    }
                )
            elif path == "/api/run/start":
                with STATE_LOCK:
                    if RUN_STATE["running"]:
                        self.send_data({"ok": False, "error": "Run already active"}, status=409)
                        return
                request_data = self.read_body() or {}
                config, library = load_state()
                apply_model_settings_override(config, request_data)
                payload = build_prompt_payload(library, config)
                selected_count = len(select_run_items(payload, config))
                seed_info = sync_seed_setting_after_payload(config, payload, advance_increment=True)
                if config["run"].get("save_prompts_json", True):
                    prompts_path = BASE_DIR / config["run"].get("prompts_file", "prompts.json")
                    write_json(prompts_path, payload)
                write_json(CONFIG_PATH, config)
                thread = threading.Thread(target=run_worker, args=(config, payload), daemon=True)
                thread.start()
                message = f"Started {selected_count} job(s)"
                if seed_info["mode"] == "increment":
                    message += f". Next seed: {seed_info['seed']}"
                elif seed_info["mode"] == "random":
                    label = "Last random seed" if selected_count > 1 else "Random seed"
                    message += f". {label}: {seed_info['seed']}"
                self.send_data(
                    {
                        "ok": True,
                        "message": message,
                        "config": config,
                        "seed_info": seed_info,
                    }
                )
            elif path == "/api/single/run/start":
                with STATE_LOCK:
                    if RUN_STATE["running"]:
                        self.send_data({"ok": False, "error": "Run already active"}, status=409)
                        return
                request_data = self.read_body() or {}
                config, _library = load_state()
                apply_model_settings_override(config, request_data)
                payload = build_single_image_payload(config, _library, request_data)
                selected_count = len(select_run_items(payload, config))
                seed_info = sync_seed_setting_after_payload(config, payload, advance_increment=True)
                if config["run"].get("save_prompts_json", True):
                    write_json(BASE_DIR / "single_prompt.json", payload)
                write_json(CONFIG_PATH, config)
                thread = threading.Thread(target=run_worker, args=(config, payload), daemon=True)
                thread.start()
                message = f"Started single image job ({selected_count})"
                if seed_info["mode"] == "increment":
                    message += f". Next seed: {seed_info['seed']}"
                elif seed_info["mode"] == "random":
                    message += f". Random seed: {seed_info['seed']}"
                self.send_data({"ok": True, "message": message, "config": config, "seed_info": seed_info})
            elif path == "/api/run/stop":
                no_active_run = False
                with STATE_LOCK:
                    if not RUN_STATE["running"]:
                        RUN_STATE["stop_requested"] = False
                        RUN_STATE["status_message"] = "Idle"
                        no_active_run = True
                    else:
                        RUN_STATE["stop_requested"] = True
                        RUN_STATE["status_message"] = "Stop requested"
                if no_active_run:
                    self.send_data({"ok": True, "message": "No active run"})
                    return
                append_log("Stop requested by user.")
                try:
                    post_json(load_config(write_back=False)["comfy_url"], "/interrupt", {}, timeout=3)
                except Exception:
                    pass
                self.send_data({"ok": True, "message": "Stop requested"})
            else:
                self.send_error(404)
        except Exception as exc:  # noqa: BLE001
            self.send_data({"ok": False, "error": str(exc)}, status=500)


def main() -> int:
    if not LIBRARY_PATH.exists():
        print(f"Missing {LIBRARY_PATH.name}", file=sys.stderr)
        return 1
    load_state()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}"
    print(f"Anima Image Set Generator: {url}")
    print("Start ComfyUI manually first. Default URL: http://127.0.0.1:8188")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nBye.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
