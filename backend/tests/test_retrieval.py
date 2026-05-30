"""
Harness de diagnóstico de retrieval + decisão.
Usa as funções REAIS do backend (services.retrieval.retrieve e
services.decision.should_answer) para medir o comportamento atual do sistema.

Rodar dentro do container (mesmo lugar onde o backend roda):
    docker compose exec rag python scripts/test_retrieval.py

Objetivo: coletar distance bruta, score normalizado, gap e a decisão de
cada query, para calibrar thresholds com base em dados — não no escuro.
"""

import sys
import os
import asyncio
import logging

# Garante que /app (raiz do backend) esteja no path, para os imports de services.*
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Silencia os logs do retrieve para a tabela ficar legível
logging.disable(logging.CRITICAL)

from services.retrieval import retrieve
from services.decision import should_answer


# (pergunta, esperado, comentário)
#   esperado = True  -> deveria RESPONDER (in-scope)
#   esperado = False -> deveria RECUSAR  (fora de escopo)
#   esperado = None  -> ambíguo, só observar
TESTES = [
    # ---- GRUPO A: deve responder (in-scope clássico) ----
    ("como faço pra pegar o certificado?",                 True,  "A in-scope"),
    ("qual a diferença entre certificado e medalha?",      True,  "A in-scope"),
    ("o que é o programa caça asteroides?",                True,  "A in-scope"),
    ("quem pode participar do programa?",                  True,  "A in-scope"),
    ("preciso saber astronomia pra participar?",           True,  "A in-scope"),
    ("o programa é pago?",                                 True,  "A in-scope"),
    ("como instalo o astrometrica?",                       True,  "A in-scope"),
    ("quando é a próxima campanha?",                       True,  "A in-scope"),

    # ---- GRUPO C: erros novos que competem entre si (foco) ----
    ("deu erro F51 ao enviar o relatório",                 True,  "C novo/competição"),
    ("o astrometrica não abre, deu runtime error",         True,  "C novo/competição"),
    ("deu erro de calibração e a option 2 não resolveu",   True,  "C novo/competição"),
    ("cliquei pra marcar e não acontece nada",             True,  "C novo/competição"),
    ("qual catálogo de estrelas eu seleciono?",            True,  "C novo/competição"),
    ("as imagens não estão todas disponíveis ainda",       True,  "C novo/competição"),
    ("apareceu floating point error",                      True,  "C novo/competição"),
    ("a tabela de objetos próximos está vazia",            True,  "C novo/competição"),

    # ---- GRUPO B: fora de escopo (deve recusar) ----
    ("qual a capital da frança?",                          False, "B fora de escopo"),
    ("me dá uma receita de bolo de chocolate",             False, "B fora de escopo"),
    ("quem ganhou a copa do mundo de 2022?",               False, "B fora de escopo"),
    ("como faço pra investir na bolsa de valores?",        False, "B fora de escopo"),

    # ---- borderline: vago de propósito ----
    ("deu erro",                                           None,  "borderline vago"),
]


def fmt(v, casas=2):
    return f"{v:.{casas}f}" if isinstance(v, (int, float)) else str(v)


async def main():
    acertos = 0
    contaveis = 0
    falsos_negativos = []
    falsos_positivos = []

    print("=" * 78)
    print("DIAGNÓSTICO DE RETRIEVAL + DECISÃO")
    print("=" * 78)

    for i, (q, esperado, nota) in enumerate(TESTES):
        results = await retrieve(q, f"test-{i}", n_results=5)
        decisao = should_answer(results)

        if not results:
            print(f"\n[{nota}] \"{q}\"")
            print("     (nenhum chunk retornado)")
            continue

        top1 = results[0]
        d1 = top1["distance"]
        s1 = top1["score"]
        cat1 = top1["metadata"].get("category", "?")
        id1 = top1["id"]

        d2 = s2 = gap = None
        if len(results) > 1:
            d2 = results[1]["distance"]
            s2 = results[1]["score"]
            gap = s1 - s2

        n_rel = len([r for r in results[:3] if r["score"] >= 0.4])

        # status vs esperado
        if esperado is None:
            status = "·"
        else:
            ok = (decisao == esperado)
            status = "✓" if ok else "✗"
            contaveis += 1
            if ok:
                acertos += 1
            elif esperado is True and decisao is False:
                falsos_negativos.append((q, id1, d1, gap, n_rel))
            elif esperado is False and decisao is True:
                falsos_positivos.append((q, id1, d1, gap, n_rel))

        dec_txt = "RESPONDER" if decisao else "RECUSAR  "
        esp_txt = {True: "RESPONDER", False: "RECUSAR", None: "ambíguo"}[esperado]

        print(f"\n[{status}] [{nota}] \"{q}\"")
        print(f"     esperado={esp_txt:<9} | decisão={dec_txt}")
        print(f"     top1: {id1:<14} ({cat1}) d={fmt(d1)} s={fmt(s1)}")
        if d2 is not None:
            print(f"     top2: {results[1]['id']:<14} "
                  f"({results[1]['metadata'].get('category','?')}) "
                  f"d={fmt(d2)} s={fmt(s2)} | gap={fmt(gap)} | n_rel={n_rel}")

    print("\n" + "=" * 78)
    print(f"RESUMO: {acertos}/{contaveis} decisões batem com o esperado")
    if falsos_negativos:
        print(f"\nFALSOS NEGATIVOS (deveria responder, mas recusou) — {len(falsos_negativos)}:")
        for q, idx, d1, gap, n_rel in falsos_negativos:
            print(f"   - \"{q}\"  [top1={idx} d={fmt(d1)} gap={fmt(gap)} n_rel={n_rel}]")
    if falsos_positivos:
        print(f"\nFALSOS POSITIVOS (deveria recusar, mas respondeu) — {len(falsos_positivos)}:")
        for q, idx, d1, gap, n_rel in falsos_positivos:
            print(f"   - \"{q}\"  [top1={idx} d={fmt(d1)} gap={fmt(gap)} n_rel={n_rel}]")
    if not falsos_negativos and not falsos_positivos:
        print("Nenhum erro de decisão nos casos com gabarito. 🎯")
    print("=" * 78)


if __name__ == "__main__":
    asyncio.run(main())