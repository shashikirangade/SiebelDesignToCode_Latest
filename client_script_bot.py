# client_script_bot.py
import os, traceback
from dotenv import load_dotenv
from openai import OpenAI
import markdown
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
VECTOR_STORE_ID = os.getenv("OPENAI_VECTOR_STORE_ID")

SYSTEM = (
    "You are a Siebel Open UI expert. Answer ONLY about Siebel Open UI. "
    "When code helps, return minimal, deployable PM/PR/WebTemplate/BS snippets with brief comments. "
    "Prefer concrete APIs like GetContainer, AttachPMBinding, BindEvents, etc."
)

_client_instance = None
def get_client() -> OpenAI:
    global _client_instance
    if _client_instance is None:
        if not API_KEY:
            raise RuntimeError("OPENAI_API_KEY is not set")
        _client_instance = OpenAI(api_key=API_KEY)
    return _client_instance
def _log_prompt_and_tools(model, system_text, user_text, vector_store_id):
    logging.info("MODEL: %s", model)
    logging.info("SYSTEM PROMPT:\n%s", system_text)
    logging.info("USER PROMPT:\n%s", user_text)
    logging.info("FILE_SEARCH vector_store_ids: %s", [vector_store_id] if vector_store_id else None)

def _log_responses_annotations(resp):
    """Logs retrieval hits (citations) if Responses+file_search ran."""
    try:
        for item in getattr(resp, "output", []) or []:
            for part in getattr(item, "content", []) or []:
                txt = getattr(part, "text", None)
                if not txt:
                    continue
                anns = getattr(txt, "annotations", []) or []
                for a in anns:
                    t = getattr(a, "type", "")
                    if t == "file_citation":
                        logging.info("VECTOR HIT: file_id=%s | quote=%s", getattr(a, "file_id", None), getattr(a, "quote", "") )
                    elif t == "file_path":
                        logging.info("VECTOR FILE PATH: file_id=%s | path=%s", getattr(a, "file_id", None), getattr(a, "path", "") )
        # Optional: token usage if present
        usage = getattr(resp, "usage", None)
        if usage:
            logging.info("USAGE: %s", usage)
    except Exception as e:
        logging.warning("Failed to parse annotations: %r", e)
def responses_supported() -> bool:
    """Check if this SDK exposes Responses API (no network call)."""
    try:
        return hasattr(get_client(), "responses") and callable(getattr(get_client().responses, "create", None))
    except Exception:
        return False

def ask_client_script_bot(message: str, context_type: str = "") -> str:
    if not message or not message.strip():
        return "Please enter a question."

    user = f"ContextType: {context_type or 'Any'}\nUser Query: {message.strip()}"

    try:
        cli = get_client()

        # Try Responses API with vector store grounding (new SDKs)
        if responses_supported() and VECTOR_STORE_ID:
            try:
                _log_prompt_and_tools(MODEL, SYSTEM, user, VECTOR_STORE_ID)
                resp = cli.responses.create(
                    model=MODEL,
                    input=[
                        {"role": "system", "content": SYSTEM},
                        {"role": "user", "content": user},
                    ],
                    tools=[{"type": "file_search"}],
                    tool_resources={"file_search": {"vector_store_ids": [VECTOR_STORE_ID]}},
                    max_completion_tokens=1200,
                    temperature=0.2,
                )
                _log_responses_annotations(resp)
                return getattr(resp, "output_text", "Sorry, I couldn’t format the response.")
            except TypeError as e:
                logging.error("Caught TypeError in Responses.create(): %s", e)
            logging.info("FALLBACK: Chat Completions (no file_search). Prompt below:")
            logging.info("SYSTEM PROMPT:\n%s", SYSTEM)
            logging.info("USER PROMPT:\n%s", user)

        chat = cli.chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
            temperature=0.2,
            max_tokens=1200  # older param; ignored by newer models but harmless
        )
        raw_answer = chat.choices[0].message.content
        html_answer = markdown.markdown(raw_answer, extensions=["fenced_code", "tables"])
        return {"answer": html_answer, "html": True}



    except Exception as e:
        print("ClientScriptBot ERROR:", repr(e))
        traceback.print_exc()
        return f"Error: {e}"
