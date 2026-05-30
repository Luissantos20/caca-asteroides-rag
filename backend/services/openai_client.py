from openai import AsyncOpenAI
from dotenv import load_dotenv
import asyncio
import os

load_dotenv()

client_openai = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
openai_semaphore = asyncio.Semaphore(6)