import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class LLMIoTExtractor:
    """
    Extract IoT commands from natural language using an LLM, then validate and
    normalize the output according to iot_command_format_v3.md.
    """

    ALLOWED_LOCATIONS = {"livingroom", "bedroom"}

    ALLOWED_DEVICES = {
        "livingroom_light",
        "bedroom_light",
        "livingroom_fan",
        "bedroom_fan",
    }

    ALLOWED_ACTIONS = {
        "on",
        "off",
        "set_brightness",
        "brighten",
        "dim",
        "set_color_temp",
        "set_color",
        "set_speed",
        "increase_speed",
        "decrease_speed",
    }

    ALLOWED_COLORS = {
        "red",
        "green",
        "blue",
        "white",
        "warm_white",
        "neutral_white",
        "cool_white",
        "yellow",
        "cyan",
        "purple",
    }

    DEVICE_TO_LOCATION = {
        "livingroom_light": "livingroom",
        "bedroom_light": "bedroom",
        "livingroom_fan": "livingroom",
        "bedroom_fan": "bedroom",
    }

    DEVICE_ACTION_COMPATIBILITY = {
        "livingroom_light": {
            "on",
            "off",
            "set_brightness",
            "brighten",
            "dim",
            "set_color_temp",
            "set_color",
        },
        "bedroom_light": {
            "on",
            "off",
            "set_brightness",
            "brighten",
            "dim",
            "set_color_temp",
            "set_color",
        },
        "livingroom_fan": {
            "on",
            "off",
            "set_speed",
            "increase_speed",
            "decrease_speed",
        },
        "bedroom_fan": {
            "on",
            "off",
            "set_speed",
            "increase_speed",
            "decrease_speed",
        },
    }

    def __init__(self) -> None:
        self.llm_api_mode = os.getenv("LLM_API_MODE", "").strip().lower()

        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "").strip().rstrip("/")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "").strip()

        self.remote_llm_api_key = os.getenv("REMOTE_LLM_API_KEY", "").strip()
        self.remote_llm_api_url = os.getenv("REMOTE_LLM_API_URL", "").strip()
        self.remote_llm_model = os.getenv("REMOTE_LLM_MODEL", "").strip()

        self.spec_text = self._load_spec_text()

    def _load_spec_text(self) -> str:
        spec_path = Path(__file__).with_name("iot_command_format_v3.md")
        if not spec_path.exists():
            raise FileNotFoundError(f"Spec file not found: {spec_path}")

        content = spec_path.read_text(encoding="utf-8").strip()
        if not content:
            raise ValueError(f"Spec file is empty: {spec_path}")

        return content

    def extract(self, user_input: str) -> List[Dict[str, Any]]:
        user_input = (user_input or "").strip()
        if not user_input:
            return []

        raw_output = self._call_llm(user_input)
        parsed = self._parse_llm_output(raw_output)
        return self._validate_and_normalize_commands(parsed)

    def _call_llm(self, user_input: str) -> str:
        if self.llm_api_mode == "local":
            return self._call_local_ollama(user_input)
        if self.llm_api_mode == "remote":
            return self._call_remote_llm(user_input)

        raise ValueError(
            f"LLM_API_MODE not configured correctly: {self.llm_api_mode!r}. "
            "Use 'local' or 'remote'."
        )

    def _call_local_ollama(self, user_input: str) -> str:
        if not self.ollama_base_url:
            raise ValueError("OLLAMA_BASE_URL is not set")
        if not self.ollama_model:
            raise ValueError("OLLAMA_MODEL is not set")

        prompt = f"{self.spec_text}\n\nInput: {user_input}\nOutput:"
        payload = {"model": self.ollama_model, "prompt": prompt, "stream": False}

        logger.info("Calling local Ollama model=%s", self.ollama_model)
        with httpx.Client(timeout=120.0) as client:
            response = client.post(f"{self.ollama_base_url}/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()

        text = data.get("response", "")
        if not isinstance(text, str):
            raise ValueError("Invalid Ollama response format: 'response' is not a string")
        return text.strip()

    def _call_remote_llm(self, user_input: str) -> str:
        if not self.remote_llm_api_url:
            raise ValueError("REMOTE_LLM_API_URL is not set")
        if not self.remote_llm_api_key:
            raise ValueError("REMOTE_LLM_API_KEY is not set")
        if not self.remote_llm_model:
            raise ValueError("REMOTE_LLM_MODEL is not set")

        headers = {
            "Authorization": f"Bearer {self.remote_llm_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.remote_llm_model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": self.spec_text},
                {"role": "user", "content": user_input},
            ],
        }

        logger.info("Calling remote LLM model=%s", self.remote_llm_model)
        with httpx.Client(timeout=120.0) as client:
            response = client.post(self.remote_llm_api_url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not isinstance(text, str):
            raise ValueError("Invalid remote LLM response format: content is not a string")
        return text.strip()

    def _parse_llm_output(self, raw_output: str) -> List[Any]:
        raw_output = (raw_output or "").strip()
        if not raw_output:
            return []

        try:
            parsed = json.loads(raw_output)
        except json.JSONDecodeError:
            parsed = self._extract_first_json_array(raw_output)

        if not isinstance(parsed, list):
            raise ValueError("LLM output is not a JSON array")
        return parsed

    def _extract_first_json_array(self, text: str) -> List[Any]:
        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end == -1 or end < start:
            raise ValueError("No JSON array found in LLM output")

        candidate = text[start : end + 1]
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Failed to parse JSON array from LLM output: {exc}") from exc

        if not isinstance(parsed, list):
            raise ValueError("Extracted JSON content is not a list")
        return parsed

    def _validate_and_normalize_commands(self, commands: List[Any]) -> List[Dict[str, Any]]:
        validated: List[Dict[str, Any]] = []
        for item in commands:
            if not isinstance(item, dict):
                continue
            cmd = self._validate_single_command(item)
            if cmd is not None:
                validated.append(cmd)
        return validated

    def _validate_single_command(self, cmd: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        device = cmd.get("device")
        location = cmd.get("location")
        action = cmd.get("action")
        parameters = cmd.get("parameters", {})

        if not isinstance(device, str) or device not in self.ALLOWED_DEVICES:
            return None
        if not isinstance(location, str) or location not in self.ALLOWED_LOCATIONS:
            return None
        if self.DEVICE_TO_LOCATION.get(device) != location:
            return None
        if not isinstance(action, str) or action not in self.ALLOWED_ACTIONS:
            return None
        if action not in self.DEVICE_ACTION_COMPATIBILITY.get(device, set()):
            return None
        if not isinstance(parameters, dict):
            return None

        normalized_parameters = self._normalize_parameters(action, parameters)
        if normalized_parameters is None:
            return None

        return {
            "device": device,
            "location": location,
            "action": action,
            "parameters": normalized_parameters,
        }

    def _normalize_parameters(self, action: str, parameters: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        no_param_actions = {"on", "off", "brighten", "dim", "increase_speed", "decrease_speed"}
        if action in no_param_actions:
            return {}

        if action == "set_brightness":
            brightness = self._to_int(parameters.get("brightness"))
            if brightness is None:
                return None
            return {"brightness": self._clamp(brightness, 0, 100)}

        if action == "set_speed":
            speed = self._to_int(parameters.get("speed"))
            if speed is None:
                return None
            return {"speed": self._clamp(speed, 0, 100)}

        if action == "set_color_temp":
            color_temp = self._to_int(parameters.get("color_temp"))
            if color_temp is None:
                return None
            return {"color_temp": self._clamp(color_temp, 2700, 6500)}

        if action == "set_color":
            color = parameters.get("color")
            if isinstance(color, str):
                normalized_color = color.strip().lower().replace(" ", "_").replace("-", "_")
                if normalized_color in self.ALLOWED_COLORS:
                    return {"color": normalized_color}

            red = self._to_int(parameters.get("red"))
            green = self._to_int(parameters.get("green"))
            blue = self._to_int(parameters.get("blue"))
            if red is None or green is None or blue is None:
                return None
            return {
                "red": self._clamp(red, 0, 255),
                "green": self._clamp(green, 0, 255),
                "blue": self._clamp(blue, 0, 255),
            }

        return None

    @staticmethod
    def _clamp(value: int, low: int, high: int) -> int:
        return max(low, min(high, value))

    @staticmethod
    def _to_int(value: Any) -> Optional[int]:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(round(value))
        if isinstance(value, str):
            text = value.strip().replace("%", "").replace("K", "").replace("k", "")
            if not text:
                return None
            try:
                return int(round(float(text)))
            except ValueError:
                return None
        return None
