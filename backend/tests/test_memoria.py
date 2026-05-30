"""
═══════════════════════════════════════════════════════════════════════
  TESTE DE MEMÓRIA — valida o query rewriting (multi-turn)
═══════════════════════════════════════════════════════════════════════

Roda DENTRO do container:
    docker compose exec rag python scripts/test_memoria.py

Reproduz os cenários que você testou no front. Para cada um, compara
três formas de montar a query que vai pro embedding:

  CRUA      → só a pergunta do follow-up, sem histórico (baseline ruim)
  CONCAT    → "{última fala do usuário} {pergunta}"  (o método ANTIGO)
  REWRITE   → rewrite_query(pergunta, history)        (o método NOVO)

Para cada forma, recupera os top-3 e marca se o chunk esperado apareceu.
O que queremos ver: REWRITE acertando onde CONCAT errava (testes 4 e 5),
sem perder os que CONCAT já acertava (testes 1 e 3).

Custo: algumas chamadas de embedding + 1 rewrite por cenário. Centavos.
"""

import sys
import os
import asyncio
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.disable(logging.CRITICAL)

from services.retrieval import get_embedding, normalize_scores, collection
from services.rewrite_query import rewrite_query


# Cenários: (nome, history, pergunta_followup, chunks_esperados)
# history termina na última fala antes do follow-up.
CENARIOS = [
    ("T1 mesmo assunto (certificado→nome)",
     [{"role": "user", "content": "como pego o certificado?"},
      {"role": "assistant", "content": "É solicitado na plataforma do IASC ao fim da campanha, e o líder identifica os participantes."}],
     "e se eu errar o nome?",
     ["DOC03-CMD-04"]),

    ("T2 depende da fala do bot (relatório)",
     [{"role": "user", "content": "terminei de analisar as imagens e não achei nenhum asteroide"},
      {"role": "assistant", "content": "Mesmo sem detecções você precisa enviar um relatório informando que nada foi encontrado."}],
     "como faço isso?",
     ["DOC06-QSG-16", "DOC02-FCP-10"]),

    ("T3 continuidade técnica (calibração→option2)",
     [{"role": "user", "content": "deu erro de calibração no astrometrica"},
      {"role": "assistant", "content": "Selecione a Option 2 (Automatic Reference Star Match) e clique OK."}],
     "e se a option 2 não resolver?",
     ["DOC07-ERR-05"]),

    ("T4 TROCA de assunto (instalação→elegibilidade)",
     [{"role": "user", "content": "como instalo o astrometrica?"},
      {"role": "assistant", "content": "Baixe pelo site do IASC, extraia o zip e rode o setup.exe."}],
     "quem pode participar do programa?",
     ["DOC05-CHUNK-02"]),

    ("T5 follow-up vago (inscrição→como)",
     [{"role": "user", "content": "quero participar"},
      {"role": "assistant", "content": "Que ótimo! A participação é feita em equipe, com inscrição pelo site."}],
     "e como?",
     ["DOC02-FCP-02", "DOC05-CHUNK-04"]),
]


async def top3_para(texto):
    """Recupera os top-3 ids para um texto de query já montado."""
    emb = await get_embedding(texto)
    res = collection.query(query_embeddings=[emb], n_results=5)
    ids = res["ids"][0]
    return ids[:3]


def ultima_fala_usuario(history):
    for msg in reversed(history):
        if msg["role"] == "user":
            return msg["content"]
    return None


def acertou(top3, esperados):
    return any(c in top3 for c in esperados)


async def main():
    print("\n" + "═" * 72)
    print("  TESTE DE MEMÓRIA — concatenação (antigo) vs rewrite (novo)")
    print("═" * 72)

    placar = {"crua": 0, "concat": 0, "rewrite": 0}
    total = len(CENARIOS)

    for nome, history, pergunta, esperados in CENARIOS:
        # CRUA
        t3_crua = await top3_para(pergunta)
        # CONCAT (método antigo)
        ult = ultima_fala_usuario(history)
        concat = f"{ult} {pergunta}" if ult else pergunta
        t3_concat = await top3_para(concat)
        # REWRITE (método novo)
        reescrita = await rewrite_query(pergunta, "test-mem", history)
        t3_rewrite = await top3_para(reescrita)

        ok_crua = acertou(t3_crua, esperados)
        ok_concat = acertou(t3_concat, esperados)
        ok_rewrite = acertou(t3_rewrite, esperados)
        placar["crua"] += ok_crua
        placar["concat"] += ok_concat
        placar["rewrite"] += ok_rewrite

        s = {True: "✓", False: "✗"}
        print(f"\n  {nome}")
        print(f"    follow-up: '{pergunta}'   espera: {esperados}")
        print(f"    reescrita: '{reescrita}'")
        print(f"    [{s[ok_crua]}] CRUA    top3={t3_crua}")
        print(f"    [{s[ok_concat]}] CONCAT  top3={t3_concat}")
        print(f"    [{s[ok_rewrite]}] REWRITE top3={t3_rewrite}")

    print("\n" + "═" * 72)
    print("  PLACAR (acertos de SC@3 em cada método)")
    print("═" * 72)
    print(f"    CRUA    (sem memória)        : {placar['crua']}/{total}")
    print(f"    CONCAT  (método antigo)      : {placar['concat']}/{total}")
    print(f"    REWRITE (método novo)        : {placar['rewrite']}/{total}")
    print()
    if placar["rewrite"] > placar["concat"]:
        print("  ✅ Rewrite melhorou em relação ao método antigo. Aplicar.")
    elif placar["rewrite"] == placar["concat"] == total:
        print("  ✅ Ambos acertam tudo neste conjunto — rewrite não regrediu.")
    elif placar["rewrite"] < placar["concat"]:
        print("  ⚠ Rewrite regrediu em algum caso — investigar a reescrita acima.")
    else:
        print("  ~ Empate abaixo do máximo — veja os casos que ainda falham.")
    print("═" * 72)


if __name__ == "__main__":
    asyncio.run(main())