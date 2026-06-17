"""
═══════════════════════════════════════════════════════════════════════
  LOAD TEST — Caça Asteroides RAG
═══════════════════════════════════════════════════════════════════════

O que ele faz:
  Dispara requisições concorrentes contra o endpoint /chat, CONSUMINDO o
  stream SSE até o fim (igual a um usuário real), e mede como o sistema
  se comporta sob carga — em RAMPA de concorrência (10, 25, 50, 75, 100).

Por que rampa: "aguenta 100 simultâneos?" só faz sentido se você vê ONDE
  começa a degradar. Um número solto não ensina nada; a curva ensina.

O que mede, por nível de concorrência:
  - TTFT (time to first token): quanto o usuário espera até a resposta
    COMEÇAR a aparecer. É o que ele "sente".
  - Total: do envio até o stream terminar.
  - Taxa de sucesso e quebra de desfechos (ok / rate_limited / http_error
    / stream_error / timeout).
  Percentis p50/p95/p99: p95 = "os 5% piores"; é o que importa num evento
  (a pessoa azarada da fila), não a média.

PRÉ-REQUISITOS:
  pip install httpx
  E desligar o rate limit no alvo (senão você mede o seu próprio limiter):
    - Local: suba o backend com  RATE_LIMIT_ENABLED=false
    - (requer o toggle por env no api/core/limiter.py)

USO:
  # Local primeiro (seguro, grátis pra calibrar):
  python load_test.py --url http://localhost:8010/chat

  # Níveis customizados:
  python load_test.py --url http://localhost:8010/chat --levels 5,10,20,40

  # Disparo controlado na produção (UMA vez, níveis menores):
  python load_test.py --url https://SEU-BACKEND.up.railway.app/chat --levels 10,25,50

ATENÇÃO PRODUÇÃO: cada requisição gasta API da OpenAI (embedding+geração).
  100 concorrentes × N níveis = algumas centenas de chamadas. Barato, mas
  não é zero. E NÃO martele a produção repetidamente — um disparo controlado.
"""

import os
import sys
import json
import time
import asyncio
import argparse
import statistics
from datetime import datetime

try:
    import httpx
except ImportError:
    print("ERRO: httpx não instalado. Rode:  pip install httpx")
    sys.exit(1)


# ── Perguntas realistas (variadas, pra não medir sempre o mesmo caminho) ──
# Mistura temas e formulações reais; evita cache trivial e exercita chunks
# diferentes (inscrição, software, detecção, faq...).
QUESTIONS = [
    "como participo?",
    "quero me inscrever, como faço?",
    "quanto custa pra participar?",
    "criança pode participar?",
    "preciso saber astronomia?",
    "como instalo o astrometrica?",
    "deu runtime error no astrometrica",
    "como gero o relatório MPC?",
    "o que é reset files?",
    "como sei se é mesmo um asteroide?",
    "o que é blink comparison?",
    "o certificado tem validade?",
    "qual a diferença entre certificado e medalha?",
    "o que é designação provisória?",
    "quem são os parceiros do programa?",
    "o que é o caça asteroides?",
]


async def uma_requisicao(client: httpx.AsyncClient, url: str, pergunta: str,
                         timeout: float) -> dict:
    """Faz UMA requisição, consome o SSE até o fim, e devolve as métricas.

    Mede dois tempos a partir do envio:
      - ttft: instante do PRIMEIRO token de conteúdo (resposta começou)
      - total: instante em que o stream terminou
    Classifica o desfecho pra você saber NÃO só 'falhou' mas COMO falhou.
    """
    payload = {"message": pergunta, "history": []}
    t0 = time.perf_counter()
    ttft = None
    n_tokens = 0
    outcome = "ok"

    try:
        async with client.stream("POST", url, json=payload,
                                 timeout=timeout) as resp:
            status = resp.status_code

            if status == 429:
                await resp.aread()
                return _registro("rate_limited", t0, None, 0, pergunta, status)
            if status != 200:
                await resp.aread()
                return _registro("http_error", t0, None, 0, pergunta, status)

            # Stream OK: lê linha a linha o SSE ("data: {json}\n\n")
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                try:
                    event = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue

                etype = event.get("type")
                if etype == "token":
                    if ttft is None:
                        ttft = time.perf_counter() - t0  # primeiro token!
                    n_tokens += 1
                elif etype == "error":
                    outcome = "stream_error"
                elif etype == "metadata":
                    # decision negou → não virá token; é um desfecho válido
                    if event.get("should_answer") is False:
                        outcome = "blocked"
                elif etype == "done":
                    break

        total = time.perf_counter() - t0
        # Se não veio token e não foi explicitamente bloqueado/erro → refused
        if outcome == "ok" and n_tokens == 0:
            outcome = "no_tokens"
        return _registro(outcome, t0, ttft, n_tokens, pergunta, 200, total)

    except (httpx.TimeoutException, asyncio.TimeoutError):
        return _registro("timeout", t0, None, 0, pergunta, None)
    except Exception as e:
        r = _registro("exception", t0, None, 0, pergunta, None)
        r["error"] = f"{type(e).__name__}: {e}"
        return r


def _registro(outcome, t0, ttft, n_tokens, pergunta, status, total=None):
    if total is None:
        total = time.perf_counter() - t0
    return {
        "outcome": outcome,
        "ttft_s": round(ttft, 3) if ttft is not None else None,
        "total_s": round(total, 3),
        "n_tokens": n_tokens,
        "status": status,
        "pergunta": pergunta,
    }


async def rodar_nivel(url: str, n: int, timeout: float) -> list:
    """Dispara N requisições SIMULTÂNEAS (pior caso) e espera todas."""
    # Limits generosos pra o CLIENTE não virar o gargalo (senão você mede
    # a fila do httpx, não a do servidor).
    limits = httpx.Limits(max_connections=n + 10,
                          max_keepalive_connections=n + 10)
    async with httpx.AsyncClient(limits=limits) as client:
        tarefas = [
            uma_requisicao(client, url, QUESTIONS[i % len(QUESTIONS)], timeout)
            for i in range(n)
        ]
        return await asyncio.gather(*tarefas)


def _pct(valores, p):
    if not valores:
        return None
    valores = sorted(valores)
    k = (len(valores) - 1) * (p / 100)
    f = int(k)
    c = min(f + 1, len(valores) - 1)
    if f == c:
        return round(valores[f], 2)
    return round(valores[f] + (valores[c] - valores[f]) * (k - f), 2)


def resumir_nivel(n, registros, wall_s):
    from collections import Counter
    outcomes = Counter(r["outcome"] for r in registros)
    ok = [r for r in registros if r["outcome"] == "ok"]
    ttfts = [r["ttft_s"] for r in ok if r["ttft_s"] is not None]
    totais = [r["total_s"] for r in ok]
    n_ok = len(ok)

    print(f"\n  ── Concorrência {n} ──  (parede: {wall_s:.1f}s)")
    print(f"     sucesso: {n_ok}/{n} ({100*n_ok//n}%)"
          f"   throughput: {n_ok / wall_s:.1f} req/s")
    if ttfts:
        print(f"     TTFT  (1º token): p50={_pct(ttfts,50)}s  "
              f"p95={_pct(ttfts,95)}s  p99={_pct(ttfts,99)}s")
    if totais:
        print(f"     Total (completo): p50={_pct(totais,50)}s  "
              f"p95={_pct(totais,95)}s  p99={_pct(totais,99)}s  "
              f"max={max(totais):.1f}s")
    nao_ok = {k: v for k, v in outcomes.items() if k != "ok"}
    if nao_ok:
        print(f"     ⚠️  não-ok: " +
              "  ".join(f"{k}={v}" for k, v in nao_ok.items()))
    return {
        "n": n, "wall_s": round(wall_s, 1), "ok": n_ok,
        "outcomes": dict(outcomes),
        "ttft_p50": _pct(ttfts, 50), "ttft_p95": _pct(ttfts, 95),
        "total_p50": _pct(totais, 50), "total_p95": _pct(totais, 95),
        "total_p99": _pct(totais, 99),
        "total_max": round(max(totais), 2) if totais else None,
        "throughput": round(n_ok / wall_s, 2),
    }


async def main():
    ap = argparse.ArgumentParser(description="Load test — Caça Asteroides")
    ap.add_argument("--url", required=True, help="URL do /chat (local ou prod)")
    ap.add_argument("--levels", default="10,25,50,75,100",
                    help="Níveis de concorrência (vírgula). Ex: 10,25,50")
    ap.add_argument("--timeout", type=float, default=90,
                    help="Timeout por requisição (s)")
    ap.add_argument("--pause", type=float, default=5,
                    help="Pausa entre níveis (s) — deixa o servidor respirar")
    ap.add_argument("--out", default=None, help="Arquivo JSON de saída")
    args = ap.parse_args()

    niveis = [int(x) for x in args.levels.split(",")]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = args.out or f"loadtest_{stamp}.json"

    print("═" * 64)
    print(f"  LOAD TEST  →  {args.url}")
    print(f"  Níveis: {niveis}   timeout: {args.timeout}s")
    print("═" * 64)

    resumos = []
    brutos = {}
    for n in niveis:
        t = time.perf_counter()
        registros = await rodar_nivel(args.url, n, args.timeout)
        wall = time.perf_counter() - t
        resumos.append(resumir_nivel(n, registros, wall))
        brutos[str(n)] = registros
        if n != niveis[-1]:
            await asyncio.sleep(args.pause)

    with open(out, "w", encoding="utf-8") as f:
        json.dump({"url": args.url, "ts": stamp,
                   "resumos": resumos, "brutos": brutos},
                  f, ensure_ascii=False, indent=2)

    print("\n" + "═" * 64)
    print("  LEITURA RÁPIDA")
    print("═" * 64)
    print("  • TTFT subindo = pessoas esperando MAIS pra resposta começar.")
    print("  • Total p95 é o que importa: o azarado da fila no evento.")
    print("  • rate_limited aparecendo = rate limit não foi desligado.")
    print("  • timeout/http_error subindo num nível = perto do teto real.")
    print(f"\n  💾 Bruto salvo em: {out}\n")


if __name__ == "__main__":
    asyncio.run(main())
