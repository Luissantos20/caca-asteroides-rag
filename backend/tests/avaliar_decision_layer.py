"""
╔══════════════════════════════════════════════════════════════════════╗
║         AVALIADOR DECISION LAYER — Caça Asteroides MCTI 2026        ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  O QUE ESSE SCRIPT FAZ:                                              ║
║                                                                      ║
║  A decision layer tem 3 parâmetros a calibrar:                       ║
║    threshold    → score mínimo do rank 1 pra aceitar a query         ║
║    gap_threshold → separação mínima entre rank 1 e rank 2            ║
║    min_relevant → quantos chunks >= relevance_cutoff precisam        ║
║                   estar nos top 3                                    ║
║    relevance_cutoff → nota de corte pra "chunk relevante"            ║
║                                                                      ║
║  PROBLEMA COM threshold:                                             ║
║    Score min-max SEMPRE gera score 1.0 pra o rank 1 — a regra 1     ║
║    (top_score < threshold) nunca filtra nada com threshold < 1.0.    ║
║    A regra real de qualidade é o gap entre rank 1 e rank 2.          ║
║    Mas mantemos o threshold como proteção de borda (ex: 0.0).        ║
║                                                                      ║
║  MÉTRICAS:                                                           ║
║    TPR  → True Positive Rate: queries IN-SCOPE que passaram          ║
║    TNR  → True Negative Rate: queries OUT-OF-SCOPE que foram         ║
║            bloqueadas (quanto maior, melhor pra evitar alucinação)   ║
║    F1   → harmônica de precisão e recall balanceada                  ║
║    Precisão → das que aceitamos, quantas são realmente in-scope?     ║
║                                                                      ║
║  Como usar:                                                          ║
║    python avaliar_decision_layer.py              → varredura padrão  ║
║    python avaliar_decision_layer.py --melhor     → só o melhor combo ║
║    python avaliar_decision_layer.py --detalhe    → erros por query   ║
║    python avaliar_decision_layer.py --salvar     → salva JSON        ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os
import json
import argparse
import itertools
from dotenv import load_dotenv
import chromadb
from chromadb.config import Settings
from openai import OpenAI
from services.retrieval import retrieve
from services.decision import should_answer

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROMA_PATH = os.path.join(BASE_DIR, "chroma_db")

client_openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
chroma_client = chromadb.Client(Settings(persist_directory=CHROMA_PATH, is_persistent=True))
collection = chroma_client.get_collection(name="caca_asteroides")


# ══════════════════════════════════════════════════════════════════════
# SEÇÃO 1 — QUERIES DE TESTE
#
# IN_SCOPE    → o sistema DEVE responder (devem passar pela decision layer)
# OUT_OF_SCOPE → o sistema NÃO deve responder (devem ser bloqueadas)
#
# As queries in-scope são um subconjunto variado do gabarito do
# avaliar_rag_v2: incluem todos os tipos (direta, negacao, tecnica,
# glossario, processo, problema, proibicao, suporte, conceito, prazo).
#
# As queries out-of-scope incluem as do gabarito original + novas que
# testam robustez: astronomia geral, hardware, legislação externa, etc.
# ══════════════════════════════════════════════════════════════════════

IN_SCOPE = [
    # direta
    "o que é o caça asteroides",
    "quantos asteroides ja foram descobertos pelo iasc",
    "quando as imagens ficam disponíveis",
    "precisa pagar alguma coisa pra participar?",
    "qual universidade coordena o programa",
    "qual o primeiro passo pra participar",
    "como faço login na plataforma",
    "todo mundo ganha certificado?",
    "como pego o certificado",
    "o que precisa pra ganhar a medalha",
    "quem pode participar do programa",
    "quantas pessoas precisa ter na equipe",
    "como faço a inscrição",
    "quais sao as datas das campanhas de 2026",
    "o treinamento é obrigatório?",
    "quando é o treinamento?",
    "posso participar de mais de uma campanha?",
    # negacao
    "o programa funciona no linux?",
    "o astrometrica funciona no mac?",
    "nao encontrei nenhum objeto, preciso mandar alguma coisa?",
    "posso trocar um integrante no meio da campanha",
    "posso abreviar o nome na inscrição",
    "posso ser eliminado do programa?",
    "dá pra ganhar medalha sem detectar nada?",
    "preciso detectar asteroide pra ter certificado?",
    "posso mandar o relatório por email?",
    "posso estar em duas equipes ao mesmo tempo?",
    "posso participar sozinho sem equipe?",
    # tecnica
    "o astrometrica funciona em que sistema",
    "o que é um MBA",
    "o que é o arquivo ps1.cfg",
    "como sei se o que encontrei é asteroide de verdade ou falso",
    "deu Reference Star Match Error, o que faço",
    "o que é o reset files",
    "precisa medir o objeto nas 4 imagens?",
    "o que é o data reduction no astrometrica",
    "o que é o known object overlay",
    # processo
    "como faço a varredura das imagens",
    "como assino o termo eletronicamente",
    "como gero o relatório mpc no astrometrica",
    "como faço o download dos image sets",
    "como nomeio um objeto desconhecido que encontrei",
    # problema
    "não recebi e-mail do iasc, o que faço",
    "coloquei o nome errado na inscrição, consigo corrigir no certificado?",
    # glossario
    "o que é blink comparison",
    "o que é o MPC",
    "o que é um NEO ou TNO",
    "o que é uma true signature",
    "o que é uma false signature",
    "o que é a team page do iasc",
    # suporte
    "onde tiro duvida durante a campanha",
    "onde acho suporte tecnico pro astrometrica",
    "onde encontro ajuda técnica para a campanha",
    # proibicao
    "o lider pode cobrar os alunos pelo treinamento?",
    "alguem ta cobrando pelo treinamento, isso é certo?",
    "posso usar o logo da nasa nos meus posts?",
    # prazo / envio
    "quanto tempo tenho pra enviar os termos",
    "onde envio os documentos de inscrição",
    "como envio o relatório mpc",
    # conceito / ciencia
    "o que é ciencia cidadã",
    "como funciona a detecção de asteroides no programa",
    # informalidades
    "isso aqui é parceiro da nasa?",
    "meu filho tem 8 anos, pode participar?",
    "preciso instalar alguma coisa antes da campanha",
    "tem grupo de whatsapp?",
    "tem algum instagram do programa",
    "tem canal no youtube do programa?",
    "o certificado tem validade nacional?",
    "posso participar morando fora do brasil?",
    "preciso saber astronomia pra participar?",
]

OUT_OF_SCOPE = [
    # astronomia geral (não tem nada a ver com o programa)
    "como funciona um buraco negro",
    "qual o melhor telescópio pra comprar",
    "o que é astronomia",
    "como me tornar astrônomo profissional",
    "qual planeta fica mais perto do sol",
    # hardware / equipamentos
    "qual processador devo comprar pra rodar o astrometrica",
    "que tipo de câmera uso pra fotografar asteroides",
    "preciso de um telescópio para participar?",
    # outras plataformas / programas
    "como instalo o python",
    "como uso o stellarium",
    "como me cadastro no nasa eyes",
    # legislação / juridico geral
    "o que é lei de direitos autorais no brasil",
    "como funciona a patente de uma descoberta cientifica",
    # finanças / bolsas
    "tem bolsa de pesquisa disponível pelo cnpq",
    "posso receber remuneração por descobrir um asteroide",
    # temas totalmente alheios
    "qual a melhor receita de bolo de cenoura",
    "como funciona o imposto de renda",
    "me recomenda um filme de ficção científica",
    "o que é machine learning",
]


# ══════════════════════════════════════════════════════════════════════
# SEÇÃO 2 — RETRIEVAL (igual ao retrieval.py do projeto)
# ══════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════
# SEÇÃO 3 — DECISION LAYER (should_answer decision.py)
# ══════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════
# SEÇÃO 4 — CACHE DE RESULTADOS DE RETRIEVAL
#
# Recuperar embeddings tem custo. Como a varredura testa muitas
# combinações de parâmetros com as mesmas queries, cachamos os
# resultados brutos do retrieval e apenas re-aplicamos a decision layer.
# ══════════════════════════════════════════════════════════════════════

def build_cache(verbose=True) -> dict:
    """
    Faz o retrieval de todas as queries (in-scope + out-of-scope)
    e retorna um dict {query: resultados}.
    """
    cache = {}
    todas = [(q, True) for q in IN_SCOPE] + [(q, False) for q in OUT_OF_SCOPE]

    if verbose:
        print(f"\n  Recuperando embeddings para {len(todas)} queries...")

    for i, (query, _) in enumerate(todas, 1):
        cache[query] = retrieve(query)
        if verbose and i % 10 == 0:
            print(f"    {i}/{len(todas)} concluídas")

    if verbose:
        print(f"    {len(todas)}/{len(todas)} concluídas\n")

    return cache


# ══════════════════════════════════════════════════════════════════════
# SEÇÃO 5 — AVALIAÇÃO COM PARÂMETROS FIXOS
# ══════════════════════════════════════════════════════════════════════

def avaliar_params(cache: dict,
                   threshold: float,
                   gap_threshold: float,
                   min_relevant: int,
                   relevance_cutoff: float) -> dict:
    """
    Avalia a decision layer com os parâmetros dados usando o cache.

    Retorna métricas e lista de erros para diagnóstico.
    """
    tp = fp = tn = fn = 0
    erros = []  # (query, esperado, obtido, top_score, gap, n_relevant)

    for query in IN_SCOPE:
        results = cache[query]
        top_distance = results[0]["distance"]
        decision = should_answer(results, threshold, gap_threshold,
                                 min_relevant, relevance_cutoff)
        if decision:
            tp += 1
        else:
            fn += 1
            gap = (results[0]["score"] - results[1]["score"]
                   if len(results) > 1 else None)
            n_rel = sum(1 for r in results[:3] if r["score"] >= relevance_cutoff)
            erros.append({
                "query": query,
                "esperado": "ACEITAR",
                "obtido": "BLOQUEAR",
                "top_score": round(results[0]["score"], 4) if results else None,
                "gap": round(gap, 4) if gap is not None else None,
                "n_relevantes_top3": n_rel,
                "top_distance": round(results[0]["distance"], 4)
            })

    for query in OUT_OF_SCOPE:
        results = cache[query]
        decision = should_answer(results, threshold, gap_threshold,
                                 min_relevant, relevance_cutoff)
        if decision:
            fp += 1
            gap = (results[0]["score"] - results[1]["score"]
                   if len(results) > 1 else None)
            n_rel = sum(1 for r in results[:3] if r["score"] >= relevance_cutoff)
            erros.append({
                "query": query,
                "esperado": "BLOQUEAR",
                "obtido": "ACEITAR",
                "top_score": round(results[0]["score"], 4) if results else None,
                "gap": round(gap, 4) if gap is not None else None,
                "n_relevantes_top3": n_rel,
                "top_distance": round(results[0]["distance"], 4)
            })
        else:
            tn += 1

    total_pos = tp + fn  # in-scope
    total_neg = tn + fp  # out-of-scope

    tpr = tp / total_pos if total_pos else 0.0   # sensibilidade
    tnr = tn / total_neg if total_neg else 0.0   # especificidade
    precisao = tp / (tp + fp) if (tp + fp) else 0.0
    f1 = (2 * precisao * tpr / (precisao + tpr)) if (precisao + tpr) else 0.0
    # F-beta com beta=0.4: penaliza mais falsos positivos (aceitar out-of-scope)
    beta = 0.4
    f_beta = ((1 + beta**2) * precisao * tpr /
              ((beta**2 * precisao) + tpr)) if (precisao + tpr) else 0.0

    return {
        "threshold":        threshold,
        "gap_threshold":    gap_threshold,
        "min_relevant":     min_relevant,
        "relevance_cutoff": relevance_cutoff,
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "tpr":       round(tpr, 4),
        "tnr":       round(tnr, 4),
        "precisao":  round(precisao, 4),
        "f1":        round(f1, 4),
        "f_beta":    round(f_beta, 4),
        "erros":     erros,
    }


# ══════════════════════════════════════════════════════════════════════
# SEÇÃO 6 — VARREDURA DE PARÂMETROS
#
# Por que varrer esses intervalos?
#
#   threshold: irrelevante para rank 1 (score min-max é sempre 1.0),
#     mas 0.0 é o valor funcional correto — deixa a filtragem pro gap.
#     Incluímos 0.0 e 0.5 só pra confirmar isso empiricamente.
#
#   gap_threshold: a regra mais importante. Um gap baixo (0.05) aceita
#     queries ambíguas; um gap alto (0.35+) bloqueia demais as in-scope.
#     Faixa útil: 0.05 a 0.40.
#
#   min_relevant: exige múltiplos chunks relevantes nos top 3.
#     min=1 é frouxo (qualquer resultado passa); min=3 é duro demais
#     (muitas queries legítimas têm só 1 chunk excelente e 2 mediocres).
#
#   relevance_cutoff: define o que conta como "chunk relevante" para
#     min_relevant. Com scores min-max, 0.3 é moderado; 0.6 é exigente.
#
# ══════════════════════════════════════════════════════════════════════

GRADE_THRESHOLD        = [0.0]  # pode ignorar threshold

GRADE_GAP              = [0.18, 0.2, 0.22]

GRADE_MIN_RELEVANT     = [1, 2]

GRADE_RELEVANCE_CUTOFF = [0.4, 0.5, 0.6]


def varrer(cache: dict, verbose=True) -> list:
    """
    Testa todas as combinações de parâmetros e retorna lista de métricas
    ordenada por F-beta decrescente.
    """
    combos = list(itertools.product(
        GRADE_THRESHOLD,
        GRADE_GAP,
        GRADE_MIN_RELEVANT,
        GRADE_RELEVANCE_CUTOFF,
    ))

    if verbose:
        print(f"\n  Varrendo {len(combos)} combinações de parâmetros...")
        print("  (isso não faz chamadas à API — usa o cache)\n")

    resultados = []
    for thr, gap, minr, cutoff in combos:
        m = avaliar_params(cache, thr, gap, minr, cutoff)
        resultados.append(m)

    resultados.sort(key=lambda x: x["f_beta"], reverse=True)

    if verbose:
        print(f"  {len(combos)}/{len(combos)} combinações testadas.\n")

    return resultados


# ══════════════════════════════════════════════════════════════════════
# SEÇÃO 7 — IMPRESSÃO DE RESULTADOS
# ══════════════════════════════════════════════════════════════════════

def imprimir_cabecalho_tabela():
    print("═" * 100)
    print(f"  {'thr':>5}  {'gap':>5}  {'min_rel':>7}  {'cutoff':>6}"
          f"  {'TPR':>6}  {'TNR':>6}  {'Precisão':>8}  {'F1':>6}  {'F-β(0.4)':>9}"
          f"  {'TP':>4}  {'FP':>4}  {'TN':>4}  {'FN':>4}")
    print("─" * 100)


def imprimir_linha(m: dict, marcador: str = ""):
    print(f"  {m['threshold']:>5.2f}  {m['gap_threshold']:>5.2f}"
          f"  {m['min_relevant']:>7}  {m['relevance_cutoff']:>6.2f}"
          f"  {m['tpr']:>6.1%}  {m['tnr']:>6.1%}  {m['precisao']:>8.1%}"
          f"  {m['f1']:>6.3f}  {m['f_beta']:>9.3f}"
          f"  {m['tp']:>4}  {m['fp']:>4}  {m['tn']:>4}  {m['fn']:>4}"
          f"  {marcador}")


def imprimir_erros(m: dict):
    falsos_neg = [e for e in m["erros"] if e["esperado"] == "ACEITAR"]
    falsos_pos = [e for e in m["erros"] if e["esperado"] == "BLOQUEAR"]

    print(f"\n  ❌ FALSOS NEGATIVOS (in-scope bloqueadas) — {len(falsos_neg)} queries")
    print("  Essas queries deveriam ser respondidas mas foram rejeitadas.\n")
    for e in falsos_neg:
        print(f"    dist={e.get('top_distance')}  gap={e['gap']}  n_rel={e['n_relevantes_top3']}  '{e['query'][:60]}'")

    print(f"\n  ⚠️  FALSOS POSITIVOS (out-of-scope aceitas) — {len(falsos_pos)} queries")
    print("  Essas queries são fora do escopo mas o sistema quis responder.\n")
    for e in falsos_pos:
        print(f"    dist={e.get('top_distance')}  gap={e['gap']}  n_rel={e['n_relevantes_top3']}  '{e['query'][:60]}'")


def imprimir_diagnostico(m: dict):
    tpr = m["tpr"]
    tnr = m["tnr"]
    fn  = m["fn"]
    fp  = m["fp"]

    print("\n" + "─" * 68)

    if tpr >= 0.90:
        print("  ✅ TPR EXCELENTE — sistema responde quase todas as queries legítimas")
    elif tpr >= 0.75:
        print("  🟡 TPR BOA — ~25% das queries legítimas são bloqueadas sem motivo")
    else:
        print("  ❌ TPR FRACA — sistema rejeita muitas queries que deveria responder")

    if tnr >= 0.85:
        print("  ✅ TNR EXCELENTE — system bloqueia quase toda query fora do escopo")
    elif tnr >= 0.65:
        print("  🟡 TNR MODERADA — algumas queries fora do escopo passam")
    else:
        print("  ❌ TNR FRACA — muitas queries fora do escopo passam (risco de alucinação)")

    if fn > 0:
        print(f"\n  ↳ {fn} in-scope bloqueadas → sinal de gap_threshold alto ou")
        print( "    min_relevant alto demais para o corpus atual")
    if fp > 0:
        print(f"\n  ↳ {fp} out-of-scope aceitas → sinal de gap_threshold baixo ou")
        print( "    min_relevant muito permissivo")

    print("─" * 68 + "\n")


def imprimir_top_n(resultados: list, n: int = 20, detalhe: bool = False):
    print(f"\n{'═' * 100}")
    print(f"  TOP {n} COMBINAÇÕES — ordenadas por F-β(0.4)")
    print(f"  F-β com β=0.4 penaliza mais falsos positivos (aceitar queries fora do escopo)")
    print(f"  TPR = sensibilidade (cobertura das in-scope)")
    print(f"  TNR = especificidade (rejeição das out-of-scope)")
    print(f"  Total in-scope: {len(IN_SCOPE)}  |  Total out-of-scope: {len(OUT_OF_SCOPE)}")
    imprimir_cabecalho_tabela()

    melhor = resultados[0]
    for i, m in enumerate(resultados[:n]):
        marcador = "← MELHOR" if i == 0 else ""
        imprimir_linha(m, marcador)

    print("═" * 100)
    print("\n  ══ MELHOR CONFIGURAÇÃO ══")
    print(f"  gap_threshold    = {melhor['gap_threshold']}")
    print(f"  min_relevant     = {melhor['min_relevant']}")
    print(f"  relevance_cutoff = {melhor['relevance_cutoff']}")
    print(f"  threshold        = {melhor['threshold']}  (regra 1 — quase sempre inerte com min-max)")
    print(f"\n  TPR      = {melhor['tpr']:.1%}   ({melhor['tp']}/{len(IN_SCOPE)} in-scope aceitas)")
    print(f"  TNR      = {melhor['tnr']:.1%}   ({melhor['tn']}/{len(OUT_OF_SCOPE)} out-of-scope bloqueadas)")
    print(f"  Precisão = {melhor['precisao']:.1%}")
    print(f"  F1       = {melhor['f1']:.3f}")
    print(f"  F-β(0.4) = {melhor['f_beta']:.3f}")
    imprimir_diagnostico(melhor)

    if detalhe:
        imprimir_erros(melhor)


# ══════════════════════════════════════════════════════════════════════
# SEÇÃO 8 — ANÁLISE DE DISTRIBUIÇÃO DOS GAPS
#
# Antes de varrer, é útil ver ONDE os gaps se concentram nas queries
# in-scope e out-of-scope. Se os dois conjuntos tiverem distribuições
# sobrepostas, nenhum gap_threshold vai separar bem — isso indica que
# a decision layer precisa de outra feature (ex: distância absoluta).
# ══════════════════════════════════════════════════════════════════════

def analisar_distribuicao(cache: dict):
    print("\n" + "═" * 68)
    print("  DISTRIBUIÇÃO DOS GAPS (rank1_score - rank2_score)")
    print("═" * 68)

    def stats(valores):
        v = sorted(valores)
        n = len(v)
        media = sum(v) / n
        p25 = v[n // 4]
        p50 = v[n // 2]
        p75 = v[3 * n // 4]
        min_v, max_v = v[0], v[-1]
        return media, p25, p50, p75, min_v, max_v

    gaps_in  = []
    gaps_out = []

    for q in IN_SCOPE:
        r = cache[q]
        if len(r) > 1:
            gaps_in.append(r[0]["score"] - r[1]["score"])

    for q in OUT_OF_SCOPE:
        r = cache[q]
        if len(r) > 1:
            gaps_out.append(r[0]["score"] - r[1]["score"])

    def fmt_hist(valores, bins=10):
        mn, mx = min(valores), max(valores)
        step = (mx - mn) / bins if mx > mn else 0.1
        buckets = [0] * bins
        for v in valores:
            idx = min(int((v - mn) / step), bins - 1)
            buckets[idx] += 1
        max_b = max(buckets)
        lines = []
        for i, b in enumerate(buckets):
            lo = mn + i * step
            hi = lo + step
            bar = "█" * int(b / max_b * 30) if max_b else ""
            lines.append(f"    [{lo:.3f}-{hi:.3f}] {bar} ({b})")
        return "\n".join(lines)

    print(f"\n  IN-SCOPE  (n={len(gaps_in)}):")
    m, p25, p50, p75, mn, mx = stats(gaps_in)
    print(f"    min={mn:.3f}  p25={p25:.3f}  mediana={p50:.3f}  "
          f"p75={p75:.3f}  max={mx:.3f}  média={m:.3f}")
    print(fmt_hist(gaps_in))

    print(f"\n  OUT-OF-SCOPE  (n={len(gaps_out)}):")
    m, p25, p50, p75, mn, mx = stats(gaps_out)
    print(f"    min={mn:.3f}  p25={p25:.3f}  mediana={p50:.3f}  "
          f"p75={p75:.3f}  max={mx:.3f}  média={m:.3f}")
    print(fmt_hist(gaps_out))

    # Sobreposição: quantas in-scope têm gap MENOR que a mediana out-of-scope?
    mediana_out = sorted(gaps_out)[len(gaps_out) // 2]
    sobreposicao = sum(1 for g in gaps_in if g < mediana_out)
    print(f"\n  Sobreposição: {sobreposicao}/{len(gaps_in)} queries in-scope têm")
    print(f"  gap < mediana out-of-scope ({mediana_out:.3f})")
    print(f"  → Se alto, gap sozinho não separa bem — considere feature adicional.\n")


# ══════════════════════════════════════════════════════════════════════
# SEÇÃO 9 — SALVAR RESULTADOS
# ══════════════════════════════════════════════════════════════════════

def salvar(resultados: list, caminho: str = "resultados_decision_layer.json"):
    exportar = []
    for m in resultados:
        entry = {k: v for k, v in m.items() if k != "erros"}
        entry["n_erros"] = len(m["erros"])
        exportar.append(entry)

    melhor = {k: v for k, v in resultados[0].items()}  # inclui erros do melhor
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump({"melhor": melhor, "todos": exportar}, f,
                  ensure_ascii=False, indent=2)
    print(f"  💾 Resultados salvos em: {caminho}\n")


# ══════════════════════════════════════════════════════════════════════
# SEÇÃO 10 — MAIN
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Avaliador da Decision Layer — Caça Asteroides",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python avaliar_decision_layer.py                 varredura completa + top 20
  python avaliar_decision_layer.py --melhor        só a melhor config + diagnóstico
  python avaliar_decision_layer.py --detalhe       top 20 + erros do melhor
  python avaliar_decision_layer.py --distribuicao  histogramas de gap antes de varrer
  python avaliar_decision_layer.py --salvar        salva JSON
  python avaliar_decision_layer.py --top 10        exibe top 10 (default: 20)
        """
    )
    parser.add_argument("--melhor",       action="store_true",
                        help="Mostra só o melhor resultado")
    parser.add_argument("--detalhe",      action="store_true",
                        help="Mostra erros detalhados do melhor resultado")
    parser.add_argument("--distribuicao", action="store_true",
                        help="Imprime histogramas de gap antes da varredura")
    parser.add_argument("--salvar",       action="store_true",
                        help="Salva resultados em JSON")
    parser.add_argument("--top",          type=int, default=20,
                        help="Quantas configurações exibir (default: 20)")
    args = parser.parse_args()

    cache = build_cache(verbose=True)

    if args.distribuicao:
        analisar_distribuicao(cache)

    resultados = varrer(cache, verbose=True)

    if args.melhor:
        melhor = resultados[0]
        print("\n  ══ MELHOR CONFIGURAÇÃO ══")
        imprimir_cabecalho_tabela()
        imprimir_linha(melhor, "← MELHOR")
        print("═" * 100)
        imprimir_diagnostico(melhor)
        if args.detalhe:
            imprimir_erros(melhor)
    else:
        imprimir_top_n(resultados, n=args.top, detalhe=args.detalhe)

    if args.salvar:
        salvar(resultados)