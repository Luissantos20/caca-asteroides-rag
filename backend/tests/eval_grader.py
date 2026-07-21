"""
eval_grader.py — Mede o GRADER (services.grader.grade_answerability) contra o
dataset rotulado (dataset.py) E DIAGNOSTICA cada erro.

Roda retrieve() + grader REAIS (precisa OPENAI_API_KEY). ~146 chamadas, ~1-2 min.

IMPORTANTE: rode com a normalize_scores NOVA (absoluta, cos = 1 - d/2) ativa.
O grader filtra chunks por score >= 0.40, e isso só significa "cos >= 0.40" com
a normalização absoluta. Com a min-max antiga a seleção sai errada.

Mede:
  TPR (das IN-SCOPE, quantas PASSAM): queremos ~100% (o chunk certo sempre está
     lá — SC@3=100%). Recusar uma dessas é o erro CARO.
  TNR (das ADVERSARIAIS, quantas ele BARRA): é o que o piso não faz.

E em cada ERRO, mostra o que o grader REALMENTE viu, separando dois diagnósticos
diferentes num falso-negativo in-scope:
  (a) valido PRESENTE no contexto mas grader recusou -> grader estrito demais
      => ajustar o PROMPT.
  (b) valido AUSENTE do contexto (foi filtrado/não recuperado) -> ajustar o
      RETRIEVAL / o floor de contexto, NÃO o prompt.

Rodar de dentro de backend/:   python tests/eval_grader.py
"""

import os
import re
import sys
import asyncio
import logging

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
sys.path.insert(0, BACKEND)   # para 'services'
sys.path.insert(0, HERE)      # para 'dataset'

# Silencia o ruído do retrieve, mas deixa o logger do grader em INFO e captura
# suas linhas — é de lá que tiramos o 'motivo' (raciocínio) de cada julgamento.
logging.getLogger().setLevel(logging.CRITICAL)


class _Captura(logging.Handler):
    def __init__(self):
        super().__init__()
        self.linhas = []

    def emit(self, record):
        self.linhas.append(record.getMessage())


_cap = _Captura()
_glog = logging.getLogger("services.grader")
_glog.setLevel(logging.INFO)
_glog.addHandler(_cap)

from services.retrieval import retrieve
from services.grader import grade_answerability
from dataset import IN_SCOPE, ADVERSARIAL

# Mesmo filtro de contexto que o grader (e a geração) usam.
CONTEXT_SCORE_FLOOR = 0.40
TOP_K = 3


def cos(d):
    return 1.0 - d / 2.0


def top_cos(results):
    return cos(results[0]["distance"]) if results else 0.0


def _motivo():
    """Último 'motivo=' capturado do log do grader nesta chamada."""
    for l in reversed(_cap.linhas):
        m = re.search(r"motivo='(.*)'", l)
        if m:
            return m.group(1)
    return ""


def _contexto_visto(results):
    """Reproduz a seleção do grader: score>=floor, top-3."""
    return [c for c in results if c["score"] >= CONTEXT_SCORE_FLOOR][:TOP_K]


def _dump_contexto(results, validos=None):
    """Imprime os chunks que o grader viu. Retorna se um 'valido' estava lá."""
    ctx = _contexto_visto(results)
    valido_presente = False
    if not ctx:
        print("        (contexto vazio após o filtro score>=0.40)")
    for c in ctx:
        eh_valido = validos is not None and c["id"] in validos
        valido_presente = valido_presente or eh_valido
        marca = "  <- VALIDO (esperado)" if eh_valido else ""
        print(f"        {c['id']:16s} cos={cos(c['distance']):.3f}{marca}")
    return valido_presente


async def _julgar(q, i, n):
    _cap.linhas.clear()
    results = await retrieve(q, f"evalg-{i}")
    veredito = await grade_answerability(q, results, f"evalg-{i}")
    print(f"\r  julgando {i}/{n}", end="", flush=True)
    return veredito, results, _motivo()


async def bloco_in_scope():
    print("\n" + "=" * 72)
    print("  IN-SCOPE — o grader DEVE deixar passar (têm resposta na base)")
    print("  TPR = quantas passam. Recusar uma dessas = pergunta válida barrada.")
    print("=" * 72)
    n = len(IN_SCOPE)
    passou = 0
    barradas = []   # falsos negativos
    for i, (q, tipo, validos, contexto) in enumerate(IN_SCOPE, 1):
        ok, results, motivo = await _julgar(q, i, n)
        if ok:
            passou += 1
        else:
            barradas.append((q, top_cos(results), motivo, results, validos))
    print()
    print(f"\n  TPR: {passou/n:6.1%}  ({passou}/{n})")
    if barradas:
        print(f"\n  IN-SCOPE barradas por engano ({len(barradas)}):")
        for q, tc, motivo, results, validos in barradas:
            print(f"\n    cos_topo={tc:.3f}  «{q[:55]}»")
            print(f"      esperado (validos): {validos}")
            print(f"      contexto que o grader viu:")
            presente = _dump_contexto(results, validos)
            if presente:
                print("      => valido PRESENTE, grader recusou  =>  (a) ajustar o PROMPT (estrito demais)")
            else:
                print("      => valido AUSENTE do contexto        =>  (b) ajustar RETRIEVAL/floor (chunk filtrado)")
            print(f"      motivo: {motivo}")
    else:
        print("\n  Nenhuma in-scope barrada. O grader não custa recall.")
    return passou, n


async def bloco_adversarial():
    print("\n" + "=" * 72)
    print("  ADVERSARIAL — o grader DEVE barrar (tema certo, resposta ausente)")
    print("  TNR = quantas ele barra. É o trabalho que o piso não faz.")
    print("=" * 72)
    n = len(ADVERSARIAL)
    barrou = 0
    passaram = []   # falsos positivos
    for i, q in enumerate(ADVERSARIAL, 1):
        ok, results, motivo = await _julgar(q, i, n)
        if not ok:
            barrou += 1
        else:
            passaram.append((q, top_cos(results), motivo, results))
    print()
    print(f"\n  TNR: {barrou/n:6.1%}  ({barrou}/{n})")
    if passaram:
        print(f"\n  ADVERSARIAL que PASSARAM ({len(passaram)}) — risco de alucinação:")
        for q, tc, motivo, results in passaram:
            print(f"\n    cos_topo={tc:.3f}  «{q[:55]}»")
            print(f"      contexto que o grader viu:")
            _dump_contexto(results)
            print(f"      motivo: {motivo}")
    else:
        print("\n  Nenhuma adversarial passou. Contenção total.")
    return barrou, n


async def main():
    print("Rodando retrieve + grader em IN-SCOPE e ADVERSARIAL...")
    tp, n_in = await bloco_in_scope()
    tn, n_adv = await bloco_adversarial()
    print("\n" + "=" * 72)
    print("  RESUMO")
    print(f"    TPR (in-scope passam)  : {tp/n_in:6.1%}  ({tp}/{n_in})")
    print(f"    TNR (adversarial barra): {tn/n_adv:6.1%}  ({tn}/{n_adv})")
    print("=" * 72)
    print("  Leitura de cada erro:")
    print("  - (a) valido PRESENTE mas recusado  -> relaxe o PROMPT do grader.")
    print("  - (b) valido AUSENTE do contexto    -> é retrieval/floor, não prompt.")
    print("  - TPR alto é inegociável; apertar o prompt sobe TNR mas pode derrubar TPR.")
    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(main())