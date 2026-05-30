import asyncio
import os
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


async def teste_streaming():
    print("Iniciando chamada com streaming...\n")
    
    stream = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": "Me explique em 3 frases curtas o que é um asteroide."
            }
        ],
        stream=True,
    )
    
    async for chunk in stream:
        token = chunk.choices[0].delta.content
        
        if token is not None:
            print(token, end="", flush=True)
    
    print("\n\nStream finalizada.")


if __name__ == "__main__":
    asyncio.run(teste_streaming())