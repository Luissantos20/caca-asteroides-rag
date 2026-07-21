"""
eval_gate.py — Bancada de calibração do PORTÃO (grounding gate).

Mesma ideia do eval_floor, aplicada ao juiz SIM/NAO. Para cada pergunta de
veredito conhecido:
  1) roda o retrieve() real (mesmo do pipeline)
  2) aplica o piso (RELEVANCE_FLOOR) — se não passa, o SISTEMA já recusa no piso
  3) monta o MESMO contexto que a geração veria (top-3 acima do piso, 900 chars)
  4) chama o portão com esse contexto + pergunta -> SIM / NAO
  5) compara com o esperado e conta os DOIS erros:
       - falso NAO  = legítima recusada (dói: perde recall)
       - falso SIM  = adversarial/lixo que passou (dói: alucina)

O PROMPT DO PORTÃO está aqui embaixo (GATE_PROMPT). Edite, rode de novo, veja os
números mexerem. É esse o loop de calibração: mede -> corta/ajusta -> mede.

Onde colocar: backend/tests/ (ao lado de dataset.py e eval_floor.py).
Rodar de dentro de backend/:   python tests/eval_gate.py
"""

import os
import sys
import asyncio
import logging

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
sys.path.insert(0, BACKEND)
sys.path.insert(0, HERE)

from dotenv import load_dotenv
load_dotenv()
logging.disable(logging.CRITICAL)

from services.retrieval import retrieve
from services.decision import RELEVANCE_FLOOR
from services.openai_client import client_openai
from dataset import IN_SCOPE, ADVERSARIAL, OUT_OF_SCOPE


# ─────────────────────────────────────────────────────────────────────
# PROMPT DO PORTÃO — edite aqui e rode de novo. É a peça sob calibração.
# ─────────────────────────────────────────────────────────────────────
GATE_PROMPT = """
Você é um verificador de grounding do assistente do programa Caça Asteroides MCTI.
Sua ÚNICA tarefa é decidir se o CONTEXTO abaixo permite responder à pergunta.
Você NÃO responde à pergunta. Emita só um veredito: SIM ou NAO.

Pergunte a si mesmo: "o contexto RESOLVE esta pergunta?"
- SIM = o contexto contém o que decide a pergunta — a resposta pode ser
  afirmativa OU negativa. Uma regra, proibição, exigência, limite ou critério
  que decide a questão CONTA como resolver.
- NAO = o contexto é SILENCIOSO sobre o que foi perguntado, ou só fala de outro
  aspecto do tema.

PRINCÍPIOS:
- A FORMA da pergunta nunca decide o veredito ("minha", "do ano passado",
  "posso...?", "dá pra...?"). Se o contexto traz a regra ou o processo, é SIM.
- Aplicar um critério do contexto é SIM — TANTO para INCLUIR quanto para EXCLUIR
  um caso. Se o contexto define um requisito e a pergunta traz um caso que NÃO
  atende a esse requisito, isso é RESPONDER (a resposta é "não atende"), não é
  silêncio. Só é NAO quando o contexto não define aquele critério de forma alguma.
- Vocabulário ou tema em comum NÃO basta. Se o contexto trata do assunto geral
  mas não do que a pergunta especificamente pede, é NAO.
- Conhecimento externo NÃO conta. Só vale o que está escrito no contexto.
- Registro INDIVIDUAL do usuário nunca está no contexto (o que MINHA equipe
  descobriu, se MINHA inscrição foi aprovada, se MINHA equipe vai ganhar) → NAO.

EXEMPLOS (ilustram o princípio, não são os casos exatos):
- Contexto define um requisito mínimo; a pergunta traz um caso abaixo desse
  mínimo → SIM (o contexto resolve: a resposta é "não atende ao requisito").
- Contexto proíbe uma conduta; a pergunta pergunta se pode fazê-la → SIM
  (a resposta é "não pode").
- Contexto descreve um procedimento do programa; a pergunta pede um conceito
  científico geral que não está ali → NAO (mesmo tema amplo, mas o contexto
  silencia sobre o que foi pedido).

Responda com UMA palavra, em maiúscula, sem pontuação: SIM ou NAO.

Contexto:
{context}

Pergunta:
{query}
"""


def montar_contexto(results):
    relevant = [c for c in results if c["score"] >= RELEVANCE_FLOOR][:3]
    if not relevant:
        return None
    return "\n\n".join(
        f"[{c['metadata']['category']}]\n{c['content'][:900]}" for c in relevant
    )


async def portao(context: str, query: str) -> str:
    """Chama o juiz. Retorna 'SIM', 'NAO' ou 'AMBIGUO'."""
    prompt = GATE_PROMPT.format(context=context, query=query)
    resp = await client_openai.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        max_tokens=5,
        messages=[{"role": "user", "content": prompt}],
    )
    txt = (resp.choices[0].message.content or "").strip().upper()
    if "NAO" in txt or "NÃO" in txt:
        return "NAO"
    if "SIM" in txt:
        return "SIM"
    return f"AMBIGUO({txt[:15]})"


async def decidir(query: str):
    """Reproduz a lógica do pipeline: piso -> portão. Retorna (decisao, detalhe)."""
    results = await retrieve(query, "evalgate")
    if not results:
        return "REFUSE", {"onde": "piso", "top_cos": 0.0}
    top_cos = results[0]["score"]
    if top_cos < RELEVANCE_FLOOR:
        return "REFUSE", {"onde": "piso", "top_cos": top_cos}
    context = montar_contexto(results)
    if context is None:
        return "REFUSE", {"onde": "piso", "top_cos": top_cos}
    verdict = await portao(context, query)
    if verdict == "SIM":
        return "ANSWER", {"onde": "gate", "top_cos": top_cos, "gate": verdict}
    return "REFUSE", {"onde": "gate", "top_cos": top_cos, "gate": verdict}


async def rodar_classe(nome, perguntas, esperado):
    """esperado = 'ANSWER' (in-scope) ou 'REFUSE' (adversarial/out)."""
    print(f"\n  rodando {nome} ({len(perguntas)})...", flush=True)
    linhas = []
    for i, q in enumerate(perguntas, 1):
        dec, det = await decidir(q)
        linhas.append((q, dec, det))
        print(f"\r    {i}/{len(perguntas)}", end="", flush=True)
    print()
    return linhas


def is_query(item):
    # IN_SCOPE traz tuplas (q, tipo, validos, contexto); os outros são strings
    return item[0] if isinstance(item, tuple) else item


async def main():
    print("=" * 74)
    print("  EVAL GATE — calibração do portão (piso atual = %.2f)" % RELEVANCE_FLOOR)
    print("=" * 74)

    in_q = [is_query(x) for x in IN_SCOPE]
    adv_q = list(ADVERSARIAL)
    out_q = list(OUT_OF_SCOPE)

    r_in = await rodar_classe("IN_SCOPE (esperado ANSWER)", in_q, "ANSWER")
    r_adv = await rodar_classe("ADVERSARIAL (esperado REFUSE)", adv_q, "REFUSE")
    r_out = await rodar_classe("OUT_OF_SCOPE (esperado REFUSE)", out_q, "REFUSE")

    # ---- erros ----
    falso_nao = [(q, det) for q, dec, det in r_in if dec == "REFUSE"]
    falso_sim_adv = [(q, det) for q, dec, det in r_adv if dec == "ANSWER"]
    falso_sim_out = [(q, det) for q, dec, det in r_out if dec == "ANSWER"]
    ambiguos = [(q, det) for lst in (r_in, r_adv, r_out)
                for q, dec, det in lst if str(det.get("gate", "")).startswith("AMBIGUO")]

    print("\n" + "#" * 74)
    print("  ERROS")
    print("#" * 74)

    print(f"\n  FALSO NAO — in-scope recusadas por engano ({len(falso_nao)}/{len(r_in)}):")
    if not falso_nao:
        print("    (nenhuma — recall preservado)")
    for q, det in falso_nao:
        print(f"    [{det['onde']:4}] cos={det['top_cos']:.3f}  «{q[:52]}»")

    print(f"\n  FALSO SIM — adversarial que passou ({len(falso_sim_adv)}/{len(r_adv)}):")
    if not falso_sim_adv:
        print("    (nenhuma — contenção perfeita)")
    for q, det in falso_sim_adv:
        print(f"    cos={det['top_cos']:.3f}  «{q[:56]}»")

    print(f"\n  FALSO SIM — out-of-scope que passou ({len(falso_sim_out)}/{len(r_out)}):")
    if not falso_sim_out:
        print("    (nenhuma — piso segurou o lixo)")
    for q, det in falso_sim_out:
        print(f"    cos={det['top_cos']:.3f}  «{q[:56]}»")

    if ambiguos:
        print(f"\n  AMBÍGUOS — portão não devolveu SIM/NAO limpo ({len(ambiguos)}):")
        for q, det in ambiguos:
            print(f"    {det.get('gate')}  «{q[:50]}»")

    # ---- placar ----
    print("\n" + "#" * 74)
    print("  PLACAR")
    print("#" * 74)
    acc_in = 1 - len(falso_nao) / len(r_in)
    acc_adv = 1 - len(falso_sim_adv) / len(r_adv)
    acc_out = 1 - len(falso_sim_out) / len(r_out)
    print(f"  IN_SCOPE    acerto (SIM correto): {acc_in:6.1%}   -> recall")
    print(f"  ADVERSARIAL acerto (NAO correto): {acc_adv:6.1%}   -> contenção da alucinação")
    print(f"  OUT_OF_SCOPE acerto:              {acc_out:6.1%}   -> deve ser ~100% (piso)")
    print()
    print("  Leitura: falso NAO alto = portão paranoico (recusa legítimas).")
    print("           falso SIM alto = portão frouxo (deixa alucinar).")
    print("           Ajuste o GATE_PROMPT e rode de novo até equilibrar os dois.")


if __name__ == "__main__":
    asyncio.run(main())
