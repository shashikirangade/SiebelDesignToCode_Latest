# main_router.py
import os
import json
import shutil
import re
from pathlib import Path
from datetime import datetime
# add imports near the top
from bs4 import BeautifulSoup
from copy import deepcopy
from client_script_bot import ask_client_script_bot
from flask import (
    Flask, request, render_template, send_file, jsonify, abort
)
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()


# Use your existing logic module (unchanged)
from siebel_generator import process_siebel_conversion

APP_ROOT = Path(__file__).parent.resolve()
UPLOAD_ROOT = APP_ROOT / "uploads"
OUTPUT_ROOT = APP_ROOT / "output"
UPLOAD_ROOT.mkdir(exist_ok=True)
OUTPUT_ROOT.mkdir(exist_ok=True)

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("FLASK_SECRET", "design-to-code-secret")

@app.route("/OpenUICodeGen", methods=["GET"])
def openui_codegen():  # existing PM/PR generator page
    return render_template("pmpr_generator.html", strings={"app_title": "Siebel Open UI – Code Gen"})

@app.route("/ClientScriptBot", methods=["GET"])
def client_script_bot_page():
    return render_template("client_script_bot.html", strings={"app_title":"Client Script Bot"})

@app.route("/api/client-script/ask", methods=["POST"])
def client_script_bot_api():
    data = request.get_json(silent=True) or {}
    msg = (data.get("message") or "").strip()
    ctx = (data.get("context_type") or "").strip()
    if not msg:
        return jsonify({"error":"message required"}), 400
    try:
        answer = ask_client_script_bot(msg, ctx)
        if isinstance(answer, dict):  # when returning both html + flag
            return jsonify(answer)
        else:
            return jsonify({"answer": answer})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def _ts_dir() -> Path:
    """Create timestamped output directory."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = OUTPUT_ROOT / stamp
    out.mkdir(parents=True, exist_ok=True)
    return out


def _inline_preview_html(out_dir: Path) -> str:
    """Return HTML with CSS inlined so the preview iframe renders correctly."""
    html_path = out_dir / "generated.html"
    css_path = out_dir / "style.css"

    if not html_path.exists():
        return "<!doctype html><html><body><h3>No HTML generated.</h3></body></html>"

    html = html_path.read_text("utf-8", errors="ignore")
    css = css_path.read_text("utf-8", errors="ignore") if css_path.exists() else ""

    if css.strip():
        # 1) Replace any <link ... href="style.css" ...> (self-closing tolerated)
        html_inlined = re.sub(
            r"<link[^>]*href=[\"']?style\.css[\"']?[^>]*\/?>",
    f"<style>{css}</style>",
            html,
            flags=re.IGNORECASE,
        )

        # 2) If nothing replaced, inject before </head>
        if html_inlined == html:
            if re.search(r"</head>", html, re.IGNORECASE):
                html_inlined = re.sub(
                    r"</head>", f"<style>{css}</style></head>", html, flags=re.IGNORECASE
                )
            else:
                # 3) No <head> → create one (inside existing <html> if present)
                if re.search(r"<html[^>]*>", html, re.IGNORECASE):
                    html_inlined = re.sub(
                        r"<html[^>]*>",
                        lambda m: m.group(0) + f"\n<head><style>{css}</style></head>",
                        html,
                        count=1,
                        flags=re.IGNORECASE,
                    )
                else:
                    html_inlined = f"<html><head><style>{css}</style></head>{html}</html>"
    else:
        html_inlined = html

    return html_inlined



@app.route("/")
def home():
    # texts from manifest for topbar/submenus, etc.
    mf = (APP_ROOT / "manifest.json")
    strings = json.loads(mf.read_text("utf-8")) if mf.exists() else {}
    return render_template("webtemplates.html", strings=strings)

# ---------- helpers ----------

def _attrs_string(tag) -> str:
    """Serialize attributes of a BeautifulSoup tag."""
    parts = []
    for k, v in (tag.attrs or {}).items():
        if isinstance(v, list):
            v = " ".join(v)
        parts.append(f'{k}="{v}"')
    return (" " + " ".join(parts)) if parts else ""

def _empty_shell(tag) -> str:
    return f"<{tag.name}{_attrs(tag)}></{tag.name}>"

# main_router.py (top-level helpers)
def _webtemplate_dir(out_dir: Path) -> Path:
    wt = out_dir / "webtemplate"
    wt.mkdir(parents=True, exist_ok=True)
    return wt

def _role_to_applet_template(name: str, role: str, inner_html: str) -> str:
    """Generate Siebel applet template based on component role"""
    r = (role or "").lower()
    name_safe = _safe_name(name)
    
    if r in {"list", "navigation", "grid"}:
        return f"""<siebel:Applet name="{name_safe}" type="List">
  <siebel:ListHeader/>
  <siebel:ListRows>
    {inner_html}
  </siebel:ListRows>
</siebel:Applet>
"""
    elif r in {"form", "main", "content", "banner", "region"}:
        return f"""<siebel:Applet name="{name_safe}" type="Form">
  <siebel:FormBody>
    {inner_html}
  </siebel:FormBody>
</siebel:Applet>
"""
    elif r in {"button", "toolbar", "action"}:
        return f"""<siebel:Applet name="{name_safe}" type="Toolbar">
  <siebel:ToolbarBody>
    {inner_html}
  </siebel:ToolbarBody>
</siebel:Applet>
"""
    else:
        # Generic applet for other roles
        return f"""<siebel:Applet name="{name_safe}" type="Generic">
  {inner_html}
</siebel:Applet>
"""
def _clean_html_content(html_content: str) -> str:
    """Clean up HTML content by removing extra whitespace and formatting."""
    # Remove leading/trailing whitespace from each line
    lines = [line.strip() for line in html_content.split('\n')]
    # Remove empty lines
    lines = [line for line in lines if line]
    return '\n'.join(lines)

def _attrs(tag):
    parts=[]
    for k,v in (tag.attrs or {}).items():
        if isinstance(v, list): v=" ".join(v)
        parts.append(f'{k}="{v}"')
    return (" " + " ".join(parts)) if parts else ""
def _build_view_template(order, found_tags) -> str:
    """
    Build the view webtemplate: same containers in order, but empty.
    Adds lightweight includes pointing to applet files.
    """
    shells = []
    for item in order:
        tag = found_tags.get(item["name"])
        if not tag:
            continue
        shells.append(f"<!-- {item['name']} ({item.get('role','')}) -->")
        shells.append(_empty_shell(tag))
        # Optional: logical include marker for Siebel assembler
        shells.append(f'''<siebel:IncludeApplet name="{item['name']}" file="applet_{item['name']}.swt" />''')
    return "<html>\n<body>\n" + "\n".join(shells) + "\n</body>\n</html>\n"

def generate_view_and_applets(html: str, manifest: list[dict], out_dir: Path, workdir: str):
    soup = BeautifulSoup(html, "lxml")
    found = {}
    written = []
    safe_by_name = {}

    # Create a copy of the original HTML for the view template
    view_soup = BeautifulSoup(html, "lxml")
    
    for it in manifest:
        name, sel, role = it["name"], it["selector"], it.get("role","")
        el = soup.select_one(sel)
        if not el:
            written.append({"name": name, "status": "not found"})
            continue

        found[name] = el
        
        # Create applet content - preserve the inner structure
        inner_html = ""
        if el.contents:
            inner_html = "".join(str(child) for child in el.contents if child != "\n")
        
        tpl = _role_to_applet_template(name, role, inner_html)

        safe = _safe_name(name)
        safe_by_name[name] = safe

        applet_file = out_dir / f"applet_{safe}.swt"
        applet_file.write_text(tpl, "utf-8")

        written.append({
            "name": name,
            "safe": safe,
            "file": f"/download/{workdir}/{applet_file.name}",
            "status": "ok"
        })
        
        # Replace the original content in view template with applet include as comment
        view_el = view_soup.select_one(sel)
        if view_el:
            # Clear the existing content but keep the container
            view_el.clear()
            
            # Add the applet include as a comment (to avoid HTML parsing issues)
            applet_comment = view_soup.new_string(f"<!-- siebel:IncludeApplet name='{safe}' file='applet_{safe}.swt' -->")
            view_el.append(applet_comment)

    # Write the view template
    view_content = str(view_soup)
    (out_dir / "view_template.swt").write_text(view_content, "utf-8")

    return {
        "applets": written,
        "view": f"/download/{workdir}/view_template.swt"
    }
# -------- API endpoints (AJAX from the UI) -------- #
# ---- deep seek start----#
def parse_hierarchical_structure(html: str, manifest: dict) -> dict:
    """Parse HTML with hierarchical awareness"""
    soup = BeautifulSoup(html, "lxml")
    structure = {}
    
    for container in manifest.get("containers", []):
        container_el = soup.select_one(container["selector"])
        if not container_el:
            continue
            
        container_data = {
            "element": container_el,
            "children": [],
            "type": container.get("type", "container")
        }
        
        # Parse children if specified
        if "children" in container:
            for child_config in container["children"]:
                child_el = container_el.select_one(child_config["selector"])
                if child_el:
                    container_data["children"].append({
                        "element": child_el,
                        "config": child_config
                    })
        
        structure[container["name"]] = container_data
    
    return structure

def generate_siebel_templates(hierarchical_structure: dict, out_dir: Path):
    """Generate templates based on hierarchical structure"""
    view_soup = BeautifulSoup("<html><body></body></html>", "lxml")
    body = view_soup.body
    
    for container_name, container_data in hierarchical_structure.items():
        # Create container in view
        container_copy = deepcopy(container_data["element"])
        container_copy.clear()
        
        # Add applet includes for children
        for child in container_data["children"]:
            safe_name = _safe_name(child["config"]["name"])
            applet_tag = view_soup.new_tag("siebel:IncludeApplet")
            applet_tag['name'] = safe_name
            applet_tag['file'] = f"applet_{safe_name}.swt"
            container_copy.append(applet_tag)
            
            # Generate applet file
            generate_applet_file(child, out_dir)
        
        body.append(container_copy)
    
    return str(view_soup)
def detect_nested_structures(soup, parent_selector):
    """Automatically detect nested structures within a container"""
    parent = soup.select_one(parent_selector)
    if not parent:
        return []
    
    # Look for common section patterns
    sections = parent.find_all(['section', 'div', 'article'], class_=True)
    return [
        {
            "name": el.get('class', ['unknown'])[0],
            "selector": f"{parent_selector} > {el.name}.{'.'.join(el.get('class', []))}",
            "element": el
        }
        for el in sections
    ]

def find_similar_selectors(soup, target_selector: str) -> list:
    """
    Find CSS selectors that are similar to the target selector.
    This helps when the exact selector from manifest doesn't exist in HTML.
    """
    try:
        # If the target selector works, return it
        if soup.select_one(target_selector):
            return [target_selector]
        
        # Parse the target selector to understand what we're looking for
        suggestions = []
        
        # Strategy 1: Try different variations of the selector
        if '.' in target_selector:
            # Class selector - try variations
            parts = target_selector.split('.')
            base_class = parts[-1]
            
            # Look for elements with similar class names
            similar_elements = soup.find_all(class_=lambda x: x and base_class in str(x))
            for element in similar_elements:
                if element.get('class'):
                    for cls in element['class']:
                        if base_class in cls:
                            suggested_selector = f".{cls}"
                            if soup.select_one(suggested_selector):
                                suggestions.append(suggested_selector)
        
        # Strategy 2: Try by element type
        if not suggestions:
            element_type = target_selector.split('.')[0] if '.' in target_selector else target_selector
            if element_type and not element_type.startswith('.'):
                # Look for elements of this type
                elements = soup.find_all(element_type)
                if elements:
                    suggestions.append(element_type)
        
        # Strategy 3: Try by role or common patterns
        if not suggestions:
            # Look for common container patterns
            common_containers = ['header', 'footer', 'main', 'section', 'div', 'nav', 'aside']
            for container in common_containers:
                elements = soup.find_all(container, class_=True)
                if elements:
                    for element in elements:
                        if element.get('class'):
                            suggested_selector = f"{container}.{element['class'][0]}"
                            suggestions.append(suggested_selector)
        
        # Strategy 4: Try ID selectors if any element has ID
        if not suggestions:
            elements_with_id = soup.find_all(id=True)
            for element in elements_with_id:
                suggestions.append(f"#{element['id']}")
        
        # Remove duplicates and limit results
        unique_suggestions = []
        seen = set()
        for suggestion in suggestions:
            if suggestion not in seen and soup.select_one(suggestion):
                seen.add(suggestion)
                unique_suggestions.append(suggestion)
        
        return unique_suggestions[:5]  # Return top 5 suggestions
        
    except Exception as e:
        print(f"Error finding similar selectors: {e}")
        return []
# --- add near the top of main_router.py ---
def _strip_code_fence(s: str) -> str:
    return re.sub(r'^\s*```(?:json)?\s*|\s*```\s*$', '', s, flags=re.IGNORECASE | re.M)

def _json_sanitize(s: str) -> str:
    s = _strip_code_fence(s)
    s = re.sub(r'//.*?$', '', s, flags=re.M)         # // comments
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.S)      # /* ... */ comments
    s = re.sub(r',\s*([}\]])', r'\1', s)             # trailing commas
    s = s.strip()
    m = re.search(r'\{[\s\S]*\}\s*$', s)
    return m.group(0) if m else s

def _load_manifest_safely(path: Path) -> dict:
    raw = path.read_text("utf-8", errors="ignore")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return json.loads(_json_sanitize(raw))
    
def validate_structure(html: str, manifest: dict) -> dict:
    """Validate that manifest structure matches HTML"""
    soup = BeautifulSoup(html, "lxml")
    validation_result = {
        "valid": True,
        "missing_selectors": [],
        "suggestions": [],
        "warnings": []
    }
    
    def validate_container(container, parent_selector=""):
        full_selector = f"{parent_selector} {container['selector']}".strip() if parent_selector else container['selector']
        
        if not soup.select_one(full_selector):
            validation_result["valid"] = False
            validation_result["missing_selectors"].append(full_selector)
            
            # Find similar selectors
            similar = find_similar_selectors(soup, full_selector)
            if similar:
                validation_result["suggestions"].append({
                    "expected": full_selector,
                    "similar": similar,
                    "container": container.get("name", "unknown")
                })
            else:
                validation_result["warnings"].append(f"No similar selectors found for {full_selector}")
        
        # Validate children recursively
        for child in container.get("children", []):
            validate_container(child, full_selector)
    
    # Validate all containers
    for container in manifest.get("containers", []):
        validate_container(container)
    
    return validation_result
@app.get("/download/<workdir>/webtemplate/<path:name>")
def download_wt(workdir: str, name: str):
    out_dir = OUTPUT_ROOT / workdir / "webtemplate"
    if not out_dir.exists():
        abort(404)
    # Allow any file inside webtemplate folder
    fp = out_dir / name
    if not fp.exists() or not fp.is_file():
        abort(404)
    return send_file(fp, as_attachment=True)

def generate_applet_file(child_data: dict, target_dir: Path):
    """Generate individual applet files from child component data"""
    config = child_data["config"]
    element = child_data["element"]
    
    # Extract inner HTML content
    inner_html = ""
    if element.contents:
        inner_html = "".join(str(child) for child in element.contents if child != "\n")
    
    # Generate the applet template based on role
    safe_name = _safe_name(config["name"])
    tpl = _role_to_applet_template(config["name"], config.get("role", ""), inner_html)
    
    # Write the applet file
    applet_file = target_dir / f"applet_{safe_name}.swt"
    applet_file.write_text(tpl, "utf-8")
    
    return {
        "name": config["name"],
        "safe": safe_name,
        "file": applet_file.name,
        "status": "ok"
    }
def generate_siebel_templates_from_hierarchy(html: str, manifest: dict, out_dir: Path, workdir: str):
    """Generate Siebel templates using hierarchical manifest structure"""
    wt = _webtemplate_dir(out_dir)  # write SWT files inside <ts>/webtemplate/
    soup = BeautifulSoup(html, "lxml")
    written = []

    # Create a copy for the view template
    view_soup = BeautifulSoup(html, "lxml")

    for container in manifest.get("containers", []):
        container_el = soup.select_one(container["selector"])
        if not container_el:
            continue

        view_container_el = view_soup.select_one(container["selector"])
        if not view_container_el:
            continue

        # Clear container content but keep the structure
        view_container_el.clear()

        # Process children components
        for child_config in container.get("children", []):
            child_el = container_el.select_one(child_config["selector"])
            if not child_el:
                continue

            # Generate applet file into webtemplate/
            child_data = {"config": child_config, "element": child_el}
            applet_result = generate_applet_file(child_data, wt)
            # add a direct URL using the /download/<workdir>/webtemplate/<name> route
            applet_result["url"] = f"/download/{workdir}/webtemplate/{applet_result['file']}"
            written.append(applet_result)

            # Add applet include to view template
            applet_tag = view_soup.new_tag("siebel:IncludeApplet")
            applet_tag['name'] = applet_result["safe"]
            applet_tag['file'] = f"applet_{applet_result['safe']}.swt"
            view_container_el.append(applet_tag)

    # Write view template into webtemplate/
    view_file = _webtemplate_dir(out_dir) / "view_template.swt"
    view_file.write_text(str(view_soup), "utf-8")

    return {
        "applets": written,
        "view": f"/download/{workdir}/webtemplate/view_template.swt"
    }

# ---- deep seek end----#
@app.post("/api/convert")
def api_convert():
    """Upload image, run conversion once, save to a timestamped folder."""
    file = request.files.get("image")
    model = request.form.get("model", "gpt-4o")
    tokens = int(request.form.get("max_tokens", "6000"))

    if not file or file.filename == "":
        return jsonify({"ok": False, "error": "No file selected."}), 400

    filename = secure_filename(file.filename)
    up_path = UPLOAD_ROOT / filename
    file.save(up_path)

    out_dir = _ts_dir()
    # Save a pointer to the source image so "generate again" can reuse it
    (out_dir / "source_image.txt").write_text(str(up_path), "utf-8")

    # Call your logic (unchanged)
    try:
        process_siebel_conversion(str(up_path), str(out_dir), model=model, max_completion_tokens=tokens)
    except Exception as e:
        # Ensure an error is visible in UI
        (out_dir / "raw_response.txt").write_text(f"ERROR: {e}", "utf-8")
        (out_dir / "generated.html").write_text(
            f"<html><body><h2>Conversion failed</h2><p>{e}</p></body></html>", "utf-8"
        )

    return jsonify({"ok": True, "workdir": out_dir.name})


@app.post("/api/retry")
def api_retry():
    """Re-run conversion using the prior uploaded image path (no re-upload)."""
    workdir = request.form.get("workdir", "")
    model = request.form.get("model", "gpt-4o")
    tokens = int(request.form.get("max_tokens", "6000"))
    prev_dir = OUTPUT_ROOT / workdir
    if not prev_dir.exists():
        return jsonify({"ok": False, "error": "Previous session expired."}), 410

    src_file = prev_dir / "source_image.txt"
    if not src_file.exists():
        return jsonify({"ok": False, "error": "No source image found to retry."}), 400

    up_path = Path(src_file.read_text("utf-8").strip())
    if not up_path.exists():
        return jsonify({"ok": False, "error": "Original image missing on disk."}), 400

    out_dir = _ts_dir()
    (out_dir / "source_image.txt").write_text(str(up_path), "utf-8")
    try:
        process_siebel_conversion(str(up_path), str(out_dir), model=model, max_completion_tokens=tokens)
    except Exception as e:
        (out_dir / "raw_response.txt").write_text(f"ERROR: {e}", "utf-8")
        (out_dir / "generated.html").write_text(
            f"<html><body><h2>Conversion failed</h2><p>{e}</p></body></html>", "utf-8"
        )

    return jsonify({"ok": True, "workdir": out_dir.name})


@app.get("/preview/<workdir>")
def preview(workdir: str):
    """Return HTML (with CSS inlined) for iframe preview."""
    out_dir = OUTPUT_ROOT / workdir
    if not out_dir.exists():
        abort(404)
    html = _inline_preview_html(out_dir)
    return html
def _safe_name(name: str) -> str:
    """Normalize names to safe identifiers for file/include usage."""
    return re.sub(r'[^a-zA-Z0-9_-]', '_', name.strip()).lower()
import shutil

def _zip_webtemplate(out_dir: Path) -> Path:
    wt = out_dir / "webtemplate"
    wt.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / f"webtemplate_{out_dir.name}.zip"
    base = str(zip_path)[:-4]  # make_archive expects no .zip
    shutil.make_archive(base_name=base, format="zip", root_dir=wt)
    return zip_path

@app.get("/download-webtemplate/<workdir>")
def download_webtemplate_zip(workdir: str):
    out_dir = OUTPUT_ROOT / workdir
    if not out_dir.exists():
        abort(404)
    zip_path = _zip_webtemplate(out_dir)
    return send_file(zip_path, as_attachment=True, download_name=zip_path.name)

@app.get("/download/<workdir>/<name>")
def download(workdir: str, name: str):
    out_dir = OUTPUT_ROOT / workdir
    if not out_dir.exists():
        abort(404)

    base_allowed = {"raw_response.txt", "generated.html", "style.css", "manifest.json", "view_template.swt"}
    is_applet = name.startswith("applet_") and name.endswith(".swt")

    if not (name in base_allowed or is_applet):
        abort(404)

    return send_file(out_dir / name, as_attachment=True)


@app.post("/api/generate_siebel")
def api_generate_siebel():
    workdir = request.form.get("workdir", "")
    out_dir = OUTPUT_ROOT / workdir
    if not out_dir.exists():
        return jsonify({"ok": False, "error": "Session expired. Re-run conversion."}), 410

    # ALWAYS read from timestamp root (your requirement)
    html_path = out_dir / "generated.html"
    manifest_path = out_dir / "manifest.json"

    if not html_path.exists():
        return jsonify({"ok": False, "error": "generated.html not found"}), 400
    if not manifest_path.exists():
        return jsonify({"ok": False, "error": "manifest.json not found"}), 400

    html = html_path.read_text("utf-8", errors="ignore")
   # manifest = json.loads(manifest_path.read_text("utf-8", errors="ignore"))
    try:
        manifest = _load_manifest_safely(manifest_path)
    except Exception as e:
        return jsonify({
            "ok": False,
            "error": f"manifest.json is not valid JSON ({e}).",
            "hint": "Remove comments/trailing commas or paste a clean JSON.",
        }), 400

    result = generate_siebel_templates_from_hierarchy(html, manifest, out_dir, workdir)
      # build zip so the client can download immediately
    zip_url = f"/download-webtemplate/{workdir}"
    return jsonify({
        "ok": True,
        "message": "Generated Siebel webtemplates.",
        "files": result,
        "zip": zip_url
    })
#PM/PR Generator code start# ---- PM/PR Generator (simple, no AI) ----

def _pmpr_safe(name: str) -> str:
    # Class/file safe: letters, numbers, underscore; leading letter
    base = re.sub(r'[^a-zA-Z0-9_]', '_', name.strip())
    if not base or not base[0].isalpha():
        base = f"A_{base}"
    return base

def _pm_template(cls: str) -> str:
    return f"""define("siebel/custom/{cls}PM", ["siebel/pmodel"], function (PModel) {{
  function {cls}PM() {{}}
  {cls}PM.prototype = new PModel();

  {cls}PM.prototype.Init = function () {{
    PModel.prototype.Init.apply(this, arguments);
    // TODO: add PM property/command registrations here
  }};

  {cls}PM.prototype.Setup = function (propSet) {{
    PModel.prototype.Setup.apply(this, arguments);
  }};

  return {cls}PM;
}});"""

def _pr_template(cls: str) -> str:
    return f"""define("siebel/custom/{cls}PR", ["siebel/physicalrenderer"], function (PR) {{
  function {cls}PR(pm) {{
    PR.call(this, pm);
  }}
  {cls}PR.prototype = Object.create(PR.prototype);
  {cls}PR.prototype.constructor = {cls}PR;

  {cls}PR.prototype.Init = function () {{
    PR.prototype.Init.apply(this, arguments);
  }};

  {cls}PR.prototype.ShowUI = function () {{
    PR.prototype.ShowUI.apply(this, arguments);
    // TODO: build DOM here
  }};

  {cls}PR.prototype.BindData = function () {{
    PR.prototype.BindData.apply(this, arguments);
  }};

  {cls}PR.prototype.BindEvents = function () {{
    PR.prototype.BindEvents.apply(this, arguments);
  }};

  {cls}PR.prototype.EndLife = function () {{
    PR.prototype.EndLife.apply(this, arguments);
  }};

  return {cls}PR;
}});"""

@app.get("/PMPRGenerator")
def pmpr_page():
    mf = (APP_ROOT / "manifest.json")
    strings = json.loads(mf.read_text("utf-8")) if mf.exists() else {}
    return render_template("pmpr_generator.html", strings=strings)

@app.post("/api/pmpr/generate")
def pmpr_generate():
    kind = (request.form.get("kind") or "").lower()   # "pm" or "pr"
    name = request.form.get("name") or ""
    if kind not in {"pm","pr"} or not name.strip():
        return jsonify({"ok": False, "error": "Choose PM/PR and enter a name."}), 400

    cls = _pmpr_safe(name)
    code = _pm_template(cls) if kind == "pm" else _pr_template(cls)
    filename = f"{cls}{kind.upper()}.js"  # e.g. MyAppletPM.js / MyAppletPR.js

    return jsonify({"ok": True, "filename": filename, "code": code})

if __name__ == "__main__":
    app.run(debug=True)