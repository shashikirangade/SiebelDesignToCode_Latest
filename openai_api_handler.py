# openai_api_handler.py
import base64
import os
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()  # loads .env into environment variables
instructions = (
    "You are an expert UI-to-HTML conversion specialist. Your PRIMARY task is to create perfect, semantic HTML5 that exactly matches the screenshot.\n\n"
    "## PHASE 1: CREATE EXCEPTIONAL HTML\n"
    "Generate pristine HTML with:\n"
    "✅ Semantic regions (header, main, section, article, nav, aside, footer)\n"
    "✅ Descriptive, stable class names (BEM encouraged)\n"
    "✅ Clean nested hierarchy reflecting visual grouping\n"
    "✅ Accessibility (alt, aria-*, roles), Flex/Grid layout\n"
    "✅ All visible content captured\n\n"
    "## PHASE 2: RETURN A MANIFEST THAT FULLY SEGREGATES THE PAGE INTO APPLETS\n"
    "The manifest MUST contain the complete applet split. Do NOT rely on the consumer to infer applets.\n"
    "Requirements:\n"
    "• Use EXACT selectors and class names from the HTML you produced\n"
    "• Every visual module must appear as an applet under some container\n"
    "• Each applet must have a name, role, selector, and (when applicable) fields and actions\n"
    "• For lists, include item_selector and infer columns as fields\n"
    "• Optionally provide entityHint and businessComponent when obvious\n\n"
    "## STRICT MANIFEST SCHEMA\n"
    "{\n"
    "  \"page\": {\n"
    "    \"title\": \"string\",\n"
    "    \"layout\": \"grid|cards|form|list|mixed\",\n"
    "    \"containers\": [\n"
    "      {\n"
    "        \"name\": \"string\",\n"
    "        \"role\": \"Region|Banner|Main|Nav|Content|Card|Grid\",\n"
    "        \"selector\": \"CSS selector\",\n"
    "        \"type\": \"container\",\n"
    "        \"applets\": [\n"
    "          {\n"
    "            \"name\": \"string\",\n"
    "            \"role\": \"List|Form|Toolbar|Nav|Card|Region|Grid|Content\",\n"
    "            \"selector\": \"CSS selector (smallest block that contains this applet)\",\n"
    "            \"item_selector\": \"CSS selector for list rows (ONLY for role=List)\",\n"
    "            \"entityHint\": \"Account|Contact|Service Request|Opportunity|None\",\n"
    "            \"businessComponent\": \"optional exact BC name if obvious\",\n"
    "            \"fields\": [\n"
    "              {\"label\":\"string\",\"dataField\":\"best-guess\",\"selector\":\"CSS selector\",\"controlType\":\"Text|Pick|Date|Number|Checkbox|Button|Link|Image\",\"required\":false,\"readonly\":false}\n"
    "            ],\n"
    "            \"actions\": [\n"
    "              {\"name\":\"string\",\"selector\":\"CSS selector\",\"type\":\"Command|Nav|Popup\"}\n"
    "            ]\n"
    "          }\n"
    "        ],\n"
    "        \"children\": [ /* nested containers with same structure */ ]\n"
    "      }\n"
    "    ]\n"
    "  }\n"
    "}\n\n"
    "## OUTPUT FORMAT — EXACTLY 3 FENCED CODE BLOCKS IN THIS ORDER (NO PROSE):\n"
    "1) ```html ...``` — Complete semantic HTML\n"
    "2) ```css  ...``` — Styles referenced by the HTML\n"
    "3) ```json ...``` — Manifest strictly following the schema above, with COMPLETE applet segregation\n\n"
    "## CRITICAL RULES\n"
    "1) The manifest MUST include the full applet split (no omissions)\n"
    "2) Selectors in the manifest MUST match the generated HTML exactly\n"
    "3) Prefer minimal, unique selectors (ids > class chains), avoid overly broad ancestors\n"
    "4) Do not output any text outside the three code blocks\n"
)

def encode_image_to_base64(image_path: Path) -> str:
    """Read image and return a data URI suitable for OpenAI’s API."""
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:image/png;base64,{b64}"

def call_openai_api(image_path: Path, model: str, max_completion_tokens: int) -> str:
    """
    Attempt to call the OpenAI API. If the call fails (e.g. network off),
    return None so the caller can handle fallback.
    """
    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        organization=os.getenv("OPENAI_ORGANIZATION") or os.getenv("OPENAI_ORG"),
        project=os.getenv("OPENAI_PROJECT"),
    )

    data_uri = encode_image_to_base64(image_path)
    
    
    '''instructions = (
        "You are a UI conversion assistant. Convert the screenshot into high-fidelity HTML and CSS.\n"
        "Return ONLY THREE fenced code blocks in this order:\n"
        "1) ```json ...``` with regions including `name`, `role`, and CSS selector if applicable\n"
        "2) ```html ...``` semantic HTML5 using flex/grid layout\n"
        "3) ```css ...``` styled to match dark theme\n"
        "Do not include any prose outside these code blocks."
    )'''

    try:
        response = client.chat.completions.create(
            model=model,
            max_completion_tokens=max_completion_tokens,
            temperature=0.2,
            messages=[
                {"role": "system", "content": instructions},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": (
                            "Convert this screenshot to HTML, CSS, and a Siebel manifest.\n"
                            "Return exactly THREE fenced code blocks in this order and NOTHING ELSE:\n"
                            "1) ```html ...```\n2) ```css ...```\n3) ```json ...```"
                        )},
                        {"type": "image_url", "image_url": {"url": data_uri}},
                    ],
                },
            ],
        )
    except Exception as e:
        # When offline or quota issues, return None to trigger fallback
        return None

    if not response.choices:
        return None

    return response.choices[0].message.content or ""
