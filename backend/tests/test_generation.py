import json
from services.pipeline import rag_pipeline


TEST_QUERIES = [
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


def run_tests():
    results = []
    for query in TEST_QUERIES:
        print("\n" + "="*80)
        print(f"PERGUNTA: {query}")

        response = rag_pipeline(query, debug=True)

        print("\n→ SHOULD ANSWER:", response["should_answer"])
        print("→ ANSWER:", response["answer"])

        print("\n--- CHUNKS ---")
        for i, c in enumerate(response["chunks"], 1):
            print(f"\n[{i}] {c['category']}")
            print(c["content"][:200], "...")

        results.append({
            "query": query,
            "should_answer": response["should_answer"],
            "answer": response["answer"],
            "chunks": response.get("chunks", []),
            "n_chunks": len(response.get("chunks", []))
        })

    with open(
        "generation_results.json",
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            results,
            f,
            ensure_ascii=False,
            indent=2
        )

if __name__ == "__main__":
    run_tests()
