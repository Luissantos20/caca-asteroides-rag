"""
═══════════════════════════════════════════════════════════════════════
  DATASET DE AVALIAÇÃO v1 — Caça Asteroides
═══════════════════════════════════════════════════════════════════════

SÓ DADO. Quem executa é o run_eval.py.

CADA CASO carrega etiquetas que viajam até o JSONL (pra fatiar a análise):
  persona            → de onde vem a dúvida:
                       software | inscricao | visao_geral | regras_faq
                       | adversarial | out_of_scope
  quality            → "clean"  (bem escrito)
                       "messy"  (minúsculas, sem pontuação, abreviação, gíria)
  category           → categoria do CONTEÚDO (vinda do corpus)
  expected_behavior  → "answer" (a base responde) | "refuse" (não responde)
  anchor             → chunk(s) que DEVERIAM responder. É PALPITE MEU pra
                       revisão — NÃO é usado pela lógica. Serve pra comparar
                       com o que o retrieval REALMENTE trouxe.
  key_facts          → o que uma boa resposta precisa conter (revisão humana)
  query              → o texto enviado ao sistema

COMO LER OS RESULTADOS (lembrete):
  - persona adversarial/out_of_scope DEVE recusar (blocked_decision ou
    refused_generation). Se responder = falso positivo (alucinação).
  - personas reais DEVEM responder. Se recusar = falsa recusa (o bug que
    achamos). Compare `anchor` com os chunks que vieram pra ver se foi
    falha de busca ou de geração.

VIÉS: a cobertura é guiada pelo corpus (não por gosto), mas a minha ESCOLHA
DE PALAVRAS ainda é minha. Por isso os casos `messy` e as variações de termo
existem — e por isso o passo seguinte é um gerador que parafraseia estas
sementes. Esta lista é o ponto de partida revisável.

Tudo aqui é single-turn (history=0) de propósito. Multi-turn (histórico
poluído, a intermitência do "como participo") é o próximo eixo — depois de
confirmarmos como o frontend monta o history.
"""

CASES = [

    # ╔══════════════════════════════════════════════════════════════════╗
    # ║ PERSONA: software — participante travado no Astrometrica           ║
    # ╚══════════════════════════════════════════════════════════════════╝
    {"id": "sw-01", "persona": "software", "quality": "clean",
     "category": "erro_astrometrica", "expected_behavior": "answer",
     "anchor": ["DOC07-ERR-03", "DOC06-QSG-04"],
     "key_facts": "Astrometrica pedindo licença → inserir License/Key do registro",
     "query": "O Astrometrica está pedindo uma licença. O que eu faço?"},

    {"id": "sw-02", "persona": "software", "quality": "messy",
     "category": "erro_astrometrica", "expected_behavior": "answer",
     "anchor": ["DOC07-ERR-04"],
     "key_facts": "runtime error ao abrir o Astrometrica → como resolver",
     "query": "abri o astrometrica e deu runtime error oq eh isso"},

    {"id": "sw-03", "persona": "software", "quality": "clean",
     "category": "analise_imagens", "expected_behavior": "answer",
     "anchor": ["DOC06-QSG-08", "DOC06-QSG-26"],
     "key_facts": "Data Reduction = calibração das imagens; como fazer",
     "query": "Como eu faço a calibração das imagens no Astrometrica?"},

    {"id": "sw-04", "persona": "software", "quality": "messy",
     "category": "erro_analise", "expected_behavior": "answer",
     "anchor": ["DOC07-ERR-08"],
     "key_facts": "cliquei pra marcar e nada acontece → causa/solução",
     "query": "cliquei pra marcar o asteroide e n acontece nada"},

    {"id": "sw-05", "persona": "software", "quality": "messy",
     "category": "erro_analise", "expected_behavior": "answer",
     "anchor": ["DOC07-ERR-09"],
     "key_facts": "marquei mas a marcação não aparece → como resolver",
     "query": "marquei o asteroide mas a marcaçao n ta aparecendo pq"},

    {"id": "sw-06", "persona": "software", "quality": "clean",
     "category": "glossario", "expected_behavior": "answer",
     "anchor": ["DOC06-QSG-23", "DOC05-CHUNK-25"],
     "key_facts": "blink = alternar imagens pra detectar movimento",
     "query": "O que é blink comparison?"},

    {"id": "sw-07", "persona": "software", "quality": "clean",
     "category": "relatorio_mpc", "expected_behavior": "answer",
     "anchor": ["DOC06-QSG-15", "DOC05-CHUNK-12"],
     "key_facts": "como gerar o relatório MPC no Astrometrica",
     "query": "Como gero o relatório MPC?"},

    {"id": "sw-08", "persona": "software", "quality": "messy",
     "category": "erro_analise", "expected_behavior": "answer",
     "anchor": ["DOC07-ERR-13"],
     "key_facts": "esqueci de marcar e já enviei → o que fazer",
     "query": "esqueci de marcar um asteroide e ja mandei o relatorio e agora"},

    {"id": "sw-09", "persona": "software", "quality": "clean",
     "category": "assinaturas", "expected_behavior": "answer",
     "anchor": ["DOC06-QSG-14", "DOC06-QSG-25", "DOC06-QSG-40"],
     "key_facts": "falsa assinatura = artefato que NÃO deve ser reportado",
     "query": "O que é uma falsa assinatura?"},

    {"id": "sw-10", "persona": "software", "quality": "messy",
     "category": "faq", "expected_behavior": "answer",
     "anchor": ["DOC06-QSG-37"],
     "key_facts": "Reference Star Match Error → causa e como resolver",
     "query": "deu reference star match error aqui, como arruma"},

    {"id": "sw-11", "persona": "software", "quality": "clean",
     "category": "faq", "expected_behavior": "answer",
     "anchor": ["DOC06-QSG-41"],
     "key_facts": "objeto precisa ser medido/aparecer nas 4 imagens",
     "query": "Preciso medir o objeto nas quatro imagens?"},

    {"id": "sw-12", "persona": "software", "quality": "messy",
     "category": "faq", "expected_behavior": "answer",
     "anchor": ["DOC06-QSG-39", "DOC06-QSG-30"],
     "key_facts": "como fazer Reset Files no Astrometrica",
     "query": "como q faz reset files no astrometrica"},

    # ╔══════════════════════════════════════════════════════════════════╗
    # ║ PERSONA: inscricao — quer entrar / montar equipe                  ║
    # ╚══════════════════════════════════════════════════════════════════╝
    {"id": "in-01", "persona": "inscricao", "quality": "clean",
     "category": "inscricao", "expected_behavior": "answer",
     "anchor": ["DOC02-FCP-02", "DOC05-CHUNK-04"],
     "key_facts": "inscrição feita pelo líder via formulário; passo a passo",
     "query": "Como faço para inscrever minha equipe?"},

    {"id": "in-02", "persona": "inscricao", "quality": "messy",
     "category": "equipes", "expected_behavior": "answer",
     "anchor": ["DOC05-CHUNK-03"],
     "key_facts": "equipe de 3 a 5 pessoas (1 líder + 2 a 4 integrantes)",
     "query": "qnts pessoas precisa pra montar uma equipe?"},

    {"id": "in-03", "persona": "inscricao", "quality": "clean",
     "category": "elegibilidade", "expected_behavior": "answer",
     "anchor": ["DOC05-CHUNK-02"],
     "key_facts": "líder ≥18; demais ≥6 anos",
     "query": "Qual a idade mínima para participar?"},

    {"id": "in-04", "persona": "inscricao", "quality": "messy",
     "category": "inscricao", "expected_behavior": "answer",
     "anchor": ["DOC02-FCP-01", "DOC02-FCP-02"],
     "key_facts": "por onde começar a inscrição",
     "query": "to querendo me inscrever mas n sei por onde começar"},

    {"id": "in-05", "persona": "inscricao", "quality": "clean",
     "category": "documentos", "expected_behavior": "answer",
     "anchor": ["DOC05-CHUNK-10", "DOC02-FCP-03"],
     "key_facts": "termos de autorização de uso de imagem em PDF por e-mail",
     "query": "Quais documentos eu preciso enviar na inscrição?"},

    {"id": "in-06", "persona": "inscricao", "quality": "clean",
     "category": "cronograma", "expected_behavior": "answer",
     "anchor": ["DOC05-CHUNK-05", "DOC02-FCP-15"],
     "key_facts": "datas/abertura das campanhas 2026",
     "query": "Quando abrem as inscrições de 2026?"},

    {"id": "in-07", "persona": "inscricao", "quality": "clean",
     "category": "elegibilidade", "expected_behavior": "answer",
     "anchor": ["DOC05-CHUNK-02"],
     "key_facts": "não precisa ser professor; públicos variados elegíveis",
     "query": "Preciso ser professor para participar?"},  # tipo que bugou

    {"id": "in-08", "persona": "inscricao", "quality": "messy",
     "category": "elegibilidade", "expected_behavior": "answer",
     "anchor": ["DOC05-CHUNK-02"],
     "key_facts": "criança pode (≥6 anos como integrante)",
     "query": "criança pode participar?"},

    {"id": "in-09", "persona": "inscricao", "quality": "clean",
     "category": "links_inscricao", "expected_behavior": "answer",
     "anchor": ["DOC05-CHUNK-15", "DOC04-LCU-10"],
     "key_facts": "links de inscrição por campanha",
     "query": "Onde encontro o link de inscrição da campanha de maio?"},

    # ╔══════════════════════════════════════════════════════════════════╗
    # ║ PERSONA: visao_geral — quer entender o projeto / por onde começar ║
    # ╚══════════════════════════════════════════════════════════════════╝
    {"id": "vg-01", "persona": "visao_geral", "quality": "clean",
     "category": "visao_geral", "expected_behavior": "answer",
     "anchor": ["DOC01-VGP-01", "DOC05-CHUNK-01"],
     "key_facts": "ciência cidadã MCTI; IASC/NASA; Astrometrica; detectar asteroides",
     "query": "O que é o Caça Asteroides?"},

    {"id": "vg-02", "persona": "visao_geral", "quality": "clean",
     "category": "visao_geral", "expected_behavior": "answer",
     "anchor": ["DOC01-VGP-02"],
     "key_facts": "objetivo do programa",
     "query": "Qual é o objetivo do programa?"},

    {"id": "vg-03", "persona": "visao_geral", "quality": "messy",
     "category": "visao_geral_fluxo", "expected_behavior": "answer",
     "anchor": ["DOC02-FCP-01"],
     "key_facts": "fluxo do início ao fim; por onde começar",
     "query": "quero entender como funciona tudo, por onde eu começo"},

    {"id": "vg-04", "persona": "visao_geral", "quality": "clean",
     "category": "regras_proibicoes", "expected_behavior": "answer",
     "anchor": ["DOC01-VGP-13", "DOC05-CHUNK-09"],
     "key_facts": "programa totalmente gratuito",
     "query": "O programa é gratuito?"},

    {"id": "vg-05", "persona": "visao_geral", "quality": "clean",
     "category": "parceiros_brasil", "expected_behavior": "answer",
     "anchor": ["DOC01-VGP-03"],
     "key_facts": "quem coordena no Brasil (MCTI e parceiros)",
     "query": "Quem coordena o programa no Brasil?"},

    {"id": "vg-06", "persona": "visao_geral", "quality": "clean",
     "category": "parceiros_iasc", "expected_behavior": "answer",
     "anchor": ["DOC01-VGP-04", "DOC05-CHUNK-30"],
     "key_facts": "IASC = International Astronomical Search Collaboration",
     "query": "O que é o IASC?"},

    {"id": "vg-07", "persona": "visao_geral", "quality": "messy",
     "category": "requisitos_tecnicos", "expected_behavior": "answer",
     "anchor": ["DOC05-CHUNK-21"],
     "key_facts": "não precisa telescópio; imagens fornecidas pelo IASC",
     "query": "preciso ter telescopio pra participar?"},

    # ╔══════════════════════════════════════════════════════════════════╗
    # ║ PERSONA: regras_faq — dúvidas de regra (inclui tipos que bugaram) ║
    # ╚══════════════════════════════════════════════════════════════════╝
    {"id": "fq-01", "persona": "regras_faq", "quality": "clean",
     "category": "faq", "expected_behavior": "answer",
     "anchor": ["DOC05-CHUNK-33"],
     "key_facts": "não precisa conhecimento prévio em astronomia",
     "query": "Preciso saber astronomia para participar?"},  # tipo que bugou

    {"id": "fq-02", "persona": "regras_faq", "quality": "clean",
     "category": "faq", "expected_behavior": "answer",
     "anchor": ["DOC05-CHUNK-34"],
     "key_facts": "pode participar de mais de uma campanha",
     "query": "Posso participar de mais de uma campanha?"},

    {"id": "fq-03", "persona": "regras_faq", "quality": "messy",
     "category": "faq", "expected_behavior": "answer",
     "anchor": ["DOC05-CHUNK-36"],
     "key_facts": "validade do certificado",
     "query": "o certificado vence? tem validade?"},

    {"id": "fq-04", "persona": "regras_faq", "quality": "clean",
     "category": "glossario", "expected_behavior": "answer",
     "anchor": ["DOC05-CHUNK-31"],
     "key_facts": "designação provisória = código temporário antes do nome oficial",
     "query": "O que é designação provisória?"},  # glossário (termo bate)

    {"id": "fq-05", "persona": "regras_faq", "quality": "messy",
     "category": "faq", "expected_behavior": "answer",
     "anchor": ["DOC05-CHUNK-37"],
     "key_facts": "pode participar de outros estados/países",
     "query": "moro em outro estado, ainda posso participar?"},

    {"id": "fq-06", "persona": "regras_faq", "quality": "messy",
     "category": "faq", "expected_behavior": "answer",
     "anchor": ["DOC05-CHUNK-39", "DOC05-CHUNK-35"],
     "key_facts": "participação é em equipe (regra de tamanho); individual?",
     "query": "da pra participar sozinho sem equipe?"},

    {"id": "fq-07", "persona": "regras_faq", "quality": "clean",
     "category": "comparativo", "expected_behavior": "answer",
     "anchor": ["DOC03-CMD-01", "DOC03-CMD-08"],
     "key_facts": "diferença entre certificado e medalha",
     "query": "Qual a diferença entre o certificado e a medalha?"},

    # ╔══════════════════════════════════════════════════════════════════╗
    # ║ CONTROLE: adversarial — vocabulário do domínio, sem resposta base ║
    # ║           DEVE RECUSAR. Se responder = alucinação.                ║
    # ╚══════════════════════════════════════════════════════════════════╝
    {"id": "adv-01", "persona": "adversarial", "quality": "clean",
     "category": "adversarial", "expected_behavior": "refuse", "anchor": [],
     "key_facts": "—",
     "query": "Qual asteroide a minha equipe descobriu?"},

    {"id": "adv-02", "persona": "adversarial", "quality": "messy",
     "category": "adversarial", "expected_behavior": "refuse", "anchor": [],
     "key_facts": "—",
     "query": "quantos pontos a minha equipe fez ate agora"},

    {"id": "adv-03", "persona": "adversarial", "quality": "clean",
     "category": "adversarial", "expected_behavior": "refuse", "anchor": [],
     "key_facts": "—",
     "query": "Minha inscrição já foi aprovada?"},

    {"id": "adv-04", "persona": "adversarial", "quality": "messy",
     "category": "adversarial", "expected_behavior": "refuse", "anchor": [],
     "key_facts": "—",
     "query": "qual a previsao do tempo pra observar hoje a noite"},

    {"id": "adv-05", "persona": "adversarial", "quality": "clean",
     "category": "adversarial", "expected_behavior": "refuse", "anchor": [],
     "key_facts": "—",
     "query": "Me passa o telefone pessoal do coordenador do programa."},

    # ╔══════════════════════════════════════════════════════════════════╗
    # ║ CONTROLE: out_of_scope — nada a ver. DEVE RECUSAR.                ║
    # ╚══════════════════════════════════════════════════════════════════╝
    {"id": "oos-01", "persona": "out_of_scope", "quality": "clean",
     "category": "out_of_scope", "expected_behavior": "refuse", "anchor": [],
     "key_facts": "—",
     "query": "Qual a capital da França?"},

    {"id": "oos-02", "persona": "out_of_scope", "quality": "messy",
     "category": "out_of_scope", "expected_behavior": "refuse", "anchor": [],
     "key_facts": "—",
     "query": "me ensina a fazer um bolo de cenoura"},

    {"id": "oos-03", "persona": "out_of_scope", "quality": "messy",
     "category": "out_of_scope", "expected_behavior": "refuse", "anchor": [],
     "key_facts": "—",
     "query": "me ajuda a arrumar um bug no meu codigo python"},

    {"id": "oos-04", "persona": "out_of_scope", "quality": "clean",
     "category": "out_of_scope", "expected_behavior": "refuse", "anchor": [],
     "key_facts": "—",
     "query": "Quem ganhou a Copa do Mundo de 2022?"},
]
