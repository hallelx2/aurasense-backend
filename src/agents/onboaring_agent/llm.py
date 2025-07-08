import os
import json
from langchain_groq import ChatGroq
from groq import Groq
from langchain_anthropic import ChatAnthropic
from src.app.core.config import settings
from rich import print

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

llm_claude = ChatAnthropic(
    model="claude-3-5-sonnet-20240620",
    api_key=settings.ANTHROPIC_API_KEY,
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
    user_input = "Hello, how are you?"
    response = llm_claude.invoke(user_input)
    print(response)
