"""
Transcrição e análise de gravação de consulta por IA.

Duas etapas, dois serviços diferentes: a OpenAI (Whisper) transcreve o
áudio pra texto; a Anthropic (Claude) lê essa transcrição e extrai as
queixas/dores que a paciente relatou. Sem as chaves configuradas
(OPENAI_API_KEY / ANTHROPIC_API_KEY), levanta ServicoIAIndisponivel em vez
de tentar e quebrar com um erro confuso — view trata isso como mensagem
pra administradora, não como bug.
"""

from django.conf import settings

MODELO_ANALISE = "claude-opus-5-5"

PROMPT_SISTEMA_ANALISE = (
    "Você é uma assistente clínica de uma clínica de tratamento de melasma/manchas "
    "de pele. Vai receber a transcrição de uma consulta. Leia com atenção e liste, "
    "em tópicos curtos, as queixas, dores e sintomas que a PACIENTE relatou durante "
    "a consulta — sintomas de pele, digestivos, hormonais, emocionais, de sono, "
    "qualquer coisa que ela tenha mencionado que a incomoda ou preocupa. "
    "Cite só o que foi dito de verdade na consulta, sem inventar ou presumir nada "
    "que não esteja na transcrição. Se a transcrição não tiver queixas claras, diga "
    "isso explicitamente em vez de forçar uma lista. Responda só com a lista, sem "
    "introdução nem comentário final."
)


class ServicoIAIndisponivel(Exception):
    """A chave de API necessária não está configurada no ambiente."""


def transcrever_audio(arquivo):
    """
    `arquivo` é um objeto tipo arquivo já aberto em modo binário (ex.:
    FieldFile.open("rb")) — a OpenAI usa o nome dele só pra inferir o
    formato, não precisa ser um caminho de disco de verdade.
    """
    if not settings.OPENAI_API_KEY:
        raise ServicoIAIndisponivel(
            "OPENAI_API_KEY não configurada — peça pra administradora configurar essa "
            "variável de ambiente no Railway antes de usar a transcrição."
        )
    from openai import OpenAI

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    resposta = client.audio.transcriptions.create(model="whisper-1", file=arquivo)
    return resposta.text


def extrair_dores(transcricao):
    if not settings.ANTHROPIC_API_KEY:
        raise ServicoIAIndisponivel(
            "ANTHROPIC_API_KEY não configurada — peça pra administradora configurar essa "
            "variável de ambiente no Railway antes de usar a análise."
        )
    import anthropic

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    resposta = client.messages.create(
        model=MODELO_ANALISE,
        max_tokens=2000,
        system=PROMPT_SISTEMA_ANALISE,
        messages=[{"role": "user", "content": transcricao}],
    )
    return next((bloco.text for bloco in resposta.content if bloco.type == "text"), "")


def processar_gravacao(gravacao):
    """
    Transcreve e analisa uma GravacaoConsulta, atualizando o próprio
    registro (status, transcrição, dores ou erro). Não levanta exceção pra
    fora — qualquer problema vira GravacaoConsulta.Status.ERRO com o
    detalhe salvo, pra aparecer na tela em vez de estourar um 500.
    """
    gravacao.status = gravacao.Status.PROCESSANDO
    gravacao.erro_detalhe = ""
    gravacao.save(update_fields=["status", "erro_detalhe"])

    try:
        gravacao.arquivo_audio.open("rb")
        try:
            transcricao = transcrever_audio(gravacao.arquivo_audio)
        finally:
            gravacao.arquivo_audio.close()

        dores = extrair_dores(transcricao)

        gravacao.transcricao = transcricao
        gravacao.dores_identificadas = dores
        gravacao.status = gravacao.Status.CONCLUIDA
        gravacao.save(update_fields=["transcricao", "dores_identificadas", "status"])
    except ServicoIAIndisponivel as exc:
        gravacao.status = gravacao.Status.ERRO
        gravacao.erro_detalhe = str(exc)
        gravacao.save(update_fields=["status", "erro_detalhe"])
        raise
    except Exception as exc:
        gravacao.status = gravacao.Status.ERRO
        gravacao.erro_detalhe = f"Erro inesperado: {exc}"
        gravacao.save(update_fields=["status", "erro_detalhe"])
        raise
