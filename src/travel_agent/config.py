import os

from agents import set_default_openai_key
from dotenv import load_dotenv

load_dotenv()

_key = os.getenv("OPENAI_API_KEY")
if _key:
    set_default_openai_key(_key)

MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
