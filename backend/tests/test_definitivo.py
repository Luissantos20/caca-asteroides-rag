"""
═══════════════════════════════════════════════════════════════════════
  TESTE DEFINITIVO — Caça Asteroides MCTI  (retrieval + decisão)
═══════════════════════════════════════════════════════════════════════

Roda DENTRO do container (onde o backend e o chroma_db vivem):

    docker compose exec rag python scripts/test_definitivo.py

Precisa de scripts/dataset.py ao lado.

O que ele faz, em 7 blocos:
  1. Saúde do dataset      — IDs do gabarito existem na collection? cobertura?
  2. Qualidade do retrieval — P@1, SC@3, R@5, por tipo, e falhas
  3. Mapa de distâncias    — distribuição de d(top1) por classe (o sinal-rei)
  4. Decisão ATUAL         — should_answer() real: TPR / TNR / erros
  5. Varredura de cutoff   — encontra a fronteira ótima de distância+gap
  6. Multi-turn            — o enriched_query do retrieve ajuda mesmo?
  7. Recomendações         — texto acionável derivado dos números

Princípio: o sistema é medido com as funções REAIS (retrieve, should_answer).
A varredura usa uma RÉPLICA parametrizável da decisão (decide_param), e o
bloco 5 confirma que ela reproduz o should_answer real antes de confiar nela.
"""

import sys
import os
import asyncio
import logging
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.disable(logging.CRITICAL)  # silencia os logs do retrieve

from services.retrieval import retrieve, collection
from services.decision import should_answer
from dataset import IN_SCOPE, ADVERSARIAL, OUT_OF_SCOPE, MULTI_TURN


# ─────────────────────────────────────────────────────────────────────
# Réplica PARAMETRIZÁVEL da decisão.
# Fiel ao should_answer atual, mas com o cutoff de distância (hoje 1.2
# hardcoded) e o gap_threshold expostos, para a varredura do Bloco 5.
# A consistência com o should_answer real é verificada antes de usar.
# ─────────────────────────────────────────────────────────────────────
def decide_param(results, dist_cutoff=1.2, gap_threshold=0.25,
                 relevance_cutoff=0.4, threshold=0.5):
    if not results:
        return False
    top_distance = results[0]["distance"]
    if top_distance > dist_cutoff:
        return False
    top_score = results[0]["score"]
    relevant = [r for r in results[:3] if r["score"] >= relevance_cutoff]
    gap = results[0]["score"] - results[1]["score"] if len(results) > 1 else None
    if gap is not None and top_distance > 0.85 and gap < 0.2 and len(relevant) < 2:
        return False
    if gap is not None and top_distance > 0.9 and gap < 0.3 and len(relevant) < 2:
        return False
    if top_score < threshold:
        return False
    if gap is not None and gap < gap_threshold and len(relevant) < 2 and top_distance > 0.85:
        return False
    return True


# ─────────────────────────────────────────────────────────────────────
# Helpers de estatística e impressão
# ─────────────────────────────────────────────────────────────────────
def stats(vals):
    v = sorted(vals)
    n = len(v)
    return {
        "min": v[0], "p25": v[n // 4], "med": v[n // 2],
        "p75": v[(3 * n) // 4], "max": v[-1], "media": sum(v) / n,
    }

def hist(vals, lo=0.3, hi=1.7, bins=14):
    step = (hi - lo) / bins
    buckets = [0] * bins
    for x in vals:
        idx = int((x - lo) / step)
        idx = max(0, min(bins - 1, idx))
        buckets[idx] += 1
    mx = max(buckets) or 1
    out = []
    for i, b in enumerate(buckets):
        a = lo + i * step
        bar = "█" * int(b / mx * 28)
        out.append(f"    {a:4.2f}–{a+step:4.2f} | {bar} {b}")
    return "\n".join(out)

def fmt(x, c=2):
    return f"{x:.{c}f}" if isinstance(x, (int, float)) else str(x)

def linha(c="─", n=72):
    print(c * n)


# ─────────────────────────────────────────────────────────────────────
# Cache de retrieval — roda cada query uma vez só
# ─────────────────────────────────────────────────────────────────────
async def montar_cache():
    cache = {}
    todas = ([q for q, *_ in IN_SCOPE] + ADVERSARIAL + OUT_OF_SCOPE)
    print(f"  Recuperando {len(todas)} queries (single-turn)...")
    for i, q in enumerate(todas):
        cache[q] = await retrieve(q, f"def-{i}", n_results=5)
    # multi-turn: com e sem histórico
    mt = []
    for j, (hist_msgs, q, val) in enumerate(MULTI_TURN):
        sem = await retrieve(q, f"mt-no-{j}", n_results=5)
        com = await retrieve(q, f"mt-yes-{j}", n_results=5, history=hist_msgs)
        mt.append({"q": q, "validos": val, "sem": sem, "com": com})
    print("  OK.\n")
    return cache, mt


# ─────────────────────────────────────────────────────────────────────
# BLOCO 1 — Saúde do dataset (contra a collection REAL)
# ─────────────────────────────────────────────────────────────────────
def bloco1_saude():
    print("\n" + "═" * 72)
    print("  BLOCO 1 — SAÚDE DO DATASET (vs. collection real)")
    print("═" * 72)
    ids_reais = set(collection.get()["ids"])
    print(f"  Chunks na collection: {len(ids_reais)}")

    ref = set()
    for q, tipo, val, ctx in IN_SCOPE:
        ref |= set(val) | set(ctx)
    for hmsgs, q, val in MULTI_TURN:
        ref |= set(val)
    quebrados = sorted(ref - ids_reais)
    if quebrados:
        print(f"  ❌ {len(quebrados)} IDs do gabarito NÃO existem na collection:")
        for x in quebrados:
            print(f"       {x}")
        print("  → corrija o dataset.py antes de confiar nas métricas abaixo.")
    else:
        print(f"  ✓ Todos os {len(ref)} IDs do gabarito existem na collection.")


# ─────────────────────────────────────────────────────────────────────
# BLOCO 2 — Qualidade do retrieval (ranking puro, sem decisão)
# ─────────────────────────────────────────────────────────────────────
def bloco2_retrieval(cache):
    print("\n" + "═" * 72)
    print("  BLOCO 2 — QUALIDADE DO RETRIEVAL")
    print("  P@1 = válido no rank 1 | SC@3 = válido nos top-3 (o que o LLM vê)")
    print("  R@5 = válido em algum top-5")
    print("═" * 72)

    p1 = sc3 = r5 = 0
    por_tipo = defaultdict(lambda: {"n": 0, "sc3": 0})
    falhas_sc3 = []

    for q, tipo, val, ctx in IN_SCOPE:
        res = cache[q]
        ids = [r["id"] for r in res]
        top3 = ids[:3]
        ok_p1 = ids and ids[0] in val
        ok_sc3 = any(c in top3 for c in val)
        ok_r5 = any(c in ids for c in val)
        p1 += ok_p1; sc3 += ok_sc3; r5 += ok_r5
        por_tipo[tipo]["n"] += 1
        por_tipo[tipo]["sc3"] += ok_sc3
        if not ok_sc3:
            falhas_sc3.append((q, val, top3))

    t = len(IN_SCOPE)
    print(f"\n  P@1  : {p1/t:6.1%}  ({p1}/{t})")
    print(f"  SC@3 : {sc3/t:6.1%}  ({sc3}/{t})   ← métrica principal")
    print(f"  R@5  : {r5/t:6.1%}  ({r5}/{t})")

    print("\n  Por tipo (SC@3):")
    for tipo in sorted(por_tipo, key=lambda k: por_tipo[k]["sc3"]/por_tipo[k]["n"]):
        d = por_tipo[tipo]
        rate = d["sc3"] / d["n"]
        bar = "█" * int(rate * 16) + "░" * (16 - int(rate * 16))
        print(f"    {tipo:18} {rate:5.0%} {bar} ({d['sc3']}/{d['n']})")

    if falhas_sc3:
        print(f"\n  ❌ Falhas de SC@3 — LLM NÃO recebe chunk válido ({len(falhas_sc3)}):")
        for q, val, top3 in falhas_sc3:
            print(f"    '{q}'")
            print(f"       esperava um de: {val}")
            print(f"       recebeu top3 : {top3}")
    else:
        print("\n  ✓ Nenhuma falha de SC@3 — o LLM sempre recebe contexto válido.")
    return sc3 / t


# ─────────────────────────────────────────────────────────────────────
# BLOCO 3 — Mapa de distâncias (a feature que separa responder/recusar)
# ─────────────────────────────────────────────────────────────────────
def bloco3_distancias(cache):
    print("\n" + "═" * 72)
    print("  BLOCO 3 — MAPA DE DISTÂNCIAS  d(top1) por classe")
    print("  É a distância ABSOLUTA (não o score) que separa as classes.")
    print("═" * 72)

    d_in  = [cache[q][0]["distance"] for q, *_ in IN_SCOPE if cache[q]]
    d_adv = [cache[q][0]["distance"] for q in ADVERSARIAL if cache[q]]
    d_out = [cache[q][0]["distance"] for q in OUT_OF_SCOPE if cache[q]]

    for nome, vals in [("IN-SCOPE", d_in), ("ADVERSARIAL", d_adv), ("OUT-OF-SCOPE", d_out)]:
        s = stats(vals)
        print(f"\n  {nome} (n={len(vals)})")
        print(f"    min={s['min']:.2f}  p25={s['p25']:.2f}  med={s['med']:.2f}  "
              f"p75={s['p75']:.2f}  max={s['max']:.2f}")
        print(hist(vals))

    # zona de fronteira: onde in-scope alto encontra adversarial baixo
    in_max = max(d_in)
    adv_min = min(d_adv)
    print("\n  FRONTEIRA:")
    print(f"    in-scope vai até  {in_max:.2f}")
    print(f"    adversarial começa em {adv_min:.2f}")
    if adv_min > in_max:
        print(f"    ✓ Há separação limpa entre {in_max:.2f} e {adv_min:.2f} — "
              f"um cutoff aqui separa bem.")
    else:
        print(f"    ⚠ Há SOBREPOSIÇÃO ({adv_min:.2f} ≤ {in_max:.2f}) — "
              f"nenhum cutoff de distância separa 100%. Veja o Bloco 5.")
    return d_in, d_adv, d_out


# ─────────────────────────────────────────────────────────────────────
# BLOCO 4 — Decisão ATUAL (should_answer real, defaults de produção)
# ─────────────────────────────────────────────────────────────────────
def bloco4_decisao(cache):
    print("\n" + "═" * 72)
    print("  BLOCO 4 — DECISÃO ATUAL  (should_answer com defaults de produção)")
    print("  TPR = in-scope aceitas | TNR = fora bloqueadas (maior = melhor)")
    print("═" * 72)

    tp = sum(1 for q, *_ in IN_SCOPE if should_answer(cache[q]))
    fn = len(IN_SCOPE) - tp
    tn_adv = sum(1 for q in ADVERSARIAL if not should_answer(cache[q]))
    tn_out = sum(1 for q in OUT_OF_SCOPE if not should_answer(cache[q]))

    print(f"\n  TPR (in-scope)      : {tp/len(IN_SCOPE):6.1%}  ({tp}/{len(IN_SCOPE)})")
    print(f"  TNR (adversarial)   : {tn_adv/len(ADVERSARIAL):6.1%}  ({tn_adv}/{len(ADVERSARIAL)})")
    print(f"  TNR (out-of-scope)  : {tn_out/len(OUT_OF_SCOPE):6.1%}  ({tn_out}/{len(OUT_OF_SCOPE)})")

    fn_list = [(q, cache[q]) for q, *_ in IN_SCOPE if not should_answer(cache[q])]
    fp_list = [(q, cache[q]) for q in (ADVERSARIAL + OUT_OF_SCOPE) if should_answer(cache[q])]

    if fn_list:
        print(f"\n  ❌ FALSOS NEGATIVOS (in-scope recusadas) — {len(fn_list)}:")
        for q, res in fn_list:
            g = res[0]["score"] - res[1]["score"] if len(res) > 1 else None
            print(f"    d={res[0]['distance']:.2f} gap={fmt(g)} '{q}'")
    if fp_list:
        print(f"\n  ⚠ FALSOS POSITIVOS (fora aceitas) — {len(fp_list)}:")
        for q, res in fp_list:
            g = res[0]["score"] - res[1]["score"] if len(res) > 1 else None
            print(f"    d={res[0]['distance']:.2f} gap={fmt(g)} '{q}'")
    if not fn_list and not fp_list:
        print("\n  ✓ Nenhum erro de decisão com os defaults atuais.")
    return tp, fn_list, fp_list


# ─────────────────────────────────────────────────────────────────────
# BLOCO 5 — Varredura: encontra a melhor fronteira (dist_cutoff × gap)
# ─────────────────────────────────────────────────────────────────────
def bloco5_varredura(cache):
    print("\n" + "═" * 72)
    print("  BLOCO 5 — VARREDURA DE CALIBRAÇÃO")
    print("═" * 72)

    # consistência: decide_param @ defaults deve reproduzir should_answer
    div = 0
    for q in [q for q, *_ in IN_SCOPE] + ADVERSARIAL + OUT_OF_SCOPE:
        if decide_param(cache[q]) != should_answer(cache[q]):
            div += 1
    if div:
        print(f"  ⚠ decide_param diverge de should_answer em {div} queries — "
              f"a varredura abaixo NÃO é confiável. Revise decide_param.")
    else:
        print("  ✓ decide_param reproduz should_answer (defaults). Varredura confiável.\n")

    cutoffs = [round(1.0 + 0.05 * i, 2) for i in range(8)]   # 1.00..1.35
    gaps = [0.15, 0.20, 0.25, 0.30]
    n_in, n_adv, n_out = len(IN_SCOPE), len(ADVERSARIAL), len(OUT_OF_SCOPE)

    print(f"  {'cutoff':>6} {'gap':>5} | {'TPR':>6} {'TNR_adv':>7} {'TNR_out':>7} | {'score':>6}")
    linha()
    melhor = None
    for dc in cutoffs:
        for g in gaps:
            tp  = sum(1 for q, *_ in IN_SCOPE if decide_param(cache[q], dc, g))
            tadv = sum(1 for q in ADVERSARIAL if not decide_param(cache[q], dc, g))
            tout = sum(1 for q in OUT_OF_SCOPE if not decide_param(cache[q], dc, g))
            tpr, radv, rout = tp/n_in, tadv/n_adv, tout/n_out
            # score: cobertura in-scope pesa, contenção adversarial pesa mais
            score = 0.45 * tpr + 0.40 * radv + 0.15 * rout
            if melhor is None or score > melhor[0]:
                melhor = (score, dc, g, tpr, radv, rout)
            marca = " ←" if (dc == 1.2 and g == 0.25) else ""
            print(f"  {dc:>6.2f} {g:>5.2f} | {tpr:>6.1%} {radv:>7.1%} {rout:>7.1%} | {score:>6.3f}{marca}")
    linha()
    print(f"  (← = configuração atual de produção: cutoff=1.20 gap=0.25)\n")
    _, dc, g, tpr, radv, rout = melhor
    print(f"  MELHOR por score combinado: cutoff={dc:.2f} gap={g:.2f}")
    print(f"     TPR={tpr:.1%}  TNR_adv={radv:.1%}  TNR_out={rout:.1%}")
    return melhor


# ─────────────────────────────────────────────────────────────────────
# BLOCO 6 — Multi-turn: o enriched_query ajuda?
# ─────────────────────────────────────────────────────────────────────
def bloco6_multiturn(mt):
    print("\n" + "═" * 72)
    print("  BLOCO 6 — MULTI-TURN (enriched_query: last_user + follow-up)")
    print("  Compara SC@3 do follow-up SOZINHO vs COM histórico.")
    print("═" * 72)
    ganhou = 0
    for item in mt:
        top3_sem = [r["id"] for r in item["sem"]][:3]
        top3_com = [r["id"] for r in item["com"]][:3]
        ok_sem = any(c in top3_sem for c in item["validos"])
        ok_com = any(c in top3_com for c in item["validos"])
        if ok_com and not ok_sem:
            ganhou += 1
        s = {True: "✓", False: "✗"}
        print(f"\n  '{item['q']}'  (espera {item['validos']})")
        print(f"    sem histórico: {s[ok_sem]}  top3={top3_sem}")
        print(f"    com histórico: {s[ok_com]}  top3={top3_com}")
    print(f"\n  Histórico recuperou contexto em {ganhou}/{len(mt)} casos "
          f"que falhariam sem ele.")


# ─────────────────────────────────────────────────────────────────────
# BLOCO 7 — Recomendações automáticas
# ─────────────────────────────────────────────────────────────────────
def bloco7_recs(sc3_rate, d_in, d_adv, dec_atual, melhor):
    print("\n" + "═" * 72)
    print("  BLOCO 7 — RECOMENDAÇÕES (derivadas dos números acima)")
    print("═" * 72)
    tp, fn_list, fp_list = dec_atual
    _, dc, g, tpr, radv, rout = melhor

    if sc3_rate < 0.9:
        print("  • SC@3 abaixo de 90%: há perguntas cujo chunk certo nem chega aos")
        print("    top-3. Isso é problema de RETRIEVAL/CONTEÚDO, não de threshold —")
        print("    mexer no cutoff não resolve. Revise keywords/related_questions")
        print("    dos chunks que falharam no Bloco 2.")
    else:
        print("  • SC@3 ≥ 90%: o retrieval entrega o chunk certo. O que sobra é só")
        print("    calibrar a decisão (responder/recusar).")

    overlap = min(d_adv) <= max(d_in)
    if overlap:
        print(f"  • Distâncias in-scope e adversarial se SOBREPÕEM. Nenhum cutoff")
        print(f"    separa 100% — escolha o trade-off no Bloco 5.")
    else:
        print(f"  • Distâncias bem separadas: cutoff entre {max(d_in):.2f} e "
              f"{min(d_adv):.2f} é seguro.")

    if (dc, g) != (1.2, 0.25):
        print(f"  • A varredura sugere mudar de (cutoff=1.20, gap=0.25) para")
        print(f"    (cutoff={dc:.2f}, gap={g:.2f}). Para aplicar, exponha o cutoff")
        print(f"    como parâmetro nomeado no should_answer (hoje o 1.2 é hardcoded).")
    else:
        print("  • A configuração atual (cutoff=1.20, gap=0.25) já é a melhor da")
        print("    varredura — não há ganho em mexer.")

    if fp_list:
        print(f"  • {len(fp_list)} consultas fora do escopo passaram. É o risco mais")
        print(f"    sério (alucinação). Priorize baixar o cutoff mesmo perdendo um")
        print(f"    pouco de TPR.")
    if fn_list:
        print(f"  • {len(fn_list)} consultas legítimas foram recusadas. Se forem do")
        print(f"    grupo adversarial-vizinho, é aceitável; se forem in-scope claras,")
        print(f"    o cutoff/gap está apertado.")

    print("  • Lembrete: o threshold de SCORE (0.5) é regra morta (score do topo é")
    print("    sempre 1.0 por min-max). A contenção real é distância + gap.")
    print("═" * 72)


# ─────────────────────────────────────────────────────────────────────
async def main():
    print("\n" + "═" * 72)
    print("  TESTE DEFINITIVO — Caça Asteroides MCTI")
    print(f"  in-scope={len(IN_SCOPE)} | adversarial={len(ADVERSARIAL)} | "
          f"out={len(OUT_OF_SCOPE)} | multi-turn={len(MULTI_TURN)}")
    print("═" * 72)

    cache, mt = await montar_cache()

    bloco1_saude()
    sc3_rate = bloco2_retrieval(cache)
    d_in, d_adv, d_out = bloco3_distancias(cache)
    dec_atual = bloco4_decisao(cache)
    melhor = bloco5_varredura(cache)
    bloco6_multiturn(mt)
    bloco7_recs(sc3_rate, d_in, d_adv, dec_atual, melhor)


if __name__ == "__main__":
    asyncio.run(main())
