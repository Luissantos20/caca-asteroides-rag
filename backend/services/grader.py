"""
grader.py — Camada de RELEVÂNCIA (answerability check).

Roda DEPOIS do piso (decision.should_answer) e ANTES da geração.
Enquanto o piso é um NÚMERO (cos do topo >= floor) que separa bem o
out-of-scope, o grader é SEMÂNTICO: lê a pergunta contra os chunks e decide se
o contexto REALMENTE responde — pegando o caso que o número não pega
(adversarial: usa o vocabulário do tema mas o material não tem a resposta,
ex.: "asteroide é a mesma coisa que cometa?").

Chamada única, não-streaming, ao gpt-4o-mini, com raciocínio-antes-do-veredito:
o modelo escreve o porquê no campo 'raciocinio' ANTES de decidir 'pode_responder'
(a ordem dos campos no JSON força isso).
"""

import json
import logging

from services.openai_client import client_openai, openai_semaphore

logger = logging.getLogger(__name__)

# O grader julga EXATAMENTE o contexto que a geração vai receber.
# Hoje a generate_answer filtra score>=0.40 e pega top-3; replicamos aqui pra
# manter os dois vendo a mesma coisa. (Centralizar quando enxugar a geração.)
CONTEXT_SCORE_FLOOR = 0.40
TOP_K_CONTEXT = 3

GRADER_SYSTEM_PROMPT = """Você é um juiz rigoroso de RELEVÂNCIA. Sua tarefa é decidir se o CONTEXTO fornecido contém informação suficiente para responder à PERGUNTA do usuário.

SISTEMA: é um chat sobre o programa Caça Asteroides MCTI (ciência cidadã, análise de imagens no software Astrometrica, inscrição, campanhas, certificados, erros comuns).

COMO JULGAR:
- "sim" quando o contexto contém a informação para responder à pergunta — mesmo que só em parte, mesmo que use PALAVRAS DIFERENTES das da pergunta, e mesmo que a resposta exija uma inferência simples. (Ex.: "a medalha vem pelo correio?" — se o contexto diz que a medalha é entregue numa cerimônia presencial, isso RESPONDE: a resposta é "não, é na cerimônia". Veredito "sim".)
- "não" apenas quando o contexto claramente NÃO tem a informação: quando ele só toca no assunto de longe, fala de um tema vizinho, ou é sobre outra coisa.

NÃO CONFUNDA "a resposta é NÃO" com "NÃO dá pra responder":
- Se o contexto permite responder com um "não", um "é proibido" ou um "não pode", isso é uma resposta VÁLIDA — o veredito é "sim" (dá pra responder). O campo pode_responder é sobre o contexto PERMITIR uma resposta, não sobre a resposta ser afirmativa. (Ex.: "posso usar o logo da NASA nos meus posts?" — se o contexto diz que é proibido usar logos das parceiras sem autorização, isso RESPONDE: "não, é proibido". Veredito "sim".)
- Mas esse "não/proibido" tem que vir DO CONTEXTO. Se o contexto não fundamenta resposta nenhuma, aí sim é "não".

ARMADILHAS (aqui o veredito é "não", porque a informação está genuinamente AUSENTE):
- A pergunta pede a DIFERENÇA ou COMPARAÇÃO entre A e B, mas o contexto só descreve um dos dois. (Ex.: diferença entre asteroide e cometa, mas o contexto só fala de asteroide → "não".)
- A pergunta pede um FATO ESPECÍFICO (um número, uma data, uma quantidade) que o contexto não afirma.
- A pergunta é sobre DADO PESSOAL ou EM TEMPO REAL (o que a MINHA equipe descobriu, quantas equipes teve em tal ano) que um material fixo não teria.
- A pergunta usa o vocabulário do tema mas pede algo que o material simplesmente não cobre.

Primeiro escreva um raciocínio curto comparando o que a pergunta PEDE com o que o contexto OFERECE. Só então dê o veredito.

Responda SOMENTE com um JSON válido, sem nenhum texto fora dele:
{"raciocinio": "<raciocínio curto>", "pode_responder": <true ou false>}"""


def _selecionar_contexto(results: list) -> list:
    """Mesmos chunks que a geração usa: score>=floor, top-3."""
    return [c for c in results if c["score"] >= CONTEXT_SCORE_FLOOR][:TOP_K_CONTEXT]


def _coerce_bool(v) -> bool:
    """
    O modelo deveria devolver um booleano, mas às vezes devolve string
    ("true"/"nao"). bool("nao") daria True (string não-vazia é truthy!), então
    normalizamos na mão. Default True = fail-open.
    """
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in ("true", "sim", "yes", "1")
    return True


async def grade_answerability(question: str, results: list, request_id: str) -> bool:
    """
    Decide se os chunks recuperados REALMENTE respondem à pergunta (não apenas
    tocam no assunto). Retorna True = pode gerar; False = cai no fallback.

    FILOSOFIA DE FALHA: FAIL-OPEN. Se o grader der erro, timeout ou vier
    ilegível, a gente PROSSEGUE para a geração (retorna True). O grader é uma
    proteção extra; se ele cair, o sistema degrada para o comportamento de hoje
    — nunca fica pior do que não ter grader nenhum.
    """
    contexto = _selecionar_contexto(results)

    if not contexto:
        # não deveria acontecer (o piso já garante >=1 chunk), mas por segurança:
        logger.warning(f"[{request_id}] [GRADER] Sem contexto após filtro → recusa")
        return False

    blocos = [f"[Chunk {i}] {c['content']}" for i, c in enumerate(contexto, 1)]
    user_prompt = (
        f"PERGUNTA:\n{question}\n\n"
        f"CONTEXTO:\n" + "\n\n".join(blocos) + "\n\n"
        f"O contexto responde à pergunta? Responda no formato JSON pedido."
    )

    try:
        logger.info(
            f"[{request_id}] [GRADER] Avaliando answerability ({len(contexto)} chunks)"
        )

        async with openai_semaphore:
            resp = await client_openai.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0,
                timeout=10,
                max_tokens=200,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": GRADER_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            )

        data = json.loads(resp.choices[0].message.content or "{}")
        pode = _coerce_bool(data.get("pode_responder", True))  # default: fail-open
        motivo = str(data.get("raciocinio", ""))[:200]

        logger.info(
            f"[{request_id}] [GRADER] veredito={'RESPONDE' if pode else 'RECUSA'} "
            f"| motivo='{motivo}'"
        )
        return pode

    except Exception as e:
        logger.error(
            f"[{request_id}] [GRADER ERROR] {e} → fail-open (segue para geração)"
        )
        return True