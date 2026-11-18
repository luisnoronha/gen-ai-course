"""What the lab of session 9 shares: loading your starter file, and the models."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
STARTER = HERE.parent / "starter"
SOLUTIONS = HERE.parents[3] / "private" / "course-02-agentic-ai" / "reference" / "session-09"
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")  # keep the terminal quiet
SMALL = os.getenv("OPENAI_MODEL_SMALL", "gpt-4.1-nano")
LARGE = os.getenv("OPENAI_MODEL_LARGE", "gpt-4.1")
PRICES = {"gpt-4.1": (2.00, 8.00), "gpt-4.1-mini": (0.40, 1.60), "gpt-4.1-nano": (0.10, 0.40)}  # USD per 1M tokens (in, out)
BACKUP_MARKUP = 1.25  # provider B: the same strong model in the lab, sold 25% dearer (simulated second provider)


def use_solutions() -> bool:
    """Trainer only: LAB_SOLUTIONS=1 runs the solutions instead of starter/, without touching starter/."""
    return os.environ.get("LAB_SOLUTIONS") == "1" and SOLUTIONS.is_dir()


def load_starter(name: str):
    folder = SOLUTIONS if use_solutions() else STARTER
    spec = importlib.util.spec_from_file_location(f"s09_{name}", folder / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"s09_{name}"] = module
    spec.loader.exec_module(module)
    return module


def patient(model: Any) -> Any:
    """An OpenAI model that retries more when rate-limited. Built inside the run's event loop."""
    if not (isinstance(model, str) and model.startswith("openai:")):
        return model
    from openai import AsyncOpenAI
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider
    return OpenAIChatModel(model.removeprefix("openai:"), provider=OpenAIProvider(openai_client=AsyncOpenAI(max_retries=6)))


def models(chosen: Any) -> dict[str, Any]:
    """{"small": ..., "large": ..., "backup": ...}. The real OpenAI models, or the test doubles the tests give.

    "backup" stands for a second provider. In the lab it is the same strong model, so the exercise runs with one API key."""
    if isinstance(chosen, dict):
        return {"backup": chosen["large"], **chosen}
    if isinstance(chosen, str):
        return {"small": f"openai:{SMALL}", "large": f"openai:{LARGE}", "backup": f"openai:{LARGE}"}
    return {"small": chosen, "large": chosen, "backup": chosen}


def model_name(model: Any) -> str:
    return model.removeprefix("openai:") if isinstance(model, str) else getattr(model, "model_name", "test")
