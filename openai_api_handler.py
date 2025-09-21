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
    "✅ Perfect semantic structure (header, main, section, article, nav, aside, footer)\n"
    "✅ Meaningful, specific class names that describe the component's purpose\n"
    "✅ Clean, nested hierarchy that reflects visual grouping and containment\n"
    "✅ Accessibility attributes (alt texts, aria-labels, roles where needed)\n"
    "✅ Responsive-ready structure using modern CSS (flexbox/grid)\n"
    "✅ Complete content preservation from the screenshot\n"
    "✅ Proper HTML5 semantic tags for each region\n\n"
    
    "## PHASE 2: ANALYZE STRUCTURE & CREATE HIERARCHICAL JSON\n"
    "Based on the HTML structure, generate JSON that:\n"
    "✅ Uses EXACT class names from the HTML you created\n"
    "✅ Reflects the actual parent-child relationships in the HTML\n"
    "✅ Identifies containers (hold multiple components) vs individual components\n"
    "✅ Suggests appropriate Siebel roles based on component purpose\n"
    "✅ Includes item selectors for list-type components\n\n"
    
    "## REQUIRED JSON FORMAT:\n"
    "```json\n"
    "{\n"
    "  \"version\": \"1.0\",\n"
    "  \"containers\": [\n"
    "    {\n"
    "      \"name\": \"Header\",\n"
    "      \"role\": \"banner\",\n"
    "      \"selector\": \".header\",\n"
    "      \"type\": \"container\",\n"
    "      \"children\": [\n"
    "        {\n"
    "          \"name\": \"HeaderInfo\",\n"
    "          \"role\": \"content\",\n"
    "          \"selector\": \".header__info\",\n"
    "          \"type\": \"applet\"\n"
    "        },\n"
    "        {\n"
    "          \"name\": \"HeaderActions\",\n"
    "          \"role\": \"navigation\",\n"
    "          \"selector\": \".header__actions\",\n"
    "          \"type\": \"applet\"\n"
    "        }\n"
    "      ]\n"
    "    },\n"
    "    {\n"
    "      \"name\": \"MainContent\",\n"
    "      \"role\": \"main\",\n"
    "      \"selector\": \".main-content\",\n"
    "      \"type\": \"container\",\n"
    "      \"children\": [\n"
    "        {\n"
    "          \"name\": \"Sidebar\",\n"
    "          \"role\": \"complementary\",\n"
    "          \"selector\": \".sidebar\",\n"
    "          \"type\": \"container\",\n"
    "          \"children\": [\n"
    "            {\n"
    "              \"name\": \"ContactsSection\",\n"
    "              \"role\": \"list\",\n"
    "              \"selector\": \".contacts\",\n"
    "              \"type\": \"applet\",\n"
    "              \"item_selector\": \".contact-item\"\n"
    "            },\n"
    "            {\n"
    "              \"name\": \"ServiceRequestsSection\",\n"
    "              \"role\": \"list\",\n"
    "              \"selector\": \".service-requests\",\n"
    "              \"type\": \"applet\",\n"
    "              \"item_selector\": \".service-request-item\"\n"
    "            }\n"
    "          ]\n"
        "    }\n"
    "      ]\n"
    "    }\n"
    "  ]\n"
    "}\n"
    "```\n\n"
    "## OUTPUT FORMAT - RETURN ONLY 2 CODE BLOCKS:\n"
    "```html\n"
    "<!-- Your perfect HTML here -->\n"
    "```\n\n"
    "```json\n"
    "{\n"
    "  \"version\": \"1.0\",\n"
    "  \"containers\": [\n"
    "    // Your hierarchical JSON manifest here\n"
    "  ]\n"
    "}\n"
    "```\n\n"
    
    "## CRITICAL RULES:\n"
    "1. 🎯 HTML FIRST: Create perfect HTML structure before thinking about JSON\n"
    "2. 🔗 EXACT MATCH: JSON selectors must use identical class names from HTML\n"
    "3. 🏗️ HIERARCHY PRESERVATION: JSON structure must mirror HTML nesting\n"
    "4. 🏷️ DESCRIPTIVE NAMING: Class names should describe purpose, not content\n"
    "5. 📦 SMART GROUPING: Identify what should be containers vs individual applets\n"
    "6. 🎨 CONSISTENT CSS: CSS must use the same class names as HTML\n"
    "7. ❌ NO PROSE: Only code blocks, no additional text\n"
    "8. ✅ COMPLETE COVERAGE: Every visual element must have HTML representation\n\n"
    
    "## CLASS NAMING GUIDELINES:\n"
    "• Purpose-based: .user-grid, .data-panel, .action-bar\n"
    "• Not content-based: Avoid .contact-card, .service-request (too specific)\n"
    "• Use semantic: .primary-nav, .main-content, .sidebar\n"
    "• Be generic: .item-list, .card-container, .form-section\n"
    "• Use BEM principles: .block, .block__element, .block--modifier\n\n"
    
    "## SIEBEL ROLE MAPPING:\n"
    "• banner: Header areas, top navigation\n"
    "• navigation: Menus, side navigation\n"
    "• main: Primary content container\n"
    "• list: Grids, repeating items, data tables\n"
    "• form: Data entry forms, input areas\n"
    "• region: Content sections, panels\n"
    "• content: Text-heavy areas, details\n"
    "• complementary: Sidebars, supplementary content\n\n"
    
    "## ANALYSIS PROCESS:\n"
    "1. First, analyze the screenshot and identify all visual components\n"
    "2. Create perfect HTML structure with semantic tags and descriptive class names\n"
    "3. From the HTML, identify parent-child relationships and containment\n"
    "4. Determine which components are containers and which are individual applets\n"
    "5. Assign appropriate Siebel roles based on component purpose\n"
    "6. Generate JSON that exactly mirrors the HTML structure\n"
    "7. Create CSS that styles the HTML structure properly\n\n"
    
    "FOCUS ON CREATING GENERIC, REUSABLE COMPONENTS THAT DESCRIBE PURPOSE."
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
            messages=[
                {"role": "system", "content": instructions},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Convert this screenshot to HTML, CSS, and a Siebel manifest."},
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
