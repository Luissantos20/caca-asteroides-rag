"""
═══════════════════════════════════════════════════════════════════════
  DATASET MULTI-TURN — Caça Asteroides (teste de memória / rewrite_query)
═══════════════════════════════════════════════════════════════════════

OBJETIVO: provar (ou inocentar) a hipótese de que o histórico faz o
rewrite_query reescrever a pergunta de forma enviesada, quebrando a busca.

MÉTODO: fixar a PERGUNTA FINAL (`query`) e variar o HISTÓRICO na frente.
Se o desfecho muda conforme o histórico, a causa é o histórico.

FIDELIDADE AO SISTEMA REAL (confirmado no chat.py + schemas/chat.py):
- A pergunta atual vai em `query` (campo `message` da API), SEPARADA.
- `history` é a lista de mensagens ANTERIORES — NÃO inclui a pergunta atual.
- history termina sempre numa fala do ASSISTENTE (a próxima fala é o `query`).
- Limites do schema respeitados: history ≤ 10 mensagens; cada content ≤ 4000 chars.
- O rewrite_query só olha as ÚLTIMAS 4 mensagens do histórico.

TAGS:
  scenario : A_control | B_same_topic | C_topic_switch | D_reference | continuity
  persona  : de onde vem a pergunta final
  target   : a intenção da pergunta final (pra agrupar A/B/C/D da mesma pergunta)

COMO LER:
  - Compare o MESMO `target` entre A_control e C_topic_switch.
  - Olhe a `rewritten_query` capturada: o que o rewrite fez com a pergunta?
  - Rode com --repeat 3 (a falha é intermitente; 1 rodada pode não pegá-la).
"""

# Históricos reutilizáveis (sempre terminam no ASSISTENTE) ──────────────

H_SOFTWARE = [
    {"role": "user", "content": "o astrometrica ta pedindo uma licença"},
    {"role": "assistant", "content": "Para registrar o Astrometrica, acesse Help > Registration e insira a License 'IASC' e a Key enviada por e-mail ao líder da equipe."},
    {"role": "user", "content": "e agora deu runtime error quando abri"},
    {"role": "assistant", "content": "Esse erro costuma ser falta da pasta de dados local. Abra Executar (Windows+R), digite %LOCALAPPDATA% e crie uma pasta chamada exatamente 'Astrometrica'."},
]

H_CERTIFICADO = [
    {"role": "user", "content": "qual a diferença entre certificado e medalha?"},
    {"role": "assistant", "content": "O certificado é digital e vai para todos que enviarem os relatórios corretamente. A medalha é física e só para equipes com ao menos uma detecção confirmada."},
]

H_GLOSSARIO = [
    {"role": "user", "content": "o que é blink comparison?"},
    {"role": "assistant", "content": "É a técnica de alternar rapidamente entre as imagens para perceber objetos que se movem, como asteroides."},
    {"role": "user", "content": "e falsa assinatura?"},
    {"role": "assistant", "content": "É um artefato que parece um asteroide mas não deve ser reportado, como pixels quentes, satélites ou spikes de difração."},
]

H_INSCRICAO = [
    {"role": "user", "content": "quando abrem as inscrições de 2026?"},
    {"role": "assistant", "content": "As inscrições abrem a partir de 06/03/2026 às 13h (horário de Brasília), por campanha."},
]

H_PROGRAMA = [
    {"role": "user", "content": "o que é o caça asteroides?"},
    {"role": "assistant", "content": "É um programa de ciência cidadã do MCTI em parceria com o IASC/NASA, onde você analisa imagens reais com o software Astrometrica para detectar asteroides. É gratuito."},
]

H_MPC = [
    {"role": "user", "content": "o que é o relatório MPC?"},
    {"role": "assistant", "content": "É o arquivo de texto gerado pelo Astrometrica com as medições dos objetos (data, RA, Dec, magnitude), que é enviado ao IASC."},
]

H_RESET = [
    {"role": "user", "content": "o que é reset files?"},
    {"role": "assistant", "content": "É a função do Astrometrica que limpa o relatório atual para você começar a análise de um novo image set."},
]

H_CERT_COMO = [
    {"role": "user", "content": "como pego o certificado?"},
    {"role": "assistant", "content": "Ao fim da campanha, o líder identifica quem participou e os participantes solicitam o certificado na plataforma do IASC."},
]

H_CAMPANHA_MAIO = [
    {"role": "user", "content": "tem campanha em maio?"},
    {"role": "assistant", "content": "Sim, a Campanha 3 vai de 11/05 a 05/06/2026."},
]


CASES = [

    # ═══ ALVO 1: "como participo?" — a estrela (curta e vaga) ═══════════
    {"id": "mt-cp-A", "target": "como_participo", "scenario": "A_control",
     "persona": "inscricao", "expected_behavior": "answer", "history": [],
     "anchor": ["DOC02-FCP-02", "DOC05-CHUNK-04"],
     "key_facts": "inscrição pelo líder via formulário; passo a passo",
     "query": "como participo?"},

    {"id": "mt-cp-B", "target": "como_participo", "scenario": "B_same_topic",
     "persona": "inscricao", "expected_behavior": "answer", "history": H_INSCRICAO,
     "anchor": ["DOC02-FCP-02"],
     "key_facts": "deve responder sobre inscrição; histórico é do mesmo tema",
     "query": "como participo?"},

    {"id": "mt-cp-C1", "target": "como_participo", "scenario": "C_topic_switch",
     "persona": "inscricao", "expected_behavior": "answer", "history": H_SOFTWARE,
     "anchor": ["DOC02-FCP-02"],
     "key_facts": "SUSPEITO: histórico de software; rewrite pode arrastar Astrometrica",
     "query": "como participo?"},

    {"id": "mt-cp-C2", "target": "como_participo", "scenario": "C_topic_switch",
     "persona": "inscricao", "expected_behavior": "answer", "history": H_CERTIFICADO,
     "anchor": ["DOC02-FCP-02"],
     "key_facts": "SUSPEITO: histórico de certificado",
     "query": "como participo?"},

    {"id": "mt-cp-C3", "target": "como_participo", "scenario": "C_topic_switch",
     "persona": "inscricao", "expected_behavior": "answer", "history": H_GLOSSARIO,
     "anchor": ["DOC02-FCP-02"],
     "key_facts": "SUSPEITO: histórico de glossário (blink/falsa assinatura)",
     "query": "como participo?"},

    {"id": "mt-cp-D", "target": "como_participo", "scenario": "D_reference",
     "persona": "inscricao", "expected_behavior": "answer", "history": H_PROGRAMA,
     "anchor": ["DOC02-FCP-02"],
     "key_facts": "rewrite DEVE ajudar: 'nisso' → participar do caça asteroides",
     "query": "e como eu entro nisso?"},

    # ═══ ALVO 2: inscrição (formulação completa) ═══════════════════════
    {"id": "mt-insc-A", "target": "inscrever", "scenario": "A_control",
     "persona": "inscricao", "expected_behavior": "answer", "history": [],
     "anchor": ["DOC02-FCP-02"], "key_facts": "como inscrever a equipe",
     "query": "quero me inscrever, como faço?"},

    {"id": "mt-insc-C", "target": "inscrever", "scenario": "C_topic_switch",
     "persona": "inscricao", "expected_behavior": "answer", "history": H_SOFTWARE,
     "anchor": ["DOC02-FCP-02"], "key_facts": "SUSPEITO: histórico de software",
     "query": "quero me inscrever, como faço?"},

    {"id": "mt-insc-cont", "target": "custo", "scenario": "continuity",
     "persona": "visao_geral", "expected_behavior": "answer", "history": H_INSCRICAO,
     "anchor": ["DOC01-VGP-13", "DOC05-CHUNK-09"],
     "key_facts": "follow-up natural; deve responder que é gratuito",
     "query": "e quanto custa?"},

    # ═══ ALVO 3: elegibilidade ═════════════════════════════════════════
    {"id": "mt-eleg-A", "target": "elegibilidade", "scenario": "A_control",
     "persona": "regras_faq", "expected_behavior": "answer", "history": [],
     "anchor": ["DOC05-CHUNK-02"], "key_facts": "qualquer um pode participar",
     "query": "qualquer um pode participar?"},

    {"id": "mt-eleg-C", "target": "elegibilidade", "scenario": "C_topic_switch",
     "persona": "regras_faq", "expected_behavior": "answer", "history": H_MPC,
     "anchor": ["DOC05-CHUNK-02"], "key_facts": "SUSPEITO: histórico de relatório MPC",
     "query": "qualquer um pode participar?"},

    {"id": "mt-eleg-vague", "target": "crianca", "scenario": "C_topic_switch",
     "persona": "regras_faq", "expected_behavior": "answer", "history": H_CERTIFICADO,
     "anchor": ["DOC05-CHUNK-02"], "key_facts": "criança pode (≥6 anos)",
     "query": "criança pode?"},

    # ═══ ALVO 4: software (continuidade e referência) ══════════════════
    {"id": "mt-sw-ref", "target": "gerar_mpc", "scenario": "D_reference",
     "persona": "software", "expected_behavior": "answer", "history": H_MPC,
     "anchor": ["DOC06-QSG-15"],
     "key_facts": "rewrite DEVE resolver 'ele' → relatório MPC",
     "query": "e como eu gero ele?"},

    {"id": "mt-sw-ref2", "target": "usar_reset", "scenario": "D_reference",
     "persona": "software", "expected_behavior": "answer", "history": H_RESET,
     "anchor": ["DOC06-QSG-39"],
     "key_facts": "rewrite DEVE resolver 'isso' → reset files; quando usar",
     "query": "e quando eu uso isso?"},

    {"id": "mt-sw-C", "target": "instalar_astrometrica", "scenario": "C_topic_switch",
     "persona": "software", "expected_behavior": "answer", "history": H_INSCRICAO,
     "anchor": ["DOC06-QSG-03"], "key_facts": "SUSPEITO inverso: histórico de inscrição",
     "query": "como instalo o astrometrica?"},

    # ═══ ALVO 5: links / certificado (referência natural) ══════════════
    {"id": "mt-link-ref", "target": "link_campanha", "scenario": "D_reference",
     "persona": "inscricao", "expected_behavior": "answer", "history": H_CAMPANHA_MAIO,
     "anchor": ["DOC05-CHUNK-15", "DOC04-LCU-10"],
     "key_facts": "rewrite DEVE resolver 'dela' → campanha de maio",
     "query": "e qual o link dela?"},

    {"id": "mt-cert-ref", "target": "validade_cert", "scenario": "D_reference",
     "persona": "regras_faq", "expected_behavior": "answer", "history": H_CERT_COMO,
     "anchor": ["DOC05-CHUNK-36"],
     "key_facts": "rewrite DEVE resolver 'ele' → certificado; validade",
     "query": "e ele tem validade?"},

    # ═══ CONTROLES em multi-turn: NÃO pode alucinar com histórico ══════
    {"id": "mt-adv-C", "target": "adversarial", "scenario": "C_topic_switch",
     "persona": "adversarial", "expected_behavior": "refuse", "history": H_INSCRICAO,
     "anchor": [], "key_facts": "—",
     "query": "qual asteroide a minha equipe descobriu?"},

    {"id": "mt-oos-C", "target": "out_of_scope", "scenario": "C_topic_switch",
     "persona": "out_of_scope", "expected_behavior": "refuse", "history": H_SOFTWARE,
     "anchor": [], "key_facts": "—",
     "query": "qual a capital da frança?"},
]
