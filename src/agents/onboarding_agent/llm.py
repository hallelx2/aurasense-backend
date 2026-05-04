"""LLM client bindings for the onboarding agent.

NOTE: This module is being kept minimal during Phase 0 for backward
compatibility. In Phase 1 these direct client instantiations are replaced
by the LLM gateway (`src.app.services.llm_gateway`) so models can be swapped
per-role via env vars without touching agent code.
"""

from groq import Groq
from langchain_groq import ChatGroq
from rich import print  # noqa: F401  (used by the smoke test below)

from src.app.core.config import settings

#######################
# Large Language Models
#######################

llm_llama3 = ChatGroq(
    model="llama3-8b-8192",
    api_key=settings.GROQ_API_KEY,
)

llm_deepseek = ChatGroq(
    model="deepseek-r1-distill-llama-70b",
    api_key=settings.GROQ_API_KEY,
)

llm_qwen = ChatGroq(
    model="qwen/qwen3-32b",
    api_key=settings.GROQ_API_KEY,
)

####################################
# Speech To Text (STT) Models
####################################
stt_client = Groq(api_key=settings.GROQ_API_KEY)

#####################################
# Text to Speech (TTS) Models
#####################################
tts_client = Groq(api_key=settings.GROQ_API_KEY)


if __name__ == "__main__":
    response = llm_qwen.invoke("Hello, how are you?")
    print(response)
