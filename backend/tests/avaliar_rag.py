"""
╔══════════════════════════════════════════════════════════════════════╗
║         AVALIADOR RAG v2 — Caça Asteroides MCTI 2026                ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  DIFERENÇAS EM RELAÇÃO À v1:                                         ║
║                                                                      ║
║  GABARITO REVISADO                                                   ║
║    A v1 tinha viés grave: aceitava apenas 1 chunk como correto,      ║
║    mas muitas perguntas têm 2-4 chunks que respondem com igual       ║
║    precisão (ex: Windows/macOS aparece em 3 docs; certificado em 2). ║
║    O gabarito agora usa conjuntos de "chunks válidos" — qualquer     ║
║    um deles no rank 1 conta como acerto.                             ║
║                                                                      ║
║  NOVA MÉTRICA: SET COVERAGE@3                                        ║
║    O modelo vai usar os 3 chunks recuperados para gerar a resposta.  ║
║    A métrica avalia se ao menos 1 chunk válido está nos 3 primeiros. ║
║    Isso é mais honesto do que P@1 quando o contexto é multi-chunk.   ║
║                                                                      ║
║  SCORE NORMALIZADO POR QUERY                                         ║
║    Ao invés de softmax sobre um conjunto arbitrário de candidatos,   ║
║    usamos score = 1 - (dist / max_dist_do_conjunto), mais intuitivo. ║
║                                                                      ║
║  Como usar:                                                          ║
║    python avaliar_rag_v2.py                   → avaliação padrão     ║
║    python avaliar_rag_v2.py --threshold 1.0   → testa threshold      ║
║    python avaliar_rag_v2.py --busca-threshold → qual o melhor?       ║
║    python avaliar_rag_v2.py --completo        → tudo junto           ║
║    python avaliar_rag_v2.py --completo --salvar → salva JSON         ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os
import math
import argparse
import json
from dotenv import load_dotenv
import chromadb
from chromadb.config import Settings
from openai import OpenAI
from services.retrieval import get_embedding, normalize_scores

load_dotenv()


# ══════════════════════════════════════════════════════════════════════
# SEÇÃO 1 — CONFIGURAÇÃO DE CONEXÃO
# ══════════════════════════════════════════════════════════════════════

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROMA_PATH = os.path.join(BASE_DIR, "chroma_db")

client_openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

chroma_client = chromadb.Client(
    Settings(persist_directory=CHROMA_PATH, is_persistent=True)
)
collection = chroma_client.get_collection(name="caca_asteroides")


# ══════════════════════════════════════════════════════════════════════
# SEÇÃO 2 — GABARITO REVISADO
#
# ESTRUTURA DE CADA ENTRADA:
#   (pergunta, tipo, chunks_validos_rank1, chunks_contexto_util)
#
# chunks_validos_rank1 → qualquer um desses no rank 1 = ACERTO em P@1.
#   São todos os chunks que respondem a pergunta de forma direta e
#   suficiente. A v1 listava apenas 1 como "ideal", o que era falso
#   quando 2-3 chunks cobrem o mesmo tópico com igual precisão.
#
# chunks_contexto_util → complementam a resposta mas não bastam
#   sozinhos. São relevantes para Set Coverage: se algum deles aparecer
#   nos top 3, junto com ao menos 1 válido, a geração vai ser melhor.
#
# CRITÉRIO PARA chunks_validos_rank1:
#   Um chunk entra nessa lista se, SOZINHO, permite ao LLM gerar uma
#   resposta correta e completa para a pergunta. Se precisa de outro
#   chunk para completar, vai para chunks_contexto_util.
#
# MUDANÇAS EM RELAÇÃO AO GABARITO ORIGINAL:
#   [✓] Perguntas que tinham 1 ideal → mantido se realmente só 1 chunk basta
#   [+] Perguntas onde 2+ chunks são igualmente válidos → todos incluídos
#   [~] "chunks_aceitaveis" do original virou "chunks_contexto_util"
#   [R] Entradas onde o chunk original estava errado → corrigido
# ══════════════════════════════════════════════════════════════════════

GABARITO = [

    # ──────────────────────────────────────────────────────────────────
    # DOC-01 — Visão Geral e Parceiros
    # ──────────────────────────────────────────────────────────────────

    # [+] DOC05-CHUNK-01 e DOC01-VGP-12 também respondem "o que é" com igual validade
    (
        "o que é o caça asteroides",
        "direta",
        ["DOC01-VGP-01", "DOC05-CHUNK-01", "DOC01-VGP-12"],
        ["DOC01-VGP-02"]
    ),
    # [+] DOC05-CHUNK-01 e DOC05-CHUNK-14 também falam da parceria NASA/IASC
    (
        "isso aqui é parceiro da nasa?",
        "informal",
        ["DOC01-VGP-04", "DOC05-CHUNK-01", "DOC05-CHUNK-14"],
        ["DOC01-VGP-10"]
    ),
    # [✓] Apenas DOC01-VGP-05 tem os números exatos (7000 descobertas, 97 numerados)
    (
        "quantos asteroides ja foram descobertos pelo iasc",
        "direta",
        ["DOC01-VGP-05"],
        []
    ),
    # [✓] Apenas DOC01-VGP-06 detalha Pan-STARRS e o formato das imagens
    (
        "de onde vem as imagens que a gente analisa",
        "indireta",
        ["DOC01-VGP-06"],
        []
    ),
    # [✓] Apenas DOC01-VGP-07 explica o período quarto minguante/crescente
    (
        "quando as imagens ficam disponíveis",
        "direta",
        ["DOC01-VGP-07"],
        []
    ),
    # [+] DOC05-CHUNK-23 (MPC) e DOC01-VGP-08 definem MBA com precisão
    # NOTA v3: DOC05-CHUNK-23 agora é só "MPC (Minor Planet Center)" — não define MBA.
    #          Removido. DOC01-VGP-08 é o único chunk que define MBA.
    (
        "o que é um MBA",
        "tecnica",
        ["DOC01-VGP-08"],
        ["DOC05-CHUNK-23"]
    ),
    # [+] DOC01-VGP-13 e DOC05-CHUNK-09 ambos afirmam gratuidade de forma completa
    (
        "precisa pagar alguma coisa pra participar?",
        "negacao",
        ["DOC01-VGP-13", "DOC05-CHUNK-09"],
        []
    ),
    # [+] DOC05-CHUNK-06, DOC05-CHUNK-21, DOC06-QSG-02, DOC02-FCP-14, DOC01-VGP-11
    (
        "o astrometrica funciona em que sistema",
        "tecnica",
        ["DOC05-CHUNK-06", "DOC05-CHUNK-21", "DOC06-QSG-02", "DOC02-FCP-14", "DOC01-VGP-11"],
        []
    ),
    # [+] DOC01-VGP-03 e DOC05-CHUNK-14 listam as instituições coordenadoras
    (
        "qual universidade coordena o programa",
        "direta",
        ["DOC01-VGP-03", "DOC05-CHUNK-14"],
        []
    ),
    # [+] DOC01-VGP-12 é o mais direto; DOC01-VGP-01 também define bem
    (
        "o que é ciencia cidadã",
        "conceito",
        ["DOC01-VGP-12", "DOC01-VGP-01"],
        ["DOC01-VGP-02"]
    ),

    # ──────────────────────────────────────────────────────────────────
    # DOC-02 — Fluxo Completo do Participante
    # ──────────────────────────────────────────────────────────────────

    # [+] DOC02-FCP-02 e DOC05-CHUNK-04 detalham o processo de inscrição igualmente
    (
        "qual o primeiro passo pra participar",
        "direta",
        ["DOC02-FCP-02", "DOC05-CHUNK-04"],
        ["DOC02-FCP-01"]
    ),
    # [+] DOC02-FCP-03, DOC04-LCU-02, DOC05-CHUNK-10 dão o e-mail e as instruções
    (
        "onde eu mando os documentos depois de me inscrever",
        "indireta",
        ["DOC02-FCP-03", "DOC04-LCU-02", "DOC05-CHUNK-10"],
        []
    ),
    # [+] DOC02-FCP-03 e DOC05-CHUNK-10 ambos mencionam o prazo de 15 dias
    (
        "quanto tempo tenho pra enviar os termos",
        "prazo",
        ["DOC02-FCP-03", "DOC05-CHUNK-10"],
        []
    ),
    # [✓] Apenas DOC02-FCP-04 explica o que fazer quando não chega o e-mail do IASC
    (
        "não recebi e-mail do iasc, o que faço",
        "problema",
        ["DOC02-FCP-04"],
        ["DOC04-LCU-07"]
    ),
    # [+] DOC02-FCP-05 e DOC06-QSG-19 cobrem o que instalar e praticar antes
    (
        "preciso instalar alguma coisa antes da campanha",
        "direta",
        ["DOC02-FCP-05", "DOC06-QSG-19"],
        ["DOC06-QSG-03"]
    ),
    # [+] DOC02-FCP-06 e DOC04-LCU-06 ambos explicam onde e como fazer login
    (
        "como faço login na plataforma",
        "tecnica",
        ["DOC02-FCP-06", "DOC04-LCU-06"],
        []
    ),
    # [+] DOC02-FCP-09 e DOC06-QSG-17 ambos explicam o envio pela Team Page
    (
        "como envio o relatório mpc",
        "tecnica",
        ["DOC02-FCP-09", "DOC06-QSG-17"],
        ["DOC06-QSG-20"]
    ),
    # [+] DOC02-FCP-10 e DOC06-QSG-16 ambos cobrem o relatório sem detecções
    (
        "nao encontrei nenhum objeto, preciso mandar alguma coisa?",
        "negacao",
        ["DOC02-FCP-10", "DOC06-QSG-16"],
        []
    ),
    # [+] DOC02-FCP-14, DOC05-CHUNK-21, DOC06-QSG-02, DOC01-VGP-11
    (
        "o programa funciona no linux?",
        "negacao",
        ["DOC02-FCP-14", "DOC05-CHUNK-21", "DOC06-QSG-02", "DOC01-VGP-11"],
        []
    ),
    # [+] DOC02-FCP-13, DOC03-CMD-03, DOC05-CHUNK-07
    (
        "quando posso pegar o certificado",
        "direta",
        ["DOC02-FCP-13", "DOC03-CMD-03", "DOC05-CHUNK-07"],
        []
    ),
    # [+] DOC02-FCP-11 e DOC05-CHUNK-09 proíbem cobranças; DOC01-VGP-13 também
    (
        "o lider pode cobrar os alunos pelo treinamento?",
        "proibicao",
        ["DOC02-FCP-11", "DOC05-CHUNK-09", "DOC01-VGP-13"],
        []
    ),
    # [+] DOC02-FCP-12 e DOC04-LCU-11 orientam sobre canais de dúvida
    (
        "onde tiro duvida durante a campanha",
        "suporte",
        ["DOC02-FCP-12", "DOC04-LCU-11"],
        ["DOC04-LCU-01", "DOC04-LCU-07"]
    ),

    # ──────────────────────────────────────────────────────────────────
    # DOC-03 — Certificados e Medalhas
    # ──────────────────────────────────────────────────────────────────

    # [+] DOC03-CMD-01 e DOC03-CMD-08 explicam a diferença de forma completa
    (
        "qual a diferença entre certificado e medalha",
        "direta",
        ["DOC03-CMD-01", "DOC03-CMD-08"],
        []
    ),
    # [+] DOC03-CMD-02, DOC03-CMD-08, DOC05-CHUNK-07 respondem que todos recebem
    (
        "todo mundo ganha certificado?",
        "direta",
        ["DOC03-CMD-02", "DOC03-CMD-08", "DOC05-CHUNK-07"],
        []
    ),
    # [+] DOC03-CMD-03, DOC02-FCP-13, DOC05-CHUNK-07 explicam como pegar
    (
        "como pego o certificado",
        "direta",
        ["DOC03-CMD-03", "DOC02-FCP-13", "DOC05-CHUNK-07"],
        []
    ),
    # [✓] Apenas DOC03-CMD-04 detalha o problema do nome errado
    (
        "coloquei o nome errado na inscrição, consigo corrigir no certificado?",
        "problema",
        ["DOC03-CMD-04"],
        ["DOC05-CHUNK-07"]
    ),
    # [+] DOC03-CMD-06 é o mais completo; DOC03-CMD-01 e DOC03-CMD-08 resumem
    (
        "o que precisa pra ganhar a medalha",
        "direta",
        ["DOC03-CMD-06", "DOC03-CMD-01", "DOC03-CMD-08"],
        []
    ),
    # [✓] Apenas DOC03-CMD-07 esclarece que é cerimônia presencial (não correio)
    (
        "a medalha é enviada pelo correio?",
        "indireta",
        ["DOC03-CMD-07"],
        ["DOC03-CMD-05"]
    ),
    # [+] DOC03-CMD-02 e DOC03-CMD-08 respondem que NÃO precisa detectar
    (
        "preciso detectar asteroide pra ter certificado?",
        "negacao",
        ["DOC03-CMD-02", "DOC03-CMD-08", "DOC05-CHUNK-07"],
        []
    ),
    # [+] DOC03-CMD-06 e DOC03-CMD-08 respondem que SIM precisa detectar para medalha
    (
        "dá pra ganhar medalha sem detectar nada?",
        "negacao",
        ["DOC03-CMD-06", "DOC03-CMD-08"],
        ["DOC03-CMD-01"]
    ),

    # ──────────────────────────────────────────────────────────────────
    # DOC-04 — Links e Contatos
    # ──────────────────────────────────────────────────────────────────

    # [+] DOC04-LCU-01 e DOC05-CHUNK-20 fornecem o e-mail cacaasteroidesbrasil@
    (
        "qual o email pra mandar duvida",
        "direta",
        ["DOC04-LCU-01", "DOC05-CHUNK-20"],
        ["DOC04-LCU-11"]
    ),
    # [+] DOC04-LCU-02, DOC02-FCP-03, DOC05-CHUNK-10
    (
        "onde envio os documentos de inscrição",
        "direta",
        ["DOC04-LCU-02", "DOC02-FCP-03", "DOC05-CHUNK-10"],
        []
    ),
    # [✓] Apenas DOC04-LCU-03 foca no Instagram
    (
        "tem algum instagram do programa",
        "direta",
        ["DOC04-LCU-03"],
        ["DOC04-LCU-11"]
    ),
    # [+] DOC04-LCU-08 e DOC06-QSG-03 explicam onde baixar o Astrometrica
    (
        "como baixo o astrometrica",
        "direta",
        ["DOC04-LCU-08", "DOC06-QSG-03"],
        ["DOC01-VGP-11"]
    ),
    # [+] DOC04-LCU-10 e DOC05-CHUNK-15 têm os links de inscrição por campanha
    (
        "link pra me inscrever na campanha 3",
        "direta",
        ["DOC04-LCU-10", "DOC05-CHUNK-15"],
        []
    ),
    # [+] DOC04-LCU-05 e DOC02-FCP-12 explicam o grupo de WhatsApp
    (
        "tem grupo de whatsapp?",
        "direta",
        ["DOC04-LCU-05", "DOC02-FCP-12"],
        []
    ),
    # [+] DOC04-LCU-07 e DOC04-LCU-11 orientam sobre suporte técnico do Astrometrica
    # NOTA v3: DOC06-QSG-44 também responde diretamente (novo chunk de ajuda técnica)
    (
        "onde acho suporte tecnico pro astrometrica",
        "tecnica",
        ["DOC04-LCU-07", "DOC04-LCU-11", "DOC06-QSG-44"],
        ["DOC02-FCP-12"]
    ),
    # [+] DOC04-LCU-09 e DOC05-CHUNK-19 explicam a assinatura eletrônica gov.br
    (
        "como assino o termo eletronicamente",
        "processo",
        ["DOC04-LCU-09", "DOC05-CHUNK-19"],
        ["DOC02-FCP-03"]
    ),

    # ──────────────────────────────────────────────────────────────────
    # DOC-05 — Edital
    # ──────────────────────────────────────────────────────────────────

    # [✓] DOC05-CHUNK-02 lista explicitamente todos os públicos elegíveis
    (
        "quem pode participar do programa",
        "direta",
        ["DOC05-CHUNK-02"],
        ["DOC01-VGP-01"]
    ),
    # [✓] DOC05-CHUNK-02 inclui "ensino fundamental I e II (2º ao 9º ano)"
    (
        "meu filho tem 8 anos, pode participar?",
        "direta",
        ["DOC05-CHUNK-02"],
        []
    ),
    # [✓] DOC05-CHUNK-03 tem a tabela mínimo/intermediário/máximo de membros
    (
        "quantas pessoas precisa ter na equipe",
        "direta",
        ["DOC05-CHUNK-03"],
        []
    ),
    # [✓] DOC05-CHUNK-03 menciona que membros não podem ser substituídos
    (
        "posso trocar um integrante no meio da campanha",
        "negacao",
        ["DOC05-CHUNK-03"],
        []
    ),
    # [+] DOC05-CHUNK-04 e DOC02-FCP-02 cobrem o passo a passo de inscrição
    (
        "como faço a inscrição",
        "direta",
        ["DOC05-CHUNK-04", "DOC02-FCP-02"],
        ["DOC04-LCU-10"]
    ),
    # [+] DOC05-CHUNK-04 e DOC03-CMD-04 alertam sobre nome completo sem abreviação
    (
        "posso abreviar o nome na inscrição",
        "negacao",
        ["DOC05-CHUNK-04", "DOC03-CMD-04"],
        []
    ),
    # [+] DOC05-CHUNK-05 e DOC02-FCP-15 têm as datas das 8 campanhas
    (
        "quais sao as datas das campanhas de 2026",
        "direta",
        ["DOC05-CHUNK-05", "DOC02-FCP-15"],
        []
    ),
    # [+] DOC05-CHUNK-21, DOC02-FCP-14, DOC06-QSG-02, DOC01-VGP-11
    (
        "o astrometrica funciona no mac?",
        "negacao",
        ["DOC05-CHUNK-21", "DOC02-FCP-14", "DOC06-QSG-02", "DOC01-VGP-11"],
        []
    ),
    # [+] DOC05-CHUNK-16 e DOC02-FCP-11 afirmam que o treinamento é obrigatório
    (
        "o treinamento é obrigatório?",
        "direta",
        ["DOC05-CHUNK-16", "DOC02-FCP-11"],
        []
    ),
    # [✓] DOC05-CHUNK-16 explica quando e como o treinamento acontece
    (
        "quando é o treinamento?",
        "direta",
        ["DOC05-CHUNK-16"],
        ["DOC05-CHUNK-20"]
    ),
    # [✓] DOC05-CHUNK-22 tem a lista completa de condições de eliminação
    (
        "posso ser eliminado do programa?",
        "negacao",
        ["DOC05-CHUNK-22"],
        []
    ),
    # [+] DOC05-CHUNK-09, DOC01-VGP-13, DOC02-FCP-11 proíbem cobranças
    (
        "alguem ta cobrando pelo treinamento, isso é certo?",
        "proibicao",
        ["DOC05-CHUNK-09", "DOC01-VGP-13", "DOC02-FCP-11"],
        []
    ),
    # [+] DOC05-CHUNK-18 é específico sobre logomarcas; DOC05-CHUNK-09 proíbe genericamente
    (
        "posso usar o logo da nasa nos meus posts?",
        "proibicao",
        ["DOC05-CHUNK-18", "DOC05-CHUNK-09"],
        []
    ),
    # [+] DOC05-CHUNK-23, DOC06-QSG-28 e DOC01-VGP-08 definem o MPC
    # NOTA v3: DOC06-QSG-21 era o glossário geral — agora é só "Astrometrica".
    #          Substituído por DOC06-QSG-28 (MPC Report, glossário QSG).
    (
        "o que é o MPC",
        "glossario",
        ["DOC05-CHUNK-23", "DOC06-QSG-28", "DOC01-VGP-08"],
        []
    ),
    # [✓] DOC05-CHUNK-34 responde "pode participar de mais de uma campanha"
    # NOTA v3: era DOC05-CHUNK-24 no gabarito v2 — chunk renumerado.
    (
        "posso participar de mais de uma campanha?",
        "direta",
        ["DOC05-CHUNK-34"],
        []
    ),
    # [+] DOC05-CHUNK-33 e DOC01-VGP-01 respondem que não precisa conhecimento prévio
    # NOTA v3: era DOC05-CHUNK-24 no gabarito v2 (chunk quebrado). Agora é CHUNK-33.
    (
        "preciso saber astronomia pra participar?",
        "direta",
        ["DOC05-CHUNK-33", "DOC01-VGP-01"],
        []
    ),

    # ──────────────────────────────────────────────────────────────────
    # DOC-06 — Quick Start Guide (Astrometrica)
    # ──────────────────────────────────────────────────────────────────

    # [+] DOC06-QSG-03 e DOC04-LCU-08 cobrem instalação
    (
        "como instalo o astrometrica",
        "direta",
        ["DOC06-QSG-03", "DOC04-LCU-08"],
        []
    ),
    # [✓] DOC06-QSG-04 tem License/Key e o processo de registro
    (
        "como registro o astrometrica",
        "direta",
        ["DOC06-QSG-04"],
        []
    ),
    # [✓] DOC06-QSG-05 é específico sobre ps1.cfg
    # NOTA v3: DOC06-QSG-21 era "glossário" no v2 — agora é só def. curta de Astrometrica.
    #          Substituído por DOC06-QSG-26 (Data Reduction def.) não é exato.
    #          O conteúdo de glossário sobre cfg está em DOC06-QSG-43 (Pan-STARRS e cfg).
    (
        "o que é o arquivo ps1.cfg",
        "tecnica",
        ["DOC06-QSG-05"],
        ["DOC06-QSG-43"]
    ),
    # [+] DOC06-QSG-13 (verdadeiras) e DOC06-QSG-14 (falsas) + DOC06-QSG-01
    # NOTA v3: DOC06-QSG-22 era "FAQ/erros" no v2 — agora é só "Image Set".
    #          Substituído pelos chunks específicos: DOC06-QSG-24 (True Sig) e DOC06-QSG-40 (False Sig).
    (
        "como sei se o que encontrei é asteroide de verdade ou falso",
        "tecnica",
        ["DOC06-QSG-13", "DOC06-QSG-14", "DOC06-QSG-01"],
        ["DOC06-QSG-24", "DOC06-QSG-40"]
    ),
    # [+] DOC06-QSG-23 e DOC05-CHUNK-25 definem blink comparison
    # NOTA v3: era QSG-21 (glossário) e DOC05-CHUNK-26 no v2.
    #          QSG-21 agora é "Astrometrica"; glossário de blink agora é QSG-23.
    #          DOC05-CHUNK-26 agora é "FITS"; blink no DOC05 agora é CHUNK-25.
    (
        "o que é blink comparison",
        "glossario",
        ["DOC06-QSG-23", "DOC05-CHUNK-25"],
        []
    ),
    # [+] DOC06-QSG-10 (grid search) e DOC06-QSG-20 (fluxo completo)
    (
        "como faço a varredura das imagens",
        "processo",
        ["DOC06-QSG-10", "DOC06-QSG-20"],
        ["DOC02-FCP-08"]
    ),
    # [+] DOC06-QSG-16 e DOC02-FCP-10 cobrem relatório sem detecções
    (
        "nao achei nada nas imagens, mando relatório mesmo assim?",
        "negacao",
        ["DOC06-QSG-16", "DOC02-FCP-10"],
        []
    ),
    # [+] DOC06-QSG-18 e DOC06-QSG-37 cobrem o Reference Star Match Error
    # NOTA v3: era QSG-18 e QSG-22 no v2. QSG-22 agora é "Image Set".
    #          O conteúdo de erro específico foi para QSG-37.
    (
        "deu Reference Star Match Error, o que faço",
        "problema",
        ["DOC06-QSG-18", "DOC06-QSG-37"],
        []
    ),
    # [+] DOC06-QSG-17 e DOC06-QSG-38 afirmam que NÃO pode enviar por e-mail
    # NOTA v3: era QSG-17 e QSG-22 no v2. QSG-22 agora é "Image Set".
    #          Conteúdo de "não enviar por email" foi para QSG-38.
    (
        "posso mandar o relatório por email?",
        "negacao",
        ["DOC06-QSG-17", "DOC06-QSG-38"],
        ["DOC02-FCP-09"]
    ),
    # [+] DOC06-QSG-30 (def) e DOC06-QSG-39 (procedimento) explicam o reset files
    # NOTA v3: era QSG-22 (FAQ) no v2. Agora há dois chunks dedicados: QSG-30 e QSG-39.
    (
        "o que é o reset files",
        "tecnica",
        ["DOC06-QSG-30", "DOC06-QSG-39"],
        ["DOC06-QSG-21"]
    ),
    # [+] DOC06-QSG-11 e DOC06-QSG-41 abordam medir nas 4 imagens
    # NOTA v3: era QSG-11 e QSG-22 no v2. QSG-22 agora é "Image Set".
    #          Conteúdo de "4 imagens" foi para QSG-41.
    (
        "precisa medir o objeto nas 4 imagens?",
        "direta",
        ["DOC06-QSG-11", "DOC06-QSG-41"],
        ["DOC06-QSG-20"]
    ),
    # [+] DOC06-QSG-19 e DOC06-QSG-01 cobrem o que o líder precisa dominar
    (
        "o que o lider precisa saber antes da campanha começar",
        "direta",
        ["DOC06-QSG-19", "DOC06-QSG-01"],
        ["DOC02-FCP-05"]
    ),

    # ──────────────────────────────────────────────────────────────────
    # COBERTURA DE CHUNKS ANTERIORMENTE SEM QUERY
    # ──────────────────────────────────────────────────────────────────

    # DOC01-VGP-09 — TNOs e NEOs
    # NOTA v3: DOC05-CHUNK-25 era "TNOs e NEOs" no v2, agora é "Blink Comparison".
    #          NEO agora é DOC05-CHUNK-24. TNO não tem chunk dedicado no corpus atual.
    (
        "o que é um NEO ou TNO",
        "glossario",
        ["DOC01-VGP-09", "DOC05-CHUNK-24"],
        []
    ),

    # DOC02-FCP-07 — Image set de prática obrigatório
    (
        "preciso fazer o image set de prática antes de começar?",
        "direta",
        ["DOC02-FCP-07"],
        ["DOC02-FCP-05"]
    ),

    # DOC05-CHUNK-08 — Responsabilidades do líder
    (
        "quais são as responsabilidades do líder durante a campanha",
        "direta",
        ["DOC05-CHUNK-08", "DOC02-FCP-11"],
        []
    ),

    # DOC05-CHUNK-11 — Metodologia científica de detecção
    (
        "como funciona a detecção de asteroides no programa",
        "conceito",
        ["DOC05-CHUNK-11"],
        ["DOC01-VGP-08"]
    ),

    # DOC05-CHUNK-12 — Relatório MPC definição e conteúdo
    # NOTA v3: DOC05-CHUNK-23 manteve ID mas agora é só "MPC" curto.
    #          DOC06-QSG-28 é o glossário de "MPC Report" no QSG.
    (
        "o que é o relatório MPC e o que ele contém",
        "tecnica",
        ["DOC05-CHUNK-12", "DOC05-CHUNK-23", "DOC06-QSG-28"],
        []
    ),

    # DOC05-CHUNK-13 — Resultados possíveis da participação
    (
        "que tipos de resultado posso obter participando do programa",
        "direta",
        ["DOC05-CHUNK-13"],
        []
    ),

    # DOC05-CHUNK-17 — Disposições finais e cancelamento
    (
        "o programa pode ser cancelado?",
        "direta",
        ["DOC05-CHUNK-17"],
        []
    ),

    # DOC06-QSG-06 — Barra de ferramentas do Astrometrica
    # NOTA v3: DOC06-QSG-21 era "glossário" no v2 — agora é definição curta.
    #          Mantido como contexto pois ainda define Astrometrica resumidamente.
    (
        "quais são os botões da barra de ferramentas do astrometrica",
        "tecnica",
        ["DOC06-QSG-06"],
        ["DOC06-QSG-21"]
    ),

    # DOC06-QSG-07 — Download dos image sets pela Team Page
    # NOTA v3: DOC06-QSG-29 (Team Page def.) entra como contexto útil.
    (
        "como faço o download dos image sets",
        "processo",
        ["DOC06-QSG-07"],
        ["DOC06-QSG-20", "DOC06-QSG-29"]
    ),

    # DOC06-QSG-08 — Data Reduction
    # NOTA v3: DOC06-QSG-26 (glossário Data Reduction) agora é chunk próprio.
    (
        "o que é o data reduction no astrometrica",
        "tecnica",
        ["DOC06-QSG-08", "DOC06-QSG-26"],
        ["DOC06-QSG-20"]
    ),

    # DOC06-QSG-09 — Known Object Overlay e Blink Images
    # NOTA v3: DOC06-QSG-27 (glossário Known Object Overlay) agora é chunk próprio.
    (
        "o que é o known object overlay",
        "tecnica",
        ["DOC06-QSG-09", "DOC06-QSG-27"],
        ["DOC06-QSG-21"]
    ),

    # DOC06-QSG-12 — Nomear objeto desconhecido / nova descoberta
    (
        "como nomeio um objeto desconhecido que encontrei",
        "processo",
        ["DOC06-QSG-12"],
        ["DOC06-QSG-11", "DOC05-CHUNK-13"]
    ),

    # DOC06-QSG-15 — Geração do relatório MPC no Astrometrica
    (
        "como gero o relatório mpc no astrometrica",
        "processo",
        ["DOC06-QSG-15"],
        ["DOC06-QSG-17", "DOC06-QSG-20"]
    ),

    # DOC04-LCU-04 — Canal no YouTube
    (
        "tem canal no youtube do programa?",
        "direta",
        ["DOC04-LCU-04"],
        ["DOC04-LCU-11"]
    ),

    # ──────────────────────────────────────────────────────────────────
    # NOVAS ENTRADAS — chunks do corpus novo sem cobertura no v2
    # ──────────────────────────────────────────────────────────────────

    # DOC05-CHUNK-35 — Participar em mais de uma equipe
    (
        "posso estar em duas equipes ao mesmo tempo?",
        "negacao",
        ["DOC05-CHUNK-35"],
        []
    ),

    # DOC05-CHUNK-36 — Validade do certificado
    (
        "o certificado tem validade nacional?",
        "direta",
        ["DOC05-CHUNK-36", "DOC03-CMD-02"],
        []
    ),

    # DOC05-CHUNK-37 — Participação de outros estados/países
    (
        "posso participar morando fora do brasil?",
        "direta",
        ["DOC05-CHUNK-37"],
        []
    ),

    # DOC05-CHUNK-39 — Participação individual
    (
        "posso participar sozinho sem equipe?",
        "negacao",
        ["DOC05-CHUNK-39", "DOC05-CHUNK-03"],
        []
    ),

    # DOC06-QSG-24 + DOC06-QSG-13 — True Signature
    (
        "o que é uma true signature",
        "glossario",
        ["DOC06-QSG-24", "DOC06-QSG-13"],
        []
    ),

    # DOC06-QSG-25 + DOC06-QSG-14 — False Signature
    (
        "o que é uma false signature",
        "glossario",
        ["DOC06-QSG-25", "DOC06-QSG-14"],
        ["DOC06-QSG-40"]
    ),

    # DOC06-QSG-29 — Team Page
    (
        "o que é a team page do iasc",
        "glossario",
        ["DOC06-QSG-29", "DOC06-QSG-07"],
        []
    ),

    # DOC06-QSG-44 — Ajuda técnica
    (
        "onde encontro ajuda técnica para a campanha",
        "suporte",
        ["DOC06-QSG-44", "DOC04-LCU-07"],
        ["DOC04-LCU-11"]
    ),
]

# Perguntas fora do escopo — nenhum chunk deve passar o threshold
FORA_DO_ESCOPO = [
    "como funciona um buraco negro",
    "qual o melhor telescópio pra comprar",
    "o que é astronomia",
    "como me tornar astrônomo profissional",
    "qual planeta fica mais perto do sol",
]


# ══════════════════════════════════════════════════════════════════════
# SEÇÃO 3 — SCORE NORMALIZADO POR QUERY
# normalizar_score (retrieval.py)
# ══════════════════════════════════════════════════════════════════════




# ══════════════════════════════════════════════════════════════════════
# SEÇÃO 4 — EMBEDDING(retrieval.py) E BUSCA
# ══════════════════════════════════════════════════════════════════════


def buscar(query: str, n_results: int = 5) -> list:
    """
    Busca os n chunks mais próximos no ChromaDB.
    Retorna lista de tuplas: (chunk_id, conteúdo, metadados, distância)
    """
    embedding = get_embedding(query)
    results = collection.query(
        query_embeddings=[embedding],
        n_results=n_results
    )
    return list(zip(
        results["ids"][0],
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0]
    ))


# ══════════════════════════════════════════════════════════════════════
# SEÇÃO 5 — AVALIAÇÃO PRINCIPAL
#
# MÉTRICAS CALCULADAS:
#
# Precision@1 (P@1)
#   O chunk no rank 1 está na lista de chunks_validos?
#   Mede se o sistema acerta o melhor resultado.
#   Erro aqui = o LLM vai começar a resposta com contexto errado.
#
# Set Coverage@3 (SC@3) ← NOVA MÉTRICA PRINCIPAL
#   Pelo menos 1 chunk válido está entre os 3 primeiros?
#   Como o LLM vai usar os 3 primeiros para gerar a resposta,
#   essa é a métrica mais relevante para qualidade de geração.
#   É a versão honesta do que a v1 chamava de "recall@5".
#
# Recall@5 (R@5)
#   Pelo menos 1 chunk válido está entre os 5 primeiros?
#   Útil para diagnóstico — se SC@3 é baixo mas R@5 é alto,
#   o sistema encontra o chunk mas não consegue ranqueá-lo bem.
#
# Contexto Útil@3 (CU@3)
#   Ao menos 1 chunk válido OU 1 chunk de contexto_util nos top 3?
#   Mede se a geração vai ter ALGUM material relevante.
#
# Taxa de Falso Negativo (FN)
#   Chunk válido estava no top-5 bruto mas foi cortado pelo threshold?
#   Se alto: threshold muito baixo, estamos descartando respostas certas.
#
# Taxa de Falso Positivo (FP)
#   Query fora do escopo retornou algum chunk abaixo do threshold?
#   Se alto: threshold muito alto, sistema responde o que não deveria.
# ══════════════════════════════════════════════════════════════════════

def avaliar(threshold: float = 1.2, verbose: bool = True) -> dict:
    """
    Avalia o sistema RAG contra o gabarito.

    Parâmetros:
        threshold → distância máxima aceita (chunks além disso são descartados)
        verbose   → imprime relatório no terminal
    """
    total = len(GABARITO)

    acertos_p1     = 0
    acertos_sc3    = 0
    acertos_r5     = 0
    acertos_cu3    = 0
    falsos_neg     = 0
    resultados     = []

    for pergunta, tipo, chunks_validos, chunks_contexto in GABARITO:

        # Busca bruta — recupera 5 candidatos sem filtro
        raw = buscar(pergunta, n_results=5)

        # Filtra pelo threshold
        candidatos = [(cid, doc, meta, dist)
                      for cid, doc, meta, dist in raw
                      if dist <= threshold]

        # Calcula scores normalizados
        if candidatos:
            dists  = [dist for _, _, _, dist in candidatos]
            scores = normalize_scores(dists)
            filtrados = [
                (cid, doc, meta, dist, score)
                for (cid, doc, meta, dist), score
                in zip(candidatos, scores)
            ]
            filtrados.sort(key=lambda x: x[4], reverse=True)
        else:
            filtrados = []

        ids_brutos    = [r[0] for r in raw]
        ids_filtrados = [f[0] for f in filtrados]
        ids_top3      = ids_filtrados[:3]

        # ── P@1: rank 1 é um chunk válido?
        rank1_id      = filtrados[0][0] if filtrados else None
        p1_correto    = rank1_id in chunks_validos if rank1_id else False

        # ── SC@3: algum chunk válido nos top 3?
        sc3_ok = any(c in ids_top3 for c in chunks_validos)

        # ── R@5: algum chunk válido nos top 5?
        r5_ok  = any(c in ids_filtrados for c in chunks_validos)

        # ── CU@3: algum válido ou contexto nos top 3?
        todos_uteis = chunks_validos + chunks_contexto
        cu3_ok = any(c in ids_top3 for c in todos_uteis)

        # ── Falso negativo: válido estava no bruto mas sumiu no filtro?
        valido_no_bruto    = any(c in ids_brutos    for c in chunks_validos)
        valido_no_filtrado = any(c in ids_filtrados for c in chunks_validos)
        if valido_no_bruto and not valido_no_filtrado:
            falsos_neg += 1

        if p1_correto: acertos_p1  += 1
        if sc3_ok:     acertos_sc3 += 1
        if r5_ok:      acertos_r5  += 1
        if cu3_ok:     acertos_cu3 += 1

        resultados.append({
            "pergunta":          pergunta,
            "tipo":              tipo,
            "validos":           chunks_validos,
            "contexto":          chunks_contexto,
            "rank1":             rank1_id,
            "rank1_dist":        filtrados[0][3] if filtrados else None,
            "rank1_score":       filtrados[0][4] if filtrados else None,
            "p1_correto":        p1_correto,
            "sc3_ok":            sc3_ok,
            "r5_ok":             r5_ok,
            "cu3_ok":            cu3_ok,
            "top3_ids":          ids_top3,
            "top5_ids":          ids_filtrados,
        })

    # ── Falsos positivos (fora do escopo)
    falsos_pos = 0
    for pergunta in FORA_DO_ESCOPO:
        raw = buscar(pergunta, n_results=5)
        if any(dist <= threshold for _, _, _, dist in raw):
            falsos_pos += 1

    metricas = {
        "threshold":      threshold,
        "total":          total,
        "precision_at_1": acertos_p1  / total,
        "set_coverage_3": acertos_sc3 / total,
        "recall_at_5":    acertos_r5  / total,
        "contexto_util_3":acertos_cu3 / total,
        "taxa_fn":        falsos_neg  / total,
        "taxa_fp":        falsos_pos  / len(FORA_DO_ESCOPO),
        "acertos_p1":     acertos_p1,
        "acertos_sc3":    acertos_sc3,
        "acertos_r5":     acertos_r5,
        "acertos_cu3":    acertos_cu3,
        "detalhe":        resultados,
    }

    if verbose:
        imprimir_metricas(metricas)

    return metricas


# ══════════════════════════════════════════════════════════════════════
# SEÇÃO 6 — FORMATAÇÃO E IMPRESSÃO
# ══════════════════════════════════════════════════════════════════════

def fmt(v) -> str:
    return f"{v:.4f}" if v is not None else "—"


def imprimir_metricas(m: dict):
    t = m["total"]
    print("\n" + "═" * 68)
    print(f"  THRESHOLD : {m['threshold']:.2f}  |  SCORE: min-max normalizado")
    print(f"  GABARITO  : {t} perguntas  |  FORA DO ESCOPO: {len(FORA_DO_ESCOPO)}")
    print("═" * 68)

    print(f"\n  {'Precision@1  (chunk válido no rank 1)':<44} "
          f"{m['precision_at_1']:>6.1%}  ({m['acertos_p1']}/{t})")
    print(f"  {'Set Coverage@3  (válido nos top 3 usados pelo LLM)':<44} "
          f"{m['set_coverage_3']:>6.1%}  ({m['acertos_sc3']}/{t})")
    print(f"  {'Recall@5  (válido em algum dos top 5)':<44} "
          f"{m['recall_at_5']:>6.1%}  ({m['acertos_r5']}/{t})")
    print(f"  {'Contexto Útil@3  (válido ou contexto nos top 3)':<44} "
          f"{m['contexto_util_3']:>6.1%}  ({m['acertos_cu3']}/{t})")

    print(f"\n  {'Falso Negativo  (válido cortado pelo threshold)':<44} "
          f"{m['taxa_fn']:>6.1%}")
    print(f"  {'Falso Positivo  (fora do escopo passou)':<44} "
          f"{m['taxa_fp']:>6.1%}")

    print("\n" + "─" * 68)
    p1  = m["precision_at_1"]
    sc3 = m["set_coverage_3"]
    r5  = m["recall_at_5"]

    # Diagnóstico P@1
    if p1 >= 0.85:
        print("  ✅ P@1 EXCELENTE — rank 1 quase sempre correto")
    elif p1 >= 0.70:
        print("  🟡 P@1 BOA — rank 1 erra em ~30% dos casos")
    else:
        print("  ❌ P@1 FRACA — muitos erros no resultado principal")

    # Diagnóstico SC@3
    if sc3 >= 0.90:
        print("  ✅ SC@3 EXCELENTE — LLM quase sempre tem contexto correto")
    elif sc3 >= 0.75:
        print("  🟡 SC@3 BOA — LLM terá contexto correto em 3/4 das queries")
    else:
        print("  ❌ SC@3 FRACA — LLM vai errar em muitas respostas")

    # Diagnóstico gap P@1 vs SC@3
    gap = sc3 - p1
    if gap > 0.15:
        print(f"  ⚠️  Gap P@1↔SC@3 = {gap:.1%} — chunks válidos chegam mas ficam")
        print(f"      mal ranqueados. Considere ajustar o threshold ou reindexar.")

    # Diagnóstico gap SC@3 vs R@5
    gap2 = r5 - sc3
    if gap2 > 0.10:
        print(f"  ⚠️  Gap SC@3↔R@5 = {gap2:.1%} — válidos aparecem no top-5 mas")
        print(f"      não nos top-3. O ranking precisa melhorar.")

    # Threshold
    if m["taxa_fn"] > 0.10:
        print("  ⚠️  FN alto — threshold pode estar baixo demais (descarta demais)")
    if m["taxa_fp"] > 0.20:
        print("  ⚠️  FP alto — threshold pode estar alto demais (aceita demais)")

    # Erros P@1
    erros = [d for d in m["detalhe"] if not d["p1_correto"]]
    if erros:
        print(f"\n  ❌ FALHAS NO RANK 1 ({len(erros)} de {t}):\n")
        for e in erros:
            sc3_tag = "✓SC@3" if e["sc3_ok"] else ("✓R@5" if e["r5_ok"] else "✗ausente")
            print(f"  [{e['tipo']:12}] [{sc3_tag}] {e['pergunta'][:46]:<46}")
            print(f"               validos  : {', '.join(e['validos'])}")
            print(f"               recebido : {e['rank1']}  "
                  f"(dist={fmt(e['rank1_dist'])}  score={fmt(e['rank1_score'])})")
            print(f"               top3     : {', '.join(e['top3_ids'])}")
            print()

    # Perguntas onde SC@3 falhou (mais crítico que P@1 para geração)
    sc3_erros = [d for d in m["detalhe"] if not d["sc3_ok"]]
    if sc3_erros:
        print(f"  ❌ FALHAS SC@3 — LLM NÃO TERÁ CONTEXTO CORRETO ({len(sc3_erros)}):\n")
        for e in sc3_erros:
            print(f"  [{e['tipo']:12}] {e['pergunta'][:50]}")
            print(f"               top3: {', '.join(e['top3_ids'])}")
            print()

    print("═" * 68 + "\n")


# ══════════════════════════════════════════════════════════════════════
# SEÇÃO 7 — BUSCA DO THRESHOLD IDEAL
#
# Otimiza para SC@3 (e não P@1 como na v1), porque SC@3 é o que
# realmente impacta a qualidade das respostas geradas pelo LLM.
# ══════════════════════════════════════════════════════════════════════

def buscar_threshold() -> dict:
    """Varre thresholds de 0.5 a 2.0 e retorna o melhor por SC@3."""

    thresholds = [round(x * 0.1, 1) for x in range(5, 21)]

    print("\n" + "═" * 82)
    print("  BUSCA DE THRESHOLD  |  score=min-max normalizado  |  otimiza SC@3")
    print("═" * 82)
    print(f"  {'Threshold':>10}  {'P@1':>7}  {'SC@3':>7}  {'R@5':>7}  "
          f"{'CU@3':>7}  {'FN':>7}  {'FP':>7}")
    print("─" * 82)

    melhor = None
    for t in thresholds:
        m = avaliar(threshold=t, verbose=False)
        marcador = " ← MELHOR" if (
            melhor is None or m["set_coverage_3"] > melhor["set_coverage_3"]
        ) else ""
        if melhor is None or m["set_coverage_3"] > melhor["set_coverage_3"]:
            melhor = m
        print(f"  {t:>10.1f}  {m['precision_at_1']:>7.1%}  {m['set_coverage_3']:>7.1%}  "
              f"{m['recall_at_5']:>7.1%}  {m['contexto_util_3']:>7.1%}  "
              f"{m['taxa_fn']:>7.1%}  {m['taxa_fp']:>7.1%}{marcador}")

    print("─" * 82)
    print(f"\n  ✅ Melhor threshold: {melhor['threshold']:.1f}  "
          f"(P@1={melhor['precision_at_1']:.1%}  "
          f"SC@3={melhor['set_coverage_3']:.1%}  "
          f"R@5={melhor['recall_at_5']:.1%})\n")
    return melhor


# ══════════════════════════════════════════════════════════════════════
# SEÇÃO 8 — ANÁLISE POR TIPO DE PERGUNTA
# ══════════════════════════════════════════════════════════════════════

def analisar_por_tipo(metricas: dict):
    from collections import defaultdict

    por_tipo_p1  = defaultdict(lambda: {"total": 0, "acertos": 0})
    por_tipo_sc3 = defaultdict(lambda: {"total": 0, "acertos": 0})

    for d in metricas["detalhe"]:
        t = d["tipo"]
        por_tipo_p1[t]["total"]  += 1
        por_tipo_sc3[t]["total"] += 1
        if d["p1_correto"]: por_tipo_p1[t]["acertos"]  += 1
        if d["sc3_ok"]:     por_tipo_sc3[t]["acertos"] += 1

    print("\n" + "═" * 68)
    print("  PERFORMANCE POR TIPO  (ordenado por SC@3 crescente)")
    print(f"  {'Tipo':<14} {'P@1':>7}  {'SC@3':>7}  {'N':>4}")
    print("─" * 68)

    tipos = sorted(
        por_tipo_sc3.keys(),
        key=lambda t: por_tipo_sc3[t]["acertos"] / por_tipo_sc3[t]["total"]
    )
    for tipo in tipos:
        p1  = por_tipo_p1[tipo]["acertos"]  / por_tipo_p1[tipo]["total"]
        sc3 = por_tipo_sc3[tipo]["acertos"] / por_tipo_sc3[tipo]["total"]
        n   = por_tipo_p1[tipo]["total"]
        barra = "█" * int(sc3 * 20) + "░" * (20 - int(sc3 * 20))
        print(f"  {tipo:<14} {p1:>7.1%}  {sc3:>7.1%}  {n:>4}  {barra}")

    print()


# ══════════════════════════════════════════════════════════════════════
# SEÇÃO 9 — ANÁLISE DE CHUNKS NUNCA RECUPERADOS
#
# Identifica chunks válidos que NUNCA aparecem no top-5 de qualquer
# query do gabarito — possível problema de indexação ou chunk muito
# genérico para ser recuperado via embedding.
# ══════════════════════════════════════════════════════════════════════

def analisar_chunks_perdidos(metricas: dict):
    """Mostra quais chunks válidos nunca foram recuperados."""
    recuperados = set()
    for d in metricas["detalhe"]:
        recuperados.update(d["top5_ids"])

    todos_validos = set()
    mapa_valido_query = {}
    for pergunta, _, chunks_validos, _ in GABARITO:
        for c in chunks_validos:
            todos_validos.add(c)
            mapa_valido_query.setdefault(c, []).append(pergunta)

    perdidos = todos_validos - recuperados

    if not perdidos:
        print("\n  ✅ Todos os chunks válidos foram recuperados em alguma query.\n")
        return

    print(f"\n  ⚠️  CHUNKS VÁLIDOS NUNCA RECUPERADOS ({len(perdidos)}):\n")
    for chunk_id in sorted(perdidos):
        queries = mapa_valido_query.get(chunk_id, [])
        print(f"  {chunk_id}")
        for q in queries:
            print(f"    → esperado em: '{q}'")
    print()


# ══════════════════════════════════════════════════════════════════════
# SEÇÃO 10 — SALVAR RESULTADOS
# ══════════════════════════════════════════════════════════════════════

def salvar_resultados(metricas: dict, caminho: str = "resultados_rag_v2.json"):
    exportar = {k: v for k, v in metricas.items() if k != "detalhe"}
    exportar["falhas_p1"] = [
        d for d in metricas["detalhe"] if not d["p1_correto"]
    ]
    exportar["falhas_sc3"] = [
        d for d in metricas["detalhe"] if not d["sc3_ok"]
    ]
    exportar["acertos_p1_detalhe"] = [
        d for d in metricas["detalhe"] if d["p1_correto"]
    ]
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(exportar, f, ensure_ascii=False, indent=2)
    print(f"  💾 Resultados salvos em: {caminho}\n")


# ══════════════════════════════════════════════════════════════════════
# SEÇÃO 11 — MAIN
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Avaliador RAG v2 — Caça Asteroides MCTI 2026",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:
  python avaliar_rag_v2.py                          avaliação padrão (threshold=1.2)
  python avaliar_rag_v2.py --threshold 0.9          testa threshold específico
  python avaliar_rag_v2.py --busca-threshold        encontra o melhor threshold
  python avaliar_rag_v2.py --completo               tudo junto
  python avaliar_rag_v2.py --completo --salvar      tudo + salva JSON

Métricas principais:
  P@1    → chunk válido está no rank 1?
  SC@3   → chunk válido está nos top 3 usados pelo LLM para gerar resposta?
  R@5    → chunk válido está em algum dos top 5?
  CU@3   → chunk válido ou de contexto útil está nos top 3?
        """
    )

    parser.add_argument("--threshold",       type=float, default=1.2,
                        help="Distância máxima aceita (padrão: 1.2)")
    parser.add_argument("--busca-threshold", action="store_true",
                        help="Varre thresholds de 0.5 a 2.0 e mostra tabela")
    parser.add_argument("--completo",        action="store_true",
                        help="Avaliação + por tipo + chunks perdidos + busca threshold")
    parser.add_argument("--salvar",          action="store_true",
                        help="Salva os resultados em resultados_rag_v2.json")

    args = parser.parse_args()

    if args.completo:
        print("\n🔍 Avaliação completa v2...\n")
        m = avaliar(args.threshold)
        analisar_por_tipo(m)
        analisar_chunks_perdidos(m)
        buscar_threshold()
        if args.salvar:
            salvar_resultados(m)

    elif args.busca_threshold:
        buscar_threshold()

    else:
        m = avaliar(args.threshold)
        analisar_por_tipo(m)
        analisar_chunks_perdidos(m)
        if args.salvar:
            salvar_resultados(m)