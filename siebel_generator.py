# siebel_generator.py
import os
import re
from pathlib import Path
from openai_api_handler import call_openai_api
from gemini_api_handler import call_gemini_api 
#from .main_router import _webtemplate_dir

def _webtemplate_dir(out: Path) -> Path:
    """Create/return the webtemplate subfolder under the run folder."""
    wt = out / "webtemplate"
    wt.mkdir(parents=True, exist_ok=True)
    return wt

def extract_block(text: str, lang: str) -> str:
    pattern = rf"```{lang}\s+([\s\S]*?)```"
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(1).strip() if m else ""

def parse_fenced_sections(raw: str) -> tuple[str, str, str]:
    return extract_block(raw, "json"), extract_block(raw, "html"), extract_block(raw, "css")
def _call_model(image_path: Path, model: str, max_tokens: int) -> tuple[str|None, str|None]:
    from openai_api_handler import call_openai_api
    try:
        if (model or "").lower().startswith("gemini"):
            from gemini_api_handler import call_gemini_api
            return call_gemini_api(image_path, model, max_tokens), None
        else:
            return call_openai_api(image_path, model, max_tokens), None
    except Exception as e:
        return None, str(e)
    
def process_siebel_conversion(image_path: str, out_dir: str, model: str = "gpt-5", max_completion_tokens: int = 6000) -> dict:
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    raw_file = out / "raw_response.txt"
    html_file = out / "generated.html"
    css_file  = out / "style.css"
    json_file = out / "manifest.json"

    raw, err = _call_model(Path(image_path), model, max_completion_tokens)

    if not raw:
        msg = f"Conversion failed: {err or 'Unknown error'}"
        raw_file.write_text(msg, "utf-8")
        html_file.write_text(f"<html><body><h2>Conversion failed</h2><pre>{msg}</pre></body></html>", "utf-8")
        css_file.write_text("body { background:#111; color:#eee; font-family:Arial,sans-serif; }", "utf-8")
        json_file.write_text("{}", "utf-8")
        return {"raw": str(raw_file), "html": str(html_file), "css": str(css_file), "json": str(json_file)}

    raw_file.write_text(raw, "utf-8")
    manifest, html, css = parse_fenced_sections(raw)
    html_file.write_text(html or "", "utf-8")
    css_file.write_text(css or "", "utf-8")
    json_file.write_text((manifest or "{}"), "utf-8")
    return {"raw": str(raw_file), "html": str(html_file), "css": str(css_file), "json": str(json_file)}
