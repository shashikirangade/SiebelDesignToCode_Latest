# SiebelDesignToCode_Latest
# SiebelDesignToCode_Latest
What this project is

A Flask app with (at least) two main modules plus a helper:
	1.	Image → Siebel WebTemplate (Design-to-Code)
Upload a UI screenshot; the app calls an LLM to produce HTML + CSS + a “manifest” JSON that describes containers/applets. It then converts that into Siebel .swt webtemplates (applets + a view file) you can preview and download.
	2.	Client Script Bot (Siebel Q&A agent with RAG)
A chat UI backed by OpenAI’s Responses API + file_search against your OpenAI Vector Store (supplied via env var) to answer Siebel/Open UI/functional logic questions. Falls back to plain Chat Completions if Responses/file_search isn’t available.
	3.	(Bonus) PM/PR generator
A tiny utility to generate skeleton PM/PR files for a given applet name.

⸻

Key files & structure (high level)
	•	main_router.py — The Flask app: routes, upload/convert/preview/download flows, Siebel .swt generation.
	•	openai_api_handler.py — Calls OpenAI (multimodal) with a big prompt to return HTML, CSS, and a manifest JSON from an image.
	•	gemini_api_handler.py — Optional Google Gemini path; reuses the same instructions so the parser stays identical.
	•	client_script_bot.py — The Q&A agent (OpenAI Responses API + file_search to your vector store).
	•	templates/*.html — UI pages (base layout, design-to-code UI, bot UI, PM/PR generator).
	•	static/css/theme.css — Clean UI styling.
	•	requirements.txt — Flask, bs4, OpenAI, Google Generative AI, etc.
	•	output/ — Per-run timestamped folders holding generated.html, styles.css, manifest.json, webtemplate/ (.swt files), and logs.
	•	uploads/ — Uploaded images.
	•	logs/ — api.log, bot.log.

⸻

Module 1: Image → Siebel WebTemplate

Flow
	1.	Upload (POST /api/convert)
	•	Saves the uploaded image under uploads/ and creates a timestamped run directory under output/YYYYMMDD_HHMMSS/.
	•	Calls process_siebel_conversion(image_path, out_dir, model, max_completion_tokens) which:
	•	Uses OpenAI (openai_api_handler.py) or Gemini (gemini_api_handler.py) based on the selected model.
	•	Returns three artifacts (as text):
	•	generated.html (semantic HTML)
	•	styles.css (CSS)
	•	manifest.json (hierarchy describing containers/applets & selectors)
	•	Writes all three into the timestamped run folder and also a raw_response.txt.
	2.	Preview (GET /preview/<workdir>)
	•	Builds an inline preview by injecting the CSS into the HTML for a sandboxed iframe in the UI (_inline_preview_html).
	3.	Retry (POST /api/retry)
	•	Re-runs conversion without re-uploading the image. It reads source_image.txt from the previous run.
	4.	Generate Siebel templates (POST /api/generate_siebel)
	•	Reads generated.html + manifest.json.
	•	Parses the HTML with BeautifulSoup and walks the manifest to:
	•	Locate elements via CSS selectors (with fallback/similarity finder if the exact selector doesn’t exist).
	•	Detect nested structures (sections/cards) to define containers and children.
	•	For each applet, wrap the element’s inner HTML in the appropriate Siebel applet skeleton based on role:
	•	List / Navigation / Grid → <siebel:Applet type="List"> … </siebel:Applet>
	•	Form / Main / Content / Banner / Region → <siebel:Applet type="Form"> … </siebel:Applet>
	•	Button / Toolbar / Action → <siebel:Applet type="Toolbar"> … </siebel:Applet>
	•	Writes webtemplate/applet_<Name>.swt for each child and webtemplate/view_template.swt that includes those applets (<siebel:IncludeApplet name="..." file="applet_..."/>).
	•	Returns success + lets you download individual files or a zip.
	5.	Downloads
	•	GET /download/<workdir>/webtemplate/<path:name> — any file inside that run’s webtemplate/.
	•	GET /download/<workdir>/webtemplate.zip — zipped webtemplate folder.
	•	GET /download/<workdir>/raw/<name> — raw artifacts like generated.html, styles.css, manifest.json.

Notable helpers
	•	_role_to_applet_template(name, role, inner_html) — maps a role to a Siebel applet skeleton.
	•	find_similar_selectors(soup, target_selector) — tries alternatives when the manifest selector doesn’t match.
	•	detect_nested_structures(soup) — groups DOM into sections/child components automatically if the manifest is sparse.
	•	_webtemplate_dir(out_dir) — ensures the webtemplate/ subfolder exists.
	•	_safe_name() — normalizes names for filenames and include tags.

⸻

Module 2: Client Script Bot (RAG agent)
	•	Page: GET /ClientScriptBot → templates/client_script_bot.html.
	•	API: POST /api/client-script/ask → client_script_bot.ask_client_script_bot.

How it answers
	•	Prefers OpenAI Responses API with the file_search tool pointed at your OPENAI_VECTOR_STORE_ID (env var).

	tools=[{"type":"file_search"}],
tool_resources={"file_search": {"vector_store_ids": [VECTOR_STORE_ID]}}

	•	System prompt pins scope to Siebel Open UI; answers are formatted to Markdown (rendered in the chat window).
	•	If Responses/file_search isn’t available (e.g., missing env or older account), it falls back to Chat Completions (no retrieval).
	•	Logs vector hits (citations) to bot.log when available.

PM/PR generator
	•	Page: GET /PMPRGenerator
	•	API: POST /api/pmpr/generate with kind=pm|pr and name=....
	•	Produces a sanitized class name and a ready-to-save MyAppletPM.js or MyAppletPR.js skeleton (with Define wrapper, Init/ShowUI/BindData/BindEvents/EndLife).



Config & environment

Add these to your .env (or shell env):
	•	FLASK_SECRET – optional secret for sessions (defaults to "design-to-code-secret").
	•	OpenAI (for both modules)
	•	OPENAI_API_KEY (required for OpenAI path)
	•	OPENAI_MODEL (defaults to gpt-4o; UI lets you pick gpt-4o, gpt-4o-mini)
	•	OPENAI_VECTOR_STORE_ID (required for the bot’s retrieval)
	•	Google Gemini (optional for design-to-code)
	•	GOOGLE_API_KEY if you select gemini-1.5-flash or gemini-1.5-pro in the UI

requirements.txt includes: flask, beautifulsoup4, openai, google-generativeai, lxml, markdown, python-dotenv, pillow, qdrant-client (present but not used here—see notes below).


Notes / limitations / quick wins
	•	Selector fragility: When the model’s manifest has imperfect selectors, the code tries “similar selectors,” but edge cases may still miss. If you see empty applets, check manifest.json vs the parsed generated.html.
	•	Role → skeleton mapping: Currently maps to List/Form/Toolbar types. If you want other Siebel types, extend _role_to_applet_template.
	•	Qdrant not wired: qdrant-client is in requirements, but the bot currently uses OpenAI’s vector store via file_search. If you want a self-hosted RAG, you’d add an ingestion script + retrieval path using Qdrant, then pass retrieved chunks into the prompt.
	•	Security: Downloads allow any file inside the run’s webtemplate/ path, with checks—looks fine for a trusted environment; avoid deploying as-is to an untrusted multi-tenant setup.
	•	Gemini fallback: If you pick a future model name (e.g., “gemini-2.5-pro”), the code quietly maps to a supported one.


    Steps to execute

1. Activate the python virtual environment
2. execute below command
    pip install -r requirements.txt
