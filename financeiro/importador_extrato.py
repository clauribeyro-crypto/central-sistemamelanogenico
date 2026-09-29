"""
Leitura de extratos bancários (OFX ou CSV) pra importar como Lançamento em
lote, em vez de digitar cada conta na mão. Não depende de nenhuma lib
externa — bancos brasileiros variam demais no formato do CSV pra confiar
numa lib genérica, então o parser aqui é tolerante por design (várias
grafias de coluna, várias formatações de data/valor) e qualquer linha que
não der pra entender é simplesmente pulada, não derruba a importação.
"""

import csv
import datetime
import io
import re
import unicodedata
from decimal import Decimal, InvalidOperation


def _decode(conteudo):
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return conteudo.decode(encoding)
        except UnicodeDecodeError:
            continue
    return conteudo.decode("latin-1", errors="replace")


def _strip_acentos(texto):
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


# --- OFX -----------------------------------------------------------------
# OFX 1.x (SGML) normalmente não fecha as tags de valor (<TRNAMT>-10.00 sem
# </TRNAMT>), só as de agregado (<STMTTRN>...</STMTTRN> sempre fecha, nas
# duas versões) — por isso dá pra usar sempre a mesma extração de blocos.
_STMTTRN_RE = re.compile(r"<STMTTRN>(.*?)</STMTTRN>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<(\w+)>\s*([^<\r\n]*)")


def parse_ofx(conteudo):
    texto = _decode(conteudo)
    transacoes = []
    for bloco in _STMTTRN_RE.findall(texto):
        campos = {m.group(1).upper(): m.group(2).strip() for m in _TAG_RE.finditer(bloco)}
        dtposted, trnamt = campos.get("DTPOSTED"), campos.get("TRNAMT")
        if not dtposted or not trnamt:
            continue
        try:
            data = datetime.datetime.strptime(dtposted[:8], "%Y%m%d").date()
            valor = Decimal(trnamt.replace(",", "."))
        except (ValueError, InvalidOperation):
            continue
        descricao = campos.get("MEMO") or campos.get("NAME") or "Transação importada"
        transacoes.append({"data": data, "valor": valor, "descricao": descricao})
    return transacoes


# --- CSV -------------------------------------------------------------------
_COLUNAS_DATA = {"data", "date", "dt"}
_COLUNAS_VALOR = {"valor", "value", "amount", "vl", "valorr", "valorbrl"}
_COLUNAS_DESCRICAO = {"descricao", "description", "historico", "memo", "lancamento", "detalhes", "title"}


def _normalizar_cabecalho(nome):
    return re.sub(r"[^a-z0-9]", "", _strip_acentos(nome).strip().lower())


def _parse_valor_brl(bruto):
    texto = bruto.strip().replace("R$", "").replace(" ", "")
    if not texto:
        raise ValueError("valor vazio")
    negativo = texto.startswith("-") or (texto.startswith("(") and texto.endswith(")"))
    texto = texto.strip("-()")
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:
        texto = texto.replace(",", ".")
    valor = Decimal(texto)
    return -valor if negativo else valor


def _parse_data_flexivel(bruto):
    texto = bruto.strip()
    for formato in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"):
        try:
            return datetime.datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    raise ValueError(f"data não reconhecida: {bruto}")


def parse_csv(conteudo):
    texto = _decode(conteudo)
    amostra = texto[:2048]
    delimitador = ";" if amostra.count(";") >= amostra.count(",") else ","
    try:
        delimitador = csv.Sniffer().sniff(amostra, delimiters=";,").delimiter
    except csv.Error:
        pass

    leitor = csv.DictReader(io.StringIO(texto), delimiter=delimitador)
    if not leitor.fieldnames:
        raise ValueError("não consegui identificar as colunas do arquivo.")

    mapa = {}
    for campo in leitor.fieldnames:
        chave = _normalizar_cabecalho(campo)
        if chave in _COLUNAS_DATA and "data" not in mapa:
            mapa["data"] = campo
        elif chave in _COLUNAS_VALOR and "valor" not in mapa:
            mapa["valor"] = campo
        elif chave in _COLUNAS_DESCRICAO and "descricao" not in mapa:
            mapa["descricao"] = campo

    if "data" not in mapa or "valor" not in mapa:
        raise ValueError(
            "não encontrei colunas de data e valor no arquivo. Colunas encontradas: "
            + ", ".join(leitor.fieldnames)
        )

    transacoes = []
    for linha in leitor:
        bruto_data = linha.get(mapa["data"], "")
        bruto_valor = linha.get(mapa["valor"], "")
        if not bruto_data or not bruto_valor:
            continue
        try:
            data = _parse_data_flexivel(bruto_data)
            valor = _parse_valor_brl(bruto_valor)
        except (ValueError, InvalidOperation):
            continue
        descricao = (linha.get(mapa.get("descricao"), "") or "").strip() or "Transação importada"
        transacoes.append({"data": data, "valor": valor, "descricao": descricao})
    return transacoes


def parse_extrato(nome_arquivo, conteudo):
    if nome_arquivo.lower().endswith(".ofx"):
        return parse_ofx(conteudo)
    return parse_csv(conteudo)


# --- Sugestão de categoria --------------------------------------------------
# Só uma ajuda pra não ter que escolher a categoria de cada linha do zero —
# casa palavras comuns de extrato bancário com o *nome* das categorias que a
# própria clínica já cadastrou (ex.: descrição "ENERGISA MG" + categoria
# "Energia" cadastrada → sugere ela). Nunca aplica sozinho, só pré-seleciona.
_PISTAS_POR_PALAVRA = [
    (("energisa", "cemig", "light sa", "enel", "cpfl", "copel", "coelba"), "energia"),
    (("internet", "vivo", "claro", "net ", "oi fibra", "telefonica", "tim "), "internet"),
    (("darf", "imposto", "receita federal", "irpj", "simples nacional", "iss "), "imposto"),
    (("tarifa", "iof", "anuidade", "manutencao de conta", "juros"), "juros"),
    (("facebook", "meta ads", "google ads", "instagram", "ads ", "anuncio", "marketing"), "marketing"),
    (("pro-labore", "prolabore", "pro labore"), "prolabore"),
]


def sugerir_categoria(descricao, categorias):
    texto = _strip_acentos(descricao).lower()
    for palavras, pista in _PISTAS_POR_PALAVRA:
        if any(p in texto for p in palavras):
            for categoria in categorias:
                if pista in _strip_acentos(categoria.nome).lower():
                    return categoria
    return None
