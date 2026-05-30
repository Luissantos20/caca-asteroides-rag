import logging

from services.openai_client import client_openai, openai_semaphore

logger = logging.getLogger(__name__)

# Quantas mensagens do fim do histórico enviar ao reescritor.
# Conversas são curtas → 4 cobre 2 trocas (user/assistant/user/assistant).
MAX_HISTORY_MESSAGES = 4

# Teto de tamanho da query reescrita. Se o modelo "viajar" e devolver algo
# muito maior que uma pergunta, é sinal de que alucinou → usa a original.
MAX_REWRITE_CHARS = 300

REWRITE_SYSTEM_PROMPT = """Você reescreve a ÚLTIMA pergunta do usuário para que ela faça sentido sozinha, sem precisar do histórico da conversa.

CONTEXTO: é um chat sobre o programa Caça Asteroides MCTI (ciência cidadã, análise de imagens no software Astrometrica, inscrição, certificados).

REGRAS:
- Resolva pronomes e referências ("isso", "e como?", "e se não resolver") usando o histórico.
- Se a última pergunta MUDA de assunto, reescreva-a de forma INDEPENDENTE — NÃO arraste o tema anterior para dentro dela.
- Mantenha a intenção original. Não responda à pergunta, não adicione informação nova, não invente.
- Devolva APENAS a pergunta reescrita, em uma linha, sem aspas, sem explicação.
- Se a pergunta já é autônoma e clara, devolva-a praticamente igual."""


async def rewrite_query(query: str, request_id: str, history: list = None) -> str:
    """
    Reescreve `query` como uma pergunta autônoma usando o histórico.

    Garantias de segurança:
    - Sem histórico → devolve a query original (não chama o LLM, custo zero).
    - Qualquer falha, resposta vazia ou suspeita → devolve a query original.
      O sistema NUNCA fica pior do que sem reescrita.
    """
    if not history:
        return query

    # só as últimas mensagens, em ordem cronológica
    recent = history[-MAX_HISTORY_MESSAGES:]
    linhas = []
    for msg in recent:
        papel = "Usuário" if msg["role"] == "user" else "Assistente"
        linhas.append(f"{papel}: {msg['content']}")
    historico_texto = "\n".join(linhas)

    user_prompt = (
        f"Histórico da conversa:\n{historico_texto}\n\n"
        f"Última pergunta do usuário: {query}\n\n"
        f"Pergunta reescrita:"
    )

    try:
        async with openai_semaphore:
            resp = await client_openai.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0,
                timeout=10,
                max_tokens=80,
                messages=[
                    {"role": "system", "content": REWRITE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            )
        reescrita = (resp.choices[0].message.content or "").strip()

        # ---- guardas de segurança: se algo estiver estranho, usa a original ----
        if not reescrita:
            logger.warning(f"[{request_id}] [REWRITE] vazia → usando query original")
            return query
        if len(reescrita) > MAX_REWRITE_CHARS:
            logger.warning(f"[{request_id}] [REWRITE] longa demais → usando query original")
            return query

        if reescrita != query:
            logger.info(
                f"[{request_id}] [REWRITE] '{query[:60]}' → '{reescrita[:60]}'"
            )
        return reescrita

    except Exception as e:
        logger.error(f"[{request_id}] [REWRITE ERROR] {e} → usando query original")
        return query
