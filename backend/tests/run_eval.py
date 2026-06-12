"""
═══════════════════════════════════════════════════════════════════════
  RUNNER DE AVALIAÇÃO — Caça Asteroides (Etapa 1)
═══════════════════════════════════════════════════════════════════════
 
O QUE ELE FAZ
  Pega cada caso de eval_cases.py e roda pelo PIPELINE REAL do projeto,
  chamando as mesmas funções, na mesma ordem que api/.../pipeline.py:
 
      rewrite_query  →  retrieve  →  should_answer  →  generate_answer_stream
 
  Mas, diferente do pipeline de produção (que só "vê pra fora" o
  should_answer e os tokens), aqui a gente captura TUDO no caminho:
  query reescrita, os 5 chunks com score/distância/categoria, as features
  que a decision layer usa (gap, n_relevant...), o desfecho da geração e
  os tempos. Grava em JSONL (uma linha por pergunta).
 
POR QUE "ESPELHAR" O PIPELINE EM VEZ DE CHAMAR rag_pipeline_stream
  Porque rag_pipeline_stream não devolve os scores/distâncias — eles só
  existem nos logs. Chamando as camadas direto, capturamos o detalhe que
  permite achar padrão. O custo é um acoplamento: se você mudar a ORDEM
  ou os ARGUMENTOS no pipeline.py de produção, espelhe a mudança na função
  `rodar_um_caso` abaixo (está marcada com  # <<< ESPELHA pipeline.py).
 
ATENÇÃO — ISSO CHAMA A OPENAI DE VERDADE
  Cada caso faz: (0 ou 1) chamada de rewrite + 1 de embedding + 1 de
  geração. Custa tokens. 8 casos é trivial; quando escalarmos pra
  centenas, a gente conversa sobre custo/limite antes.
 
COMO RODAR (a partir da RAIZ do backend, onde estão as pastas services/ e chroma_db/)
    1. copie eval_cases.py e run_eval.py para dentro de tests/  (ou qualquer pasta do projeto)
    2. tenha o .env com OPENAI_API_KEY carregável
    3. python tests/run_eval.py
       opções: --limit N  (roda só os N primeiros)
               --out caminho.jsonl  (onde gravar; default: tests/results/run_<timestamp>.jsonl)
"""
 
import os
import sys
import json
import time
import uuid
import asyncio
import argparse
import importlib
from collections import Counter
from datetime import datetime
 
# ── Bootstrap de import ───────────────────────────────────────────────
# Garante que a RAIZ do backend (onde está services/) esteja no sys.path,
# independente de onde você rodar o script.
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.dirname(THIS_DIR)  # tests/ -> backend/
for p in (BACKEND_ROOT, THIS_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)
 
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass
 
# Funções REAIS do projeto (mesmas que o pipeline usa)
from services.rewrite_query import rewrite_query
from services.retrieval import retrieve
from services.decision import should_answer
from services.generate_answer import generate_answer_stream
 
# Os casos são carregados dinamicamente em main() (via --cases), pra você
# escolher o dataset: eval_cases (single-turn) ou eval_cases_multiturn.
 
 
# ══════════════════════════════════════════════════════════════════════
#  Features da decision layer (recalculadas pra registro/análise)
#  São os mesmos sinais que should_answer() usa internamente. Capturamos
#  pra conseguir explicar DEPOIS por que algo passou ou foi bloqueado.
# ══════════════════════════════════════════════════════════════════════
 
def extrair_features(results: list, relevance_cutoff: float = 0.4) -> dict:
    if not results:
        return {
            "top_id": None, "top_category": None,
            "top_distance": None, "top_score": None,
            "gap": None, "n_relevant_top3": 0,
        }
    top = results[0]
    gap = (results[0]["score"] - results[1]["score"]) if len(results) > 1 else None
    n_rel = sum(1 for r in results[:3] if r["score"] >= relevance_cutoff)
    return {
        "top_id": top["id"],
        "top_category": top["metadata"].get("category"),
        "top_distance": round(top["distance"], 4),
        "top_score": round(top["score"], 4),
        "gap": round(gap, 4) if gap is not None else None,
        "n_relevant_top3": n_rel,
    }
 
 
def resumir_chunks(results: list, k: int = 5) -> list:
    """Versão enxuta dos chunks pra gravar (sem o content inteiro)."""
    out = []
    for r in results[:k]:
        out.append({
            "id": r["id"],
            "category": r["metadata"].get("category"),
            "distance": round(r["distance"], 4),
            "score": round(r["score"], 4),
        })
    return out
 
 
# ══════════════════════════════════════════════════════════════════════
#  Executa UM caso pelo pipeline espelhado
# ══════════════════════════════════════════════════════════════════════
 
async def rodar_um_caso(caso: dict) -> dict:
    request_id = str(uuid.uuid4())[:8]
    query = caso["query"]
    history = caso.get("history") or []
 
    t0 = time.time()
    erro = None
    outcome = None          # "answered" | "refused_generation" | "blocked_decision" | "no_retrieval" | "interrupted" | "exception"
    answer_text = ""
    n_chunks_geracao = 0
 
    try:
        # ── 1. REWRITE ────────────────────────────────  # <<< ESPELHA pipeline.py
        t_rw = time.time()
        search_query = await rewrite_query(query, request_id, history)
        rewrite_ms = round((time.time() - t_rw) * 1000)
 
        # ── 2. RETRIEVE ───────────────────────────────  # <<< ESPELHA pipeline.py
        t_rt = time.time()
        results = await retrieve(search_query, request_id)
        retrieve_ms = round((time.time() - t_rt) * 1000)
 
        features = extrair_features(results)
        chunks = resumir_chunks(results)
 
        if not results:
            outcome = "no_retrieval"
        else:
            # ── 3. DECISION ───────────────────────────  # <<< ESPELHA pipeline.py
            decision = should_answer(results)
 
            if not decision:
                outcome = "blocked_decision"
            else:
                # ── 4. GENERATION ─────────────────────  # <<< ESPELHA pipeline.py
                # filtro de relevância igual ao da geração (score >= 0.4, top 3)
                n_chunks_geracao = len([c for c in results if c["score"] >= 0.4][:3])
 
                t_gen = time.time()
                tokens = []
                refused = False
                async for token in generate_answer_stream(
                    search_query, request_id, results, history=history
                ):
                    if token is None:
                        # None = recusa (<FALLBACK>) OU falha. Se ainda não
                        # saiu nenhum token, tratamos como recusa de geração.
                        refused = not bool(tokens)
                        if not refused:
                            outcome = "interrupted"
                        break
                    tokens.append(token)
 
                gen_ms = round((time.time() - t_gen) * 1000)
                answer_text = "".join(tokens)
 
                if outcome is None:
                    outcome = "refused_generation" if refused else "answered"
 
    except Exception as e:
        outcome = "exception"
        erro = f"{type(e).__name__}: {e}"
        # Garante variáveis pra montar o registro mesmo em falha
        search_query = locals().get("search_query", query)
        rewrite_ms = locals().get("rewrite_ms")
        retrieve_ms = locals().get("retrieve_ms")
        gen_ms = locals().get("gen_ms")
        features = locals().get("features", extrair_features([]))
        chunks = locals().get("chunks", [])
 
    total_ms = round((time.time() - t0) * 1000)
 
    # Comportamento esperado (responder/recusar) bateu?
    respondeu = (outcome == "answered")
    esperava_responder = (caso.get("expected_behavior") == "answer")
    behavior_match = (respondeu == esperava_responder)
 
    # Passa adiante TODAS as etiquetas do caso (persona, quality, anchor, etc),
    # menos `history` (pesado) — assim qualquer dimensão nova que você criar no
    # eval_cases.py já vai parar no JSONL sem precisar mexer aqui.
    tags = {k: v for k, v in caso.items() if k != "history"}
 
    return {
        # ---- identidade + TODAS as tags do caso (pra fatiar depois) ----
        **tags,
        # ---- entrada ----
        "history_len": len(history),
        "rewritten_query": locals().get("search_query", query),
        # ---- retrieval ----
        "features": features,
        "chunks": chunks,
        # ---- desfecho ----
        "outcome": outcome,
        "behavior_match": behavior_match,
        "n_chunks_geracao": n_chunks_geracao,
        "answer_text": answer_text,
        "error": erro,
        # ---- tempos ----
        "timing_ms": {
            "rewrite": locals().get("rewrite_ms"),
            "retrieve": locals().get("retrieve_ms"),
            "generation": locals().get("gen_ms"),
            "total": total_ms,
        },
        "request_id": request_id,
        "ts": datetime.now().isoformat(timespec="seconds"),
    }
 
 
# ══════════════════════════════════════════════════════════════════════
#  Impressão no terminal (visão rápida enquanto roda)
# ══════════════════════════════════════════════════════════════════════
 
ICONE = {
    "answered": "✅ respondeu",
    "refused_generation": "🟥 recusou (geração)",
    "blocked_decision": "🟧 bloqueou (decision)",
    "no_retrieval": "⬛ sem chunk",
    "interrupted": "⚠️  interrompeu",
    "exception": "💥 erro",
}
 
 
def imprimir_linha(reg: dict):
    f = reg["features"]
    match = "OK " if reg["behavior_match"] else "DIVERGE"
    print(
        f"  [{match:7}] {ICONE.get(reg['outcome'], reg['outcome']):24} "
        f"| {reg['category']:13} | top={f['top_id']} "
        f"score={f['top_score']} dist={f['top_distance']} gap={f['gap']} "
        f"n_rel={f['n_relevant_top3']}"
    )
    print(f"            q: '{reg['query']}'")
    if reg["rewritten_query"] != reg["query"]:
        print(f"            → reescrita: '{reg['rewritten_query']}'")
 
 
def imprimir_run(reg: dict, run_idx: int, n_runs: int):
    """Uma linha por execução. Mostra a query reescrita, que no multi-turn
    é o principal suspeito."""
    f = reg["features"]
    prefixo = f"      run {run_idx}/{n_runs}:" if n_runs > 1 else "     "
    print(
        f"{prefixo} {ICONE.get(reg['outcome'], reg['outcome']):24} "
        f"top={f['top_id']} score={f['top_score']} dist={f['top_distance']} gap={f['gap']}"
    )
    if reg["rewritten_query"] != reg["query"]:
        print(f"           ↳ rewrite: '{reg['rewritten_query']}'")
 
 
def imprimir_resumo(por_caso: dict):
    """por_caso: {case_id: {"caso": caso, "regs": [reg, ...]}}"""
    print("\n" + "═" * 72)
    print("  RESUMO")
    print("═" * 72)
 
    todos = [r for v in por_caso.values() for r in v["regs"]]
    por_outcome = Counter(r["outcome"] for r in todos)
    print(f"  Total de execuções: {len(todos)}")
    for oc, n in por_outcome.most_common():
        print(f"    {ICONE.get(oc, oc):26} {n}")
 
    # ---- INTERMITENTES: mesmo caso, desfechos diferentes entre as rodadas ----
    intermitentes = []
    sempre_diverge = []
    for cid, v in por_caso.items():
        outcomes = [r["outcome"] for r in v["regs"]]
        distintos = set(outcomes)
        matches = [r["behavior_match"] for r in v["regs"]]
        if len(distintos) > 1:
            intermitentes.append((cid, v, outcomes))
        elif not all(matches):
            sempre_diverge.append((cid, v))
 
    if intermitentes:
        print(f"\n  ⚠️  INTERMITENTES ({len(intermitentes)}) — "
              f"MESMO caso, desfecho MUDOU entre rodadas (a falha que caçamos):")
        for cid, v, outcomes in intermitentes:
            c = v["caso"]
            dist = Counter(outcomes)
            resumo = ", ".join(f"{n}x {ICONE.get(o, o)}" for o, n in dist.most_common())
            print(f"     [{cid}] cenário={c.get('scenario','-')} | '{c['query']}'")
            print(f"            → {resumo}")
            # mostra as reescritas distintas (o suspeito)
            rws = {r["rewritten_query"] for r in v["regs"]}
            if rws != {c["query"]}:
                for rw in rws:
                    print(f"            rewrite: '{rw}'")
 
    if sempre_diverge:
        print(f"\n  ❌ DIVERGÊNCIA ESTÁVEL ({len(sempre_diverge)}) — "
              f"erra em TODAS as rodadas (bug fixo, não intermitente):")
        for cid, v in sempre_diverge:
            c = v["caso"]
            oc = v["regs"][0]["outcome"]
            print(f"     [{cid}] {c.get('expected_behavior')}→{oc} | "
                  f"cenário={c.get('scenario','-')} | '{c['query']}'")
 
    if not intermitentes and not sempre_diverge:
        print("\n  ✅ Nenhuma intermitência nem divergência — todos estáveis e corretos.")
    print("═" * 72 + "\n")
 
 
# ══════════════════════════════════════════════════════════════════════
#  Main
# ══════════════════════════════════════════════════════════════════════
 
async def main():
    parser = argparse.ArgumentParser(description="Runner de avaliação — Caça Asteroides")
    parser.add_argument("--cases", type=str, default="eval_cases",
                        help="Módulo de casos (ex.: eval_cases, eval_cases_multiturn)")
    parser.add_argument("--repeat", type=int, default=1,
                        help="Quantas vezes rodar CADA caso (pega intermitência)")
    parser.add_argument("--limit", type=int, default=None, help="Roda só os N primeiros casos")
    parser.add_argument("--out", type=str, default=None, help="Arquivo JSONL de saída")
    args = parser.parse_args()
 
    # carrega o dataset escolhido
    try:
        mod = importlib.import_module(args.cases)
    except ModuleNotFoundError:
        mod = importlib.import_module(f"tests.{args.cases}")
    CASES = mod.CASES
    casos = CASES[: args.limit] if args.limit else CASES
 
    # caminho de saída
    if args.out:
        out_path = args.out
    else:
        results_dir = os.path.join(THIS_DIR, "results")
        os.makedirs(results_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = os.path.join(results_dir, f"run_{args.cases}_{stamp}.jsonl")
 
    total_exec = len(casos) * args.repeat
    print(f"\n  Dataset: {args.cases} | {len(casos)} caso(s) × {args.repeat} = {total_exec} execuções")
    print(f"  Saída: {out_path}\n")
    print("─" * 72)
 
    por_caso = {}
    with open(out_path, "w", encoding="utf-8") as f:
        for i, caso in enumerate(casos, 1):
            cid = caso.get("id", f"caso-{i}")
            por_caso[cid] = {"caso": caso, "regs": []}
            print(f"  ({i}/{len(casos)}) [{cid}] cenário={caso.get('scenario','-')} "
                  f"hist={len(caso.get('history') or [])} :: '{caso['query']}'")
            for r in range(1, args.repeat + 1):
                reg = await rodar_um_caso(caso)
                reg["run_idx"] = r
                por_caso[cid]["regs"].append(reg)
                f.write(json.dumps(reg, ensure_ascii=False) + "\n")
                f.flush()  # não perde o que já rodou se travar
                imprimir_run(reg, r, args.repeat)
 
    imprimir_resumo(por_caso)
    print(f"  💾 {total_exec} registros gravados em: {out_path}\n")
 
 
if __name__ == "__main__":
    asyncio.run(main())
 