"""
═══════════════════════════════════════════════════════════════════════
  DATASET DE AVALIAÇÃO — Caça Asteroides MCTI
  Fonte ÚNICA de perguntas e gabarito. Importado por test_definitivo.py.
═══════════════════════════════════════════════════════════════════════

Quatro conjuntos, cada um testa uma coisa diferente:

  IN_SCOPE     → tem resposta na base. Sistema DEVE responder.
                 Gabarito multi-chunk: 'validos' = chunks que sozinhos
                 respondem; 'contexto' = ajudam mas não bastam.

  ADVERSARIAL  → usa vocabulário do domínio (asteroide, equipe, campanha)
                 MAS não tem resposta na base. Sistema DEVE recusar.
                 É o teste DURO de contenção — cai na zona de distância
                 intermediária, onde o cutoff é decidido.

  OUT_OF_SCOPE → totalmente fora. Sistema DEVE recusar. Teste fácil.

  MULTI_TURN   → follow-up que só faz sentido com o histórico. Testa o
                 enriched_query do retrieve (last_user + query).
"""

# ─────────────────────────────────────────────────────────────────────
# IN-SCOPE  (q, tipo, validos, contexto)
# ─────────────────────────────────────────────────────────────────────
IN_SCOPE = [
    # ---- DOC-01 visão geral ----
    ("o que é o caça asteroides", "visao_geral",
     ["DOC01-VGP-01", "DOC05-CHUNK-01", "DOC01-VGP-12"], ["DOC01-VGP-02"]),
    ("o programa é parceria com a nasa?", "visao_geral",
     ["DOC01-VGP-04", "DOC05-CHUNK-01"], ["DOC01-VGP-10"]),
    ("quantos asteroides o iasc já descobriu", "visao_geral",
     ["DOC01-VGP-05"], []),
    ("de onde vêm as imagens que a gente analisa", "visao_geral",
     ["DOC01-VGP-06"], []),
    ("o que é ciência cidadã", "conceito",
     ["DOC01-VGP-12", "DOC01-VGP-01"], []),
    ("o programa é gratuito?", "regras",
     ["DOC01-VGP-13", "DOC05-CHUNK-09"], []),
    ("o que é um asteroide do cinturão principal", "glossario",
     ["DOC01-VGP-08"], []),

    # ---- DOC-02 fluxo ----
    ("qual o primeiro passo pra participar", "inscricao",
     ["DOC02-FCP-02", "DOC05-CHUNK-04"], ["DOC02-FCP-01"]),
    ("como faço login na plataforma do iasc", "processo",
     ["DOC02-FCP-06", "DOC04-LCU-06"], []),
    ("não recebi o email do iasc, o que faço", "problema",
     ["DOC02-FCP-04"], ["DOC04-LCU-07"]),
    ("preciso usar windows?", "tecnica",
     ["DOC02-FCP-14", "DOC05-CHUNK-21", "DOC06-QSG-02", "DOC01-VGP-11"], []),

    # ---- DOC-03 certificado / medalha ----
    ("como pego o certificado", "certificado",
     ["DOC03-CMD-03", "DOC02-FCP-13", "DOC05-CHUNK-07"], []),
    ("qual a diferença entre certificado e medalha", "certificado",
     ["DOC03-CMD-01", "DOC03-CMD-08"], []),
    ("o que preciso pra ganhar a medalha", "medalha",
     ["DOC03-CMD-06", "DOC03-CMD-08"], ["DOC03-CMD-01"]),
    ("errei meu nome na inscrição, dá pra corrigir no certificado?", "problema",
     ["DOC03-CMD-04"], ["DOC05-CHUNK-07"]),
    ("preciso detectar asteroide pra ter certificado?", "certificado",
     ["DOC03-CMD-02", "DOC03-CMD-08", "DOC05-CHUNK-07"], []),
    ("a medalha vem pelo correio?", "medalha",
     ["DOC03-CMD-07"], ["DOC03-CMD-05"]),

    # ---- DOC-04 contatos ----
    ("tem instagram do programa?", "contato",
     ["DOC04-LCU-03"], ["DOC04-LCU-11"]),
    ("tem grupo de whatsapp?", "contato",
     ["DOC04-LCU-05", "DOC02-FCP-12"], []),
    ("qual o email pra tirar dúvida", "contato",
     ["DOC04-LCU-01", "DOC05-CHUNK-20"], ["DOC04-LCU-11"]),
    ("onde envio os documentos de inscrição", "inscricao",
     ["DOC04-LCU-02", "DOC02-FCP-03", "DOC05-CHUNK-10"], []),

    # ---- DOC-05 edital ----
    ("quem pode participar do programa", "elegibilidade",
     ["DOC05-CHUNK-02"], ["DOC01-VGP-01"]),
    ("meu filho tem 8 anos, pode participar?", "elegibilidade",
     ["DOC05-CHUNK-02"], []),
    ("quantas pessoas precisa ter na equipe", "equipe",
     ["DOC05-CHUNK-03"], []),
    ("posso trocar um integrante no meio da campanha", "equipe",
     ["DOC05-CHUNK-03"], []),
    ("quais as datas das campanhas de 2026", "cronograma",
     ["DOC05-CHUNK-05", "DOC02-FCP-15"], []),
    ("o treinamento é obrigatório?", "regras",
     ["DOC05-CHUNK-16", "DOC02-FCP-11"], []),
    ("posso ser eliminado do programa?", "regras",
     ["DOC05-CHUNK-22"], []),
    ("alguém está cobrando pelo treinamento, isso é certo?", "proibicao",
     ["DOC05-CHUNK-09", "DOC01-VGP-13", "DOC02-FCP-11"], []),
    ("posso usar o logo da nasa nos meus posts?", "proibicao",
     ["DOC05-CHUNK-18", "DOC05-CHUNK-09"], []),
    ("posso participar morando fora do brasil?", "elegibilidade",
     ["DOC05-CHUNK-37"], []),
    ("posso estar em duas equipes ao mesmo tempo?", "equipe",
     ["DOC05-CHUNK-35"], []),
    ("posso participar sozinho sem equipe?", "equipe",
     ["DOC05-CHUNK-39", "DOC05-CHUNK-03"], []),
    ("o certificado tem validade nacional?", "certificado",
     ["DOC05-CHUNK-36", "DOC03-CMD-02"], []),
    ("preciso saber astronomia pra participar?", "elegibilidade",
     ["DOC05-CHUNK-33", "DOC01-VGP-01"], []),

    # ---- DOC-06 QSG (inclui os 3 novos: 45, 46, 47) ----
    ("como instalo o astrometrica", "instalacao",
     ["DOC06-QSG-03", "DOC04-LCU-08"], []),
    ("como registro o astrometrica / onde coloco a licença", "instalacao",
     ["DOC06-QSG-04"], []),
    ("o que é o arquivo ps1.cfg", "config",
     ["DOC06-QSG-05"], ["DOC06-QSG-43"]),
    ("como sei se o que encontrei é asteroide de verdade", "analise",
     ["DOC06-QSG-13", "DOC06-QSG-14"], ["DOC06-QSG-24"]),
    ("o que é uma falsa assinatura", "analise",
     ["DOC06-QSG-14", "DOC06-QSG-25"], ["DOC06-QSG-40"]),
    ("posso mandar o relatório por email?", "relatorio",
     ["DOC06-QSG-17", "DOC06-QSG-38"], ["DOC02-FCP-09"]),
    ("o que é o reset files", "config",
     ["DOC06-QSG-30", "DOC06-QSG-39"], []),
    ("como envio o relatório mpc", "relatorio",
     ["DOC02-FCP-09", "DOC06-QSG-17"], ["DOC06-QSG-20"]),
    ("o que é a team page do iasc", "glossario",
     ["DOC06-QSG-29", "DOC06-QSG-07"], []),
    # --- 3 chunks novos do QSG ---
    ("qual catálogo de estrelas eu seleciono no astrometrica", "config",
     ["DOC06-QSG-45"], ["DOC06-QSG-05"]),
    ("posso clicar em send no astrometrica pra enviar?", "relatorio",
     ["DOC06-QSG-46"], ["DOC06-QSG-17"]),
    ("por que só tem a imagem de prática disponível?", "download_imagens",
     ["DOC06-QSG-47", "DOC02-FCP-07"], ["DOC06-QSG-07"]),

    # ---- DOC-07 erros (todos os 14 novos) ----
    ("não consigo abrir a página da minha equipe", "erro_site",
     ["DOC07-ERR-01"], ["DOC06-QSG-07"]),
    ("deu erro F51 ao enviar o relatório", "erro_site",
     ["DOC07-ERR-02"], []),
    ("o astrometrica está pedindo uma licença", "erro_astrometrica",
     ["DOC07-ERR-03", "DOC06-QSG-04"], []),
    ("deu runtime error ao abrir o astrometrica", "erro_astrometrica",
     ["DOC07-ERR-04"], []),
    ("o erro de calibração continua mesmo com a option 2", "erro_astrometrica",
     ["DOC07-ERR-05"], ["DOC06-QSG-18", "DOC06-QSG-37"]),
    ("deu I/O-error 3 escrevendo o mpcreport", "erro_astrometrica",
     ["DOC07-ERR-06"], []),
    ("sumiram os ícones da barra de ferramentas", "erro_astrometrica",
     ["DOC07-ERR-07"], []),
    ("cliquei pra marcar o asteroide e não acontece nada", "erro_analise",
     ["DOC07-ERR-08"], ["DOC02-FCP-08"]),
    ("marquei o objeto mas a marcação não aparece", "erro_analise",
     ["DOC07-ERR-09"], ["DOC06-QSG-45"]),
    ("a tabela de objetos próximos está vazia", "erro_analise",
     ["DOC07-ERR-10"], []),
    ("apareceu floating point error ao marcar", "erro_analise",
     ["DOC07-ERR-11"], []),
    ("fiz uma marcação errada, como corrijo", "erro_analise",
     ["DOC07-ERR-12"], ["DOC06-QSG-39"]),
    ("esqueci de marcar um asteroide e já enviei o relatório", "erro_analise",
     ["DOC07-ERR-13"], []),
    ("o objeto se move mas não aparece em todas as imagens", "erro_analise",
     ["DOC07-ERR-14", "DOC06-QSG-13"], []),
]

# ─────────────────────────────────────────────────────────────────────
# ADVERSARIAL — vocabulário do domínio, SEM resposta na base. Recusar.
# ─────────────────────────────────────────────────────────────────────
ADVERSARIAL = [
    "o asteroide apophis vai colidir com a terra?",
    "qual asteroide a minha equipe descobriu?",
    "qual a distância da terra até o cinturão de asteroides?",
    "quantos asteroides existem no sistema solar?",
    "qual o maior asteroide já descoberto na história?",
    "como os asteroides se formaram?",
    "asteroide é a mesma coisa que cometa?",
    "qual a velocidade média de um asteroide?",
    "minha equipe vai ganhar a medalha esse ano?",
    "quantas equipes participaram da campanha de 2025?",
    "de que material é feito um asteroide?",
    "qual a chance de um asteroide destruir a terra?",
]

# ─────────────────────────────────────────────────────────────────────
# OUT-OF-SCOPE — totalmente fora. Recusar.
# ─────────────────────────────────────────────────────────────────────
OUT_OF_SCOPE = [
    "qual a capital da frança",
    "me dá uma receita de bolo de chocolate",
    "quem ganhou a copa do mundo de 2022",
    "como faço pra investir na bolsa de valores",
    "como instalo o python",
    "o que é machine learning",
    "me recomenda um filme de ficção científica",
    "como funciona o imposto de renda",
    "qual o melhor celular pra comprar em 2026",
    "como faço um bom currículo",
]

# ─────────────────────────────────────────────────────────────────────
# MULTI-TURN — follow-up depende do histórico. (history, q, validos)
# history termina na última fala do USUÁRIO antes do follow-up.
# ─────────────────────────────────────────────────────────────────────
MULTI_TURN = [
    (
        [{"role": "user", "content": "deu erro de calibração no astrometrica"},
         {"role": "assistant", "content": "Selecione a Option 2 (Automatic Reference Star Match) e clique OK."}],
        "e se isso não resolver?",
        ["DOC07-ERR-05"],
    ),
    (
        [{"role": "user", "content": "como pego o certificado?"},
         {"role": "assistant", "content": "É solicitado na plataforma do IASC ao fim da campanha."}],
        "e se eu tiver errado meu nome?",
        ["DOC03-CMD-04"],
    ),
    (
        [{"role": "user", "content": "quero montar uma equipe pra participar"},
         {"role": "assistant", "content": "Ótimo! As equipes têm um líder e integrantes."}],
        "quantas pessoas eu preciso?",
        ["DOC05-CHUNK-03"],
    ),
    (
        [{"role": "user", "content": "to analisando as imagens no astrometrica"},
         {"role": "assistant", "content": "Perfeito. Use o blink para ver o movimento."}],
        "como sei se é de verdade?",
        ["DOC06-QSG-13", "DOC06-QSG-14"],
    ),
    (
        [{"role": "user", "content": "o astrometrica não abre"},
         {"role": "assistant", "content": "Pode ser falta da pasta de dados locais."}],
        "apareceu runtime error",
        ["DOC07-ERR-04"],
    ),
    (
        [{"role": "user", "content": "terminei de analisar e não achei nenhum asteroide"},
         {"role": "assistant", "content": "Mesmo assim você precisa enviar um relatório."}],
        "como faço isso?",
        ["DOC06-QSG-16", "DOC02-FCP-10"],
    ),
]
