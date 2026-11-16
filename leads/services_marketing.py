"""
Leitura da planilha de campanhas do Meta Ads (CSV publicado do Google
Sheets) usada no painel de Marketing — investimento por campanha, pra somar
no total do período e montar a tabela "Por funil de campanha".
"""

import csv
import decimal
import io

import requests
from django.utils.dateparse import parse_date


class PlanilhaCampanhasIndisponivel(Exception):
    """A planilha não está configurada pra essa organização, ou não deu pra buscar/ler."""


def _parse_valor(texto):
    texto = (texto or "").strip()
    if not texto:
        return decimal.Decimal("0")
    texto = texto.replace("R$", "").strip().replace(".", "").replace(",", ".")
    try:
        return decimal.Decimal(texto)
    except decimal.InvalidOperation:
        return decimal.Decimal("0")


def _parse_data(texto):
    texto = (texto or "").strip()
    partes = texto.split("/")
    if len(partes) != 3:
        return None
    dia, mes, ano = partes
    try:
        return parse_date(f"{ano}-{mes}-{dia}")
    except ValueError:
        return None


def buscar_linhas_campanhas(url, data_inicio, data_fim, timeout=10):
    """
    Busca a planilha (CSV publicado) e devolve uma linha por
    campanha/dia dentro do período pedido: {"data", "campanha", "investimento"}.
    Levanta PlanilhaCampanhasIndisponivel se não tiver link configurado ou a
    busca/leitura falhar — quem chama decide como avisar.
    """
    if not url:
        raise PlanilhaCampanhasIndisponivel(
            "Nenhuma planilha de campanhas configurada pra essa organização "
            "(configure em /admin/ → Organizações → Marketing)."
        )
    try:
        resposta = requests.get(url, timeout=timeout)
        resposta.raise_for_status()
    except requests.RequestException as exc:
        raise PlanilhaCampanhasIndisponivel(f"Não deu pra buscar a planilha de campanhas: {exc}") from exc

    try:
        texto = resposta.content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise PlanilhaCampanhasIndisponivel(f"Não deu pra ler a planilha de campanhas: {exc}") from exc

    leitor = csv.DictReader(io.StringIO(texto))
    if not leitor.fieldnames or "Data" not in leitor.fieldnames or "Campanha" not in leitor.fieldnames:
        raise PlanilhaCampanhasIndisponivel(
            "A planilha de campanhas não tem as colunas esperadas (\"Data\", \"Campanha\", \"Investimento\")."
        )

    linhas = []
    for linha in leitor:
        data = _parse_data(linha.get("Data"))
        if data is None or data < data_inicio or data > data_fim:
            continue
        campanha = (linha.get("Campanha") or "").strip()
        if not campanha:
            continue
        linhas.append({
            "data": data,
            "campanha": campanha,
            # "OUTCOME_LEADS" é o objetivo de campanha de captação de lead no
            # Meta Ads — usado pra não deixar uma campanha de outro tipo
            # (ex.: "[MPA] [CAPTAÇÃO DE SEGUIDORES]...", que é engajamento/
            # tráfego, não captação de lead de verdade) bater sem querer
            # com o texto de uma Origem só porque contém a palavra "Captação".
            "objetivo": (linha.get("Objetivo") or "").strip(),
            "investimento": _parse_valor(linha.get("Investimento")),
        })
    return linhas
