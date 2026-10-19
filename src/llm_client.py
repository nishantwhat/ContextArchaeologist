"""Client interface for interacting with LLM backends (Ollama local / Mocked rule fallback)."""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional


class OllamaClient:
    def __init__(self, model_name: str = "llama3:latest", base_url: str = "http://localhost:11434"):
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self._is_available: Optional[bool] = None

    def is_available(self) -> bool:
        if self._is_available is not None:
            return self._is_available
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags", headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = [m.get("name", "") for m in data.get("models", [])]
                self._is_available = any(self.model_name in m for m in models)
                return self._is_available
        except Exception:
            self._is_available = False
            return False

    def generate(self, prompt: str, system: Optional[str] = None, timeout: int = 45) -> str:
        """Call Ollama's generate API synchronously with timeout."""
        payload: Dict[str, Any] = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,  # Low temperature for factual accuracy
                "num_ctx": 4096,
            },
        }
        if system:
            payload["system"] = system

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=data_bytes,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp_data = json.loads(resp.read().decode("utf-8"))
            return resp_data.get("response", "").strip()

    def generate_json(self, prompt: str, system: Optional[str] = None, timeout: int = 45) -> Dict[str, Any]:
        """Generate response formatted as JSON."""
        full_system = (system or "") + "\nRESPOND IN STRICT VALID JSON ONLY. NO MARKDOWN CODE BLOCKS."
        raw = self.generate(prompt=prompt, system=full_system, timeout=timeout)
        # Strip potential markdown code fences
        clean = raw.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[-1]
        if clean.endswith("```"):
            clean = clean.rsplit("\n", 1)[0]
        clean = clean.strip()
        if clean.startswith("json"):
            clean = clean[4:].strip()
        try:
            return json.loads(clean)
        except Exception:
            # Fallback regex search for JSON object
            import re
            m = re.search(r"\{.*\}", clean, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(0))
                except Exception:
                    pass
            return {"error": "Failed to parse model JSON", "raw": raw}
