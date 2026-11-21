# Ética e Impactos da Inteligência Artificial

UDF Centro Universitário · Inteligência Artificial e LFA · Profa. Kadidja Valéria
Aula de 17/11/2026
Projeto: Assistente de IA Caça Asteroides MCTI (https://github.com/Luissantos20/caca-asteroides-rag)
Integrantes: Luís Filipe Silva Santos (RGM: 37049887) e Luana Stoinski (RGM: 36872580)

## 1. Leitura e vídeo

### Artigo

LACERDA JÚNIOR, Francisco Pires de. Da proibição à governança: uso ético da inteligência artificial generativa na educação superior — uma revisão integrativa (2023–2026). *Revista Foco*, v. 19, n. 8, e12330, p. 1-18, 2026. DOI: 10.54751/revistafoco.v19n8-017.

**Questão de integridade acadêmica:** como declarar o uso de IA de forma que o professor consiga avaliar o que foi feito por nós e o que teve apoio da ferramenta?

O artigo responde que dizer só "utilizei IA" não basta. A declaração precisa registrar "ferramenta, finalidade, partes apoiadas e procedimento de verificação" (p. 10), e o autor lista três requisitos mínimos: autoria humana responsável, rastreabilidade do uso e capacidade de explicar as decisões apresentadas (p. 10). Ele também lembra que a responsabilidade não passa para a ferramenta: o usuário continua responsável pelo que assina (p. 5-6).

No nosso caso isso pesa porque o projeto já existia antes desta avaliação, e usamos IA para estudar como ele se enquadra no conceito de sistema especialista. Por isso a seção 4 separa o uso de IA dentro do sistema do uso de IA na elaboração do trabalho, e diz o que foi conferido em cada um.

### Vídeo

*O Estado da Arte em Ética na Inteligência Artificial*, IEA-USP, 9/6/2026 (lançamento do *Palgrave Handbook on the Ethics of Artificial Intelligence*).

**Trecho:** 1h53min. O palestrante diz, em paráfrase: "precisamos dar um passo atrás e pensar por que eu quero programar isso, quais são os objetivos desta programação e quais são os instrumentos éticos que estou aplicando para garantir estratégias de mitigação de resultados negativos".

**Ideia para o debate:** antes de construir, perguntar para que o sistema existe e como ele evita causar dano. No nosso projeto, o objetivo é tirar dúvidas dos participantes sem passar informação errada, e o instrumento de mitigação são as regras que impedem o sistema de responder quando o material oficial não sustenta a resposta.

## 2. Análise ética do projeto

O assistente responde dúvidas dos participantes do Programa Caça Asteroides MCTI, um programa real de ciência cidadã do MCTI e da AEB com o IASC/NASA. Ele foi criado para reduzir os e-mails repetidos que a coordenação recebia sobre inscrição, edital, o software Astrometrica e certificados. Quem usa são professores e estudantes participantes, muitos deles menores de idade. As respostas podem afetar a equipe do participante, que precisa seguir prazos e regras do edital, e a coordenação, que responde pelo programa.

O sistema foi construído para não inventar. Ele só responde com trechos do material oficial e, antes de responder, passa por duas regras: a pergunta precisa ser parecida com o material (R1) e um juiz precisa confirmar que os trechos encontrados respondem à pergunta (R2/R3). Se uma das duas falhar, ele não responde e encaminha a pessoa para o e-mail da coordenação.

Essa escolha segue o que o artigo diz sobre modelos de linguagem: a fluência da resposta pode esconder erros, e a saída deve ser tratada como "um rascunho probabilístico, não uma autoridade epistêmica" (p. 4-5). Por isso o modelo não decide sozinho. Ele fornece fatos (a semelhança da busca e o veredito do juiz), e quem decide se o sistema responde são as regras.

Vêm de regras definidas por nós: responder ou não, o limiar de 0,40 e o encaminhamento à coordenação. Vêm de modelos: a medida de semelhança da busca, o veredito do juiz e a redação da resposta, sempre limitada aos trechos oficiais. As regras estão em [`REGRAS.md`](REGRAS.md).

| Aspecto | Situação | Quem pode ser afetado | Medida |
|---|---|---|---|
| Privacidade e dados | O chat não tem cadastro e não pede nenhum dado pessoal, mas a pessoa pode digitar o nome ou o e-mail por conta própria. As perguntas passam pela API da OpenAI e ficam em log para calibração. | Participantes, inclusive menores. | O sistema funciona sem nenhum dado pessoal, o que segue a orientação do artigo de não enviar dados a serviços externos sem finalidade definida (p. 13). Próximo passo: aviso no chat para não digitar dados pessoais e prazo de retenção dos logs. |
| Viés e equidade | Quem escreve de forma informal ou com erros de digitação, comum entre estudantes mais novos, pode ter a pergunta encaminhada ao e-mail mais vezes do que quem usa os termos do edital. | Estudantes mais novos. | A reescrita da pergunta (R4) já reduz isso. Vamos incluir nos testes perguntas informais e comparar com as mesmas perguntas escritas formalmente. |
| Transparência | A pessoa precisa saber que fala com uma IA e de onde vem a resposta. | Participantes. | A tela inicial avisa: "Sou o assistente de IA do programa". Cada decisão fica registrada no log com a regra que disparou. Próximo passo: mostrar o documento de origem abaixo de cada resposta. |
| Supervisão e responsabilidade | Uma pergunta que o sistema não consegue responder com segurança. | Participantes e coordenação. | O sistema não arrisca: encaminha para o e-mail, onde a coordenação responde. É o que o artigo defende: o sistema apoia a tarefa preparatória, e a decisão continua "explicável e revisável" por uma pessoa com autoridade para contestar (p. 13). O botão 👍/👎 por resposta está no roadmap. |
| Impacto social | Benefício: resposta imediata, a qualquer hora, e menos e-mails para a coordenação. O ponto sensível são os prazos e as regras de eliminação do edital. | Equipes, principalmente de escolas com menos contato com a coordenação. | Perguntas sobre prazos só são respondidas quando o trecho do edital está entre as fontes; caso contrário, vão para a coordenação. |

## 3. Debate

### Dilema: quando o sistema deve responder?

| Escolha | Consequência |
|---|---|
| Responder sempre (limiar baixo, sem juiz) | Mais perguntas respondidas na hora, mas com risco de responder algo que o material oficial não cobre. |
| Responder só com segurança (limiar calibrado e juiz) | Respostas confiáveis. Algumas perguntas vão para o e-mail, mas a pessoa continua sendo atendida, agora por alguém da coordenação. |

Escolhemos a segunda. O artigo chega a uma conclusão parecida no contexto das universidades: proibir tudo não orienta a prática e liberar sem critério transfere os riscos para as pessoas (p. 15). O caminho que ele defende é tornar o uso da IA "justificável, verificável e compatível com os objetivos" (p. 1). No nosso sistema, isso quer dizer que o assistente não deixa de responder por precaução excessiva nem responde sem base: responde quando o material oficial sustenta a resposta, e essa condição foi calibrada com 89 perguntas rotuladas.

### Questão para o debate

Os logs de perguntas deveriam ser compartilhados com a coordenação? A matriz do artigo inclui o movimento "acompanhar": medir erros, equidade e confiança dos usuários e revisar as regras (p. 14). Os logs servem exatamente para isso, e mostram quais partes do edital geram mais dúvidas. Por outro lado, o movimento "proteger" pede minimizar dados (p. 14), e alguém que digitou o próprio nome ou o da escola pode ser identificado.

Nossa posição: compartilhar relatórios agregados (temas mais perguntados, taxa de encaminhamento), sem o texto bruto das perguntas.

### Reflexão individual

**Luís Filipe Silva Santos**

Eu manteria a decisão de encaminhar para a coordenação quando o sistema não tem segurança. O argumento que mais me influenciou foi a ideia do artigo de que a fluência de um modelo pode esconder erros (p. 4): um assistente que responde tudo com segurança aparente seria perigoso num programa em que um prazo errado pode eliminar uma equipe. O que eu mudaria é a transparência para o participante: hoje o caminho da decisão fica no log, que só eu vejo, e eu passaria a mostrar o documento de origem de cada resposta. Para verificar se as medidas funcionam, eu acompanharia a taxa de encaminhamentos, o número de e-mails repetidos que a coordenação ainda recebe e, quando existir, a avaliação 👍/👎 das respostas.

**Luana Stoinski**

Participei das decisões sobre as regras e da calibração, e foi nos testes que ficou claro que o score sozinho não bastava: perguntas com as palavras do programa, mas sem resposta no material, passavam. Eu manteria o juiz por isso. O que eu mudaria é o conjunto de testes, incluindo perguntas escritas como um estudante mais novo escreveria, com abreviações e erros, porque o artigo lembra que os efeitos sobre estudantes em condições diferentes ainda são pouco estudados (p. 12) e não queremos que o sistema atenda melhor quem escreve como o edital. Para verificar, eu compararia a taxa de encaminhamento das perguntas informais com a das mesmas perguntas escritas formalmente.

## 4. Declaração de uso de sistemas de IA

### IA incorporada ao projeto

O projeto utiliza os modelos `text-embedding-3-small` e `gpt-4o-mini`, da OpenAI, combinados com regras SE–ENTÃO definidas por nós, para responder dúvidas dos participantes do Programa Caça Asteroides MCTI usando apenas o material oficial do programa. O sistema recebe a pergunta do participante e, quando existe, o histórico recente da conversa, e gera uma resposta baseada nos trechos oficiais ou o encaminhamento para o e-mail da coordenação. Verificamos o funcionamento com 89 perguntas rotuladas (61 dentro do escopo, 12 adversariais, 10 fora do escopo e 6 que dependem da conversa), usando scripts que avaliam a busca, o limiar e o juiz (`backend/tests/`), e com testes de carga (`benchmark/`). As situações que exigem revisão são as perguntas que o material oficial não cobre, que o sistema encaminha à coordenação, e as mudanças de edital, que exigem atualizar a base. A revisão técnica e a atualização da base cabem a mim, e o conteúdo oficial cabe à Comissão Organizadora do programa. A Luana participou das decisões sobre as regras, da avaliação do sistema e da calibração.

### IA utilizada na elaboração do trabalho

Utilizei o Claude (Anthropic) para estudar como este projeto se enquadra no conceito de sistema especialista visto em aula e para organizar este documento e o `REGRAS.md`. O projeto já estava pronto quando a avaliação foi proposta. Ele foi desenvolvido como parte do meu estudo em engenharia de software e engenharia de IA. Durante o desenvolvimento, usei IA como apoio ao estudo: para entender decisões de arquitetura, como funciona a busca semântica e como avaliar os resultados dos testes, além de encontrar estudos e referências. Também usei IA para gerar código a partir das minhas ideias para a interface, deixando-a mais apresentável para o usuário, para comentar o código e para otimizar o sistema, reescrevendo alguns trechos. Revisei e testei esse código antes de incorporá-lo. As decisões de projeto, a calibração com dados reais e a validação foram feitas por nós. Conferi as regras, os números de linha e os dados dos testes diretamente no código do repositório, e as citações do artigo no texto original. Assumo a responsabilidade pelas escolhas, verificações e conteúdo da entrega.
