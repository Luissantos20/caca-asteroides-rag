"""
eval_floor.py — Valida o PISO de cos contra o dataset rotulado (dataset.py).

Roda o retrieve() REAL (precisa OPENAI_API_KEY). NÃO chama a geração.
Calcula cos = 1 - distância/2 direto da distância, então independe de você já
ter trocado a normalize_scores ou não. Mede DUAS coisas separadas:

  A) RECALL (independe do piso): quando há resposta na base, o chunk certo
     foi recuperado? P@1 / SC@3 / R@5 contra o gabarito 'validos'.
  B) CALIBRAÇÃO DO PISO: varredura de floor mostrando, em cada valor,
     TPR(in-scope passam) / TNR(adversarial barrados) / TNR(out barrados).

Onde colocar: backend/tests/ (ao lado de dataset.py).
Rodar de dentro de backend/:   python tests/eval_floor.py
"""

import os
import sys
import asyncio
import logging

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
sys.path.insert(0, BACKEND)   # para 'services'
sys.path.insert(0, HERE)      # para 'dataset'

logging.disable(logging.CRITICAL)  # silencia os logs do retrieve

from services.retrieval import retrieve
from dataset import IN_SCOPE, ADVERSARIAL, OUT_OF_SCOPE


def cos(d: float) -> float:
    return 1.0 - d / 2.0


def top_cos(results) -> float:
    return cos(results[0]["distance"]) if results else 0.0


def ids_topk(results, k):
    return [r["id"] for r in results[:k]]


async def cache_all():
    """Roda retrieve uma vez por query e guarda o resultado."""
    queries = [q for q, *_ in IN_SCOPE] + list(ADVERSARIAL) + list(OUT_OF_SCOPE)
    cache = {}
    for i, q in enumerate(queries, 1):
        cache[q] = await retrieve(q, f"eval-{i}")
        print(f"\r  retrieve {i}/{len(queries)}", end="", flush=True)
    print()
    return cache


def pctl(xs, p):
    xs = sorted(xs)
    if not xs:
        return 0.0
    k = (len(xs) - 1) * p / 100
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def bloco_recall(cache):
    print("\n" + "=" * 72)
    print("  A) RECALL DO RETRIEVAL (independe do piso)")
    print("  P@1 = válido no rank 1  |  SC@3 = válido nos top-3 (o que o LLM vê)")
    print("  R@5 = válido em algum top-5")
    print("=" * 72)
    p1 = sc3 = r5 = 0
    falhas = []
    for q, tipo, validos, contexto in IN_SCOPE:
        ids = ids_topk(cache[q], 5)
        if ids and ids[0] in validos:
            p1 += 1
        in3 = any(i in validos for i in ids[:3])
        if in3:
            sc3 += 1
        if any(i in validos for i in ids[:5]):
            r5 += 1
        if not in3:
            falhas.append((q, validos, ids[:3]))
    t = len(IN_SCOPE)
    print(f"\n  P@1  : {p1/t:6.1%}  ({p1}/{t})")
    print(f"  SC@3 : {sc3/t:6.1%}  ({sc3}/{t})   <- métrica principal (LLM recebe chunk válido)")
    print(f"  R@5  : {r5/t:6.1%}  ({r5}/{t})")
    if falhas:
        print(f"\n  Falhas de SC@3 — o LLM NÃO recebe chunk válido ({len(falhas)}):")
        for q, validos, got in falhas:
            print(f"    «{q[:55]}»")
            print(f"        esperado um de {validos}  |  veio {got}")
    else:
        print("\n  Nenhuma falha de SC@3 — o LLM sempre vê pelo menos um chunk válido.")


def bloco_distribuicao(cache):
    print("\n" + "=" * 72)
    print("  Distribuição de cos do TOPO por classe (dataset inteiro)")
    print("=" * 72)
    grupos = {
        "IN-SCOPE": [top_cos(cache[q]) for q, *_ in IN_SCOPE],
        "ADVERSARIAL": [top_cos(cache[q]) for q in ADVERSARIAL],
        "OUT-OF-SCOPE": [top_cos(cache[q]) for q in OUT_OF_SCOPE],
    }
    for nome, xs in grupos.items():
        print(f"\n  {nome:13s}  min={min(xs):.3f}  p10={pctl(xs,10):.3f}  "
              f"p50={pctl(xs,50):.3f}  max={max(xs):.3f}")
    return grupos


def bloco_varredura(cache, grupos):
    print("\n" + "=" * 72)
    print("  B) VARREDURA DO PISO")
    print("  TPR = in-scope que PASSam | TNR = fora/adversarial BARRADos")
    print("=" * 72)
    in_cos = grupos["IN-SCOPE"]
    adv_cos = grupos["ADVERSARIAL"]
    out_cos = grupos["OUT-OF-SCOPE"]
    floors = [0.30, 0.34, 0.38, 0.42, 0.46, 0.50, 0.55]
    print(f"\n  {'floor':>6} | {'TPR in':>7} | {'TNR adv':>8} | {'TNR out':>8}")
    print("  " + "-" * 40)
    for f in floors:
        tpr = sum(1 for c in in_cos if c >= f) / len(in_cos)
        tnr_adv = sum(1 for c in adv_cos if c < f) / len(adv_cos)
        tnr_out = sum(1 for c in out_cos if c < f) / len(out_cos)
        marca = "  <- proposto" if abs(f - 0.38) < 1e-9 else ""
        print(f"  {f:6.2f} | {tpr:7.1%} | {tnr_adv:8.1%} | {tnr_out:8.1%}{marca}")

    f = 0.38
    print("\n  --- detalhe no piso proposto (0.38) ---")
    bloqueadas = [(q, top_cos(cache[q])) for q, *_ in IN_SCOPE if top_cos(cache[q]) < f]
    passaram_adv = [(q, top_cos(cache[q])) for q in ADVERSARIAL if top_cos(cache[q]) >= f]
    if bloqueadas:
        print(f"  In-scope BARRADAS por engano ({len(bloqueadas)}) — o custo do piso:")
        for q, c in bloqueadas:
            print(f"    cos={c:.3f}  «{q[:55]}»")
    else:
        print("  Nenhuma in-scope barrada por engano. Piso não custa recall.")
    print(f"\n  Adversarial que PASSAM o piso ({len(passaram_adv)}/{len(ADVERSARIAL)}) "
          f"— estas a GERAÇÃO precisa recusar:")
    for q, c in passaram_adv:
        print(f"    cos={c:.3f}  «{q[:55]}»")


async def main():
    print("Rodando retrieve em todo o dataset...")
    cache = await cache_all()
    bloco_recall(cache)
    grupos = bloco_distribuicao(cache)
    bloco_varredura(cache, grupos)
    print("\n" + "=" * 72)
    print("  Leitura: escolha o piso que mantém TPR alto e TNR-out alto.")
    print("  TNR-adv vai ficar baixo em qualquer piso usável — é esperado.")
    print("  Conter adversarial é trabalho da geração, não do piso.")
    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(main())
