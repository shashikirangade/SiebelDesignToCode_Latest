# gemini_api_handler.py
from pathlib import Path
import os
import mimetypes
import google.generativeai as genai

def _detect_mime(p: Path) -> str:
    mt, _ = mimetypes.guess_type(str(p))
    # default to png if unknown
    return mt or "image/png"

def call_gemini_api(image_path: Path, model: str, max_output_tokens: int) -> str | None:
    """
    Returns the raw text response (two fenced code blocks) or raises
    a detailed Exception that upstream can surface to the user.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is not set")

    genai.configure(api_key=api_key)
    model_name = (model or "gemini-1.5-flash").strip()

    # Fallback if someone selects a future model
    if model_name.lower() in {"gemini-2.5-pro", "gemini-2.0-pro"}:
        model_name = "gemini-1.5-pro"

    try:
        mdl = genai.GenerativeModel(model_name)
    except Exception as e:
        raise RuntimeError(f"Failed to init model '{model_name}': {e}")

    # Reuse your OpenAI instructions verbatim so parsing stays identical
    from openai_api_handler import instructions  # import the same prompt text
    mime = _detect_mime(image_path)
    img_bytes = image_path.read_bytes()

    try:
        resp = mdl.generate_content(
            [
                {"text": instructions},
                {"inline_data": {"mime_type": mime, "data": img_bytes}},
            ],
            generation_config={
                "max_output_tokens": max_output_tokens,
                # optional: raise limits a bit if needed
                # "temperature": 0.2,
            },
            # optional: relax safety if you hit blocks (tune as needed)
            # safety_settings=[{"category":"HARM_CATEGORY_HARASSMENT","threshold":"BLOCK_NONE"}, ...]
        )
    except Exception as e:
        # transport / quota / auth errors
        raise RuntimeError(f"Gemini request failed: {e}")

    # SDK can return finishes with filters/blocks; capture details
    if not hasattr(resp, "text") or not resp.text:
        # gather diagnostics if available
        diag = []
        if getattr(resp, "prompt_feedback", None):
            diag.append(f"prompt_feedback={resp.prompt_feedback}")
        if getattr(resp, "candidates", None):
            diag.append(f"candidates={getattr(resp, 'candidates', None)}")
        raise RuntimeError("Gemini returned no text. " + (" ".join(map(str, diag)) if diag else ""))

    return resp.text