import logging

from services.openai_client import client_openai, openai_semaphore

logger = logging.getLogger(__name__)


async def generate_answer_stream(
    query: str,
    request_id: str,
    chunks: list,
    history: list = None,
):
    """
    Gerador assíncrono. Yields:
    - cada token (string) recebido da OpenAI conforme chega;
    - ou yield None caso a GERAÇÃO falhe (sem chunks, ou erro na chamada OpenAI).
      O pipeline trata o None mostrando o fallback / mensagem de interrupção.

    A decisão de RECUSAR (contexto não responde) NÃO é mais feita aqui — é do
    grader, ANTES desta função. Por isso não existe mais marcador de recusa:
    quando chegamos aqui, o contexto já foi julgado respondível, e a única
    tarefa é responder a partir dele. Nada é retido/bufferizado → nada vaza.
    """
    if history is None:
        history = []

    if not chunks:
        logger.warning(f"[{request_id}] [GENERATION] Nenhum chunk recebido")
        yield None
        return

    # Mesmos chunks que o grader julgou: score>=0.40, top-3.
    relevant_chunks = [c for c in chunks if c["score"] >= 0.4]

    if not relevant_chunks:
        logger.warning(
            f"[{request_id}] [GENERATION WARNING] "
            "Nenhum chunk relevante após filtro de score"
        )
        yield None
        return

    context = "\n\n".join([
        f"[{c['metadata']['category']}]\n{c['content'][:900]}"
        for c in relevant_chunks[:3]
    ])

    logger.info(
        f"[{request_id}] Gerando resposta com {len(relevant_chunks[:3])} chunks "
        f"(query='{query[:80]}', history={len(history)} msgs)"
    )

    system_prompt = f"""
Você é um assistente RAG do programa Caça Asteroides MCTI 2026.
O programa é uma iniciativa de ciência cidadã do MCTI em parceria com o IASC/NASA,
onde participantes analisam imagens astronômicas com o software Astrometrica para detectar asteroides.

Você receberá uma pergunta do usuário e até 3 chunks de contexto recuperados.
Pode haver histórico de mensagens anteriores nesta conversa — use-as para entender referências, mas baseie a resposta SEMPRE no contexto recuperado.

COMO RESPONDER:
- Sua tarefa é RESPONDER à pergunta usando o contexto abaixo. O contexto já foi verificado e contém a informação necessária.
- Leia TODOS os chunks. A resposta pode estar em um deles ou ser montada a partir de dois ou mais — combine as informações quando necessário.
- Responda com naturalidade mesmo que a pergunta use palavras diferentes das do texto. Se a resposta correta for um "não" ou uma restrição fundamentada no contexto (ex.: algo é proibido, ou é feito de outra forma), diga isso normalmente.
- Inclua TODAS as informações relevantes do contexto na resposta.
- Baseie-se SOMENTE no contexto recuperado. Não use conhecimento externo nem acrescente fatos que não estejam ali.

FORMATO DA RESPOSTA:
- Seja claro, direto, objetivo, simples mas completo
- Use linguagem simples
- Formate em markdown legível
- Use listas numeradas para passos
- Use negrito para destaques importantes
- Sempre use quebra de linha entre tópicos

Contexto recuperado:
{context}
"""

    messages = [{"role": "system", "content": system_prompt}]

    # Adiciona o histórico, mas remove a última fala do usuário (será substituída
    # pela versão reescrita 'query'). Evita duplicar a pergunta.
    history_sem_ultima = history[:-1] if (history and history[-1]["role"] == "user") else history
    for msg in history_sem_ultima:
        messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": query})

    logger.info(f"[{request_id}] [GENERATION] Aguardando slot do openai_semaphore")

    try:
        async with openai_semaphore:
            logger.info(f"[{request_id}] [GENERATION] Slot adquirido, iniciando stream")
            stream = await client_openai.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0,
                timeout=30,
                stream=True,
                messages=messages,
            )

            # Sem marcador, sem buffer: cada token vai direto pro usuário.
            async for chunk in stream:
                token = chunk.choices[0].delta.content
                if token is None:
                    continue
                yield token

            logger.info(f"[{request_id}] [GENERATION] Stream finalizada")

    except Exception as e:
        logger.error(
            f"[{request_id}] [GENERATION ERROR] "
            f"query='{query[:80]}' "
            f"Falha na chamada OpenAI: {str(e)}"
        )
        yield None