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


# --- Texto colado (extrato copiado de um PDF/internet banking) -------------
# Formato específico do "HISTÓRICO DE MOVIMENTAÇÃO" do Sicoob (e parecido com
# o de outros bancos): uma linha "DD/MM <TIPO> VALOR,00C" ou "...D" (crédito/
# débito), seguida de 1-4 linhas de detalhe (ex.: "Recebimento Pix", nome de
# quem pagou, CPF/CNPJ mascarado, "DOC.: Pix") até a próxima transação. Só
# interessa achar os créditos (dinheiro que entrou) e, se der, o nome de quem
# pagou — não tenta entender todo tipo de lançamento do extrato.
_LINHA_TRANSACAO_RE = re.compile(r"^(\d{2}/\d{2})\s*(.+?)\s+([\d.,]+)\s*([CD])\*?\s*$")
_LINHA_IGNORAR_RE = re.compile(r"^(doc\.?:|recebimento pix|transfer[eê]ncia pix|pagamento pix|\*{2,}\.|rem\.:|fav\.:)", re.IGNORECASE)


def extrair_texto_pdf(conteudo):
    """
    Extrai o texto de um PDF de extrato (ex.: exportado do internet banking
    ou enviado por e-mail), página por página, pra passar pro
    extrair_creditos_colados — evita a pessoa ter que copiar e colar o texto
    na mão. Só funciona com PDF que tem texto de verdade (a maioria dos
    extratos bancários é assim); um PDF escaneado como imagem não tem texto
    pra extrair, e isso vira um ValueError claro em vez de devolver vazio.
    """
    from pypdf import PdfReader

    leitor = PdfReader(io.BytesIO(conteudo))
    texto = "\n".join((pagina.extract_text() or "") for pagina in leitor.pages)
    if not texto.strip():
        raise ValueError("não consegui ler texto desse PDF (pode ser um PDF escaneado, sem texto de verdade).")
    return texto


def extrair_creditos_colados(texto, ano):
    """
    Varre um texto colado (copiado do extrato em PDF ou da tela do banco) e
    devolve só as linhas de CRÉDITO (dinheiro que entrou), cada uma com data,
    valor, o "tipo" cru da linha (pra separar Pix direto de repasse de
    maquininha) e, quando dá pra achar, o nome de quem pagou (a primeira
    linha de detalhe que não é claramente um rótulo/documento/CPF mascarado).
    Ignora "SALDO ANTERIOR"/"SALDO DO DIA" (não são transações).
    """
    linhas = [l.strip() for l in texto.splitlines()]
    creditos = []
    for indice, linha in enumerate(linhas):
        m = _LINHA_TRANSACAO_RE.match(linha)
        if not m:
            continue
        data_str, tipo, valor_str, sinal = m.groups()
        tipo = tipo.strip()
        if "SALDO" in tipo.upper() or sinal != "C":
            continue
        try:
            dia, mes = int(data_str[:2]), int(data_str[3:5])
            data = datetime.date(ano, mes, dia)
        except ValueError:
            continue
        try:
            valor = _parse_valor_brl(valor_str)
        except (ValueError, InvalidOperation):
            continue

        nome = ""
        for prox in linhas[indice + 1:indice + 6]:
            if not prox:
                continue
            if _LINHA_TRANSACAO_RE.match(prox):
                break
            if _LINHA_IGNORAR_RE.match(prox):
                continue
            nome = prox
            break

        creditos.append({"data": data, "valor": valor, "tipo": tipo.upper(), "nome": nome})
    return creditos


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
