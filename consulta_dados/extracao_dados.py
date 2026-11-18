"""
Carga dos dados do projeto no MySQL (banco merc_financeiro).

Como usar (Prompt de Comando, dentro da pasta onde estao os CSVs):
    pip install pandas sqlalchemy pymysql
    python extracao_dados.py

Arquivos esperados na mesma pasta do script:
    bcdata_sgs_432.csv    -> Selic meta (diaria)
    bcdata_sgs_433.csv    -> IPCA variacao mensal (%)
    bcdata_sgs_24363.csv  -> IBC-Br (indice)
    bcdata_sgs_24369.csv  -> Taxa de desocupacao PNAD (%)
    PrecoTaxaTesouroDireto.csv (opcional) -> Tesouro Transparente
"""
import os
import glob
import sys
from urllib.parse import quote_plus
import pandas as pd
from sqlalchemy import create_engine, text

# ====== Configuracoes do Database ======
USUARIO = "root"
SENHA = "amigo1234"
HOST = "localhost"
PORTA = 3306
BANCO = "merc_financeiro"
DATA_INICIO_TESOURO = "2024-12-01"   # um mes antes da janela, para calcular variacoes
# =========================

PASTA = os.path.dirname(os.path.abspath(__file__))
engine = create_engine(
    f"mysql+pymysql://{USUARIO}:{quote_plus(SENHA)}@{HOST}:{PORTA}/{BANCO}?charset=utf8mb4"
)

# Pastas onde o script procura os CSVs
PASTAS_BUSCA = [PASTA, os.getcwd(), os.path.dirname(PASTA), os.path.join(PASTA, "dados")]


def achar_arquivo(prefixo, obrigatorio=True):
    """Procura um .csv cujo nome comece com `prefixo` (ignora maiusculas e sufixos
    como ' (1)'). Se nao achar, mostra os CSVs que existem nas pastas buscadas."""
    for pasta in PASTAS_BUSCA:
        for caminho in sorted(glob.glob(os.path.join(pasta, "*.csv"))):
            # aceita bcdata_sgs_432.csv, bcdata.sgs.432.csv, bcdata-sgs-432.csv etc.
            nome = os.path.basename(caminho).lower().replace(".", "_").replace("-", "_")
            if nome.startswith(prefixo.lower().replace(".", "_")):
                return caminho
    if obrigatorio:
        print(f"\nERRO: nao encontrei nenhum arquivo '{prefixo}*.csv'. Pastas procuradas:")
        for pasta in PASTAS_BUSCA:
            if os.path.isdir(pasta):
                arqs = [a for a in os.listdir(pasta) if "csv" in a.lower()]
                print(f"  - {pasta}  ->  {arqs if arqs else 'nenhum csv'}")
            else:
                print(f"  - {pasta}  ->  (pasta nao existe)")
        sys.exit(1)
    return None

SERIES = {
    432:   ("selic_meta",   "Meta da taxa Selic",                   "% a.a.",  "diaria"),
    433:   ("ipca_mensal",  "IPCA - variacao mensal",               "%",       "mensal"),
    24363: ("ibc_br",       "IBC-Br (indice de atividade)",         "indice",  "mensal"),
    24369: ("desocupacao",  "Taxa de desocupacao (PNAD Continua)",  "%",       "mensal"),
}

DDL = [
    """CREATE TABLE IF NOT EXISTS serie_def (
        codigo_serie INT PRIMARY KEY,
        nome         VARCHAR(40)  NOT NULL,
        descricao    VARCHAR(100) NOT NULL,
        unidade      VARCHAR(20),
        frequencia   VARCHAR(10)
    )""",
    """CREATE TABLE IF NOT EXISTS serie_macro (
        codigo_serie INT  NOT NULL,
        data         DATE NOT NULL,
        valor        DECIMAL(18,6) NOT NULL,
        PRIMARY KEY (codigo_serie, data),
        INDEX idx_data (data),
        FOREIGN KEY (codigo_serie) REFERENCES serie_def(codigo_serie)
    )""",
    """CREATE TABLE IF NOT EXISTS titulo_tesouro (
        tipo_titulo VARCHAR(60) NOT NULL,
        vencimento  DATE NOT NULL,
        data_base   DATE NOT NULL,
        taxa_compra DECIMAL(10,4),
        taxa_venda  DECIMAL(10,4),
        pu_compra   DECIMAL(14,4),
        pu_venda    DECIMAL(14,4),
        pu_base     DECIMAL(14,4),
        PRIMARY KEY (tipo_titulo, vencimento, data_base),
        INDEX idx_data_base (data_base)
    )""",
]


def carregar_series():
    with engine.begin() as con:
        for cod, (nome, desc, un, freq) in SERIES.items():
            con.execute(text(
                "REPLACE INTO serie_def VALUES (:c, :n, :d, :u, :f)"),
                {"c": cod, "n": nome, "d": desc, "u": un, "f": freq})
        con.execute(text("DELETE FROM serie_macro"))

    partes = []
    for cod in SERIES:
        arq = achar_arquivo(f"bcdata_sgs_{cod}")
        df = pd.read_csv(arq, sep=";", decimal=",", encoding="utf-8-sig")
        df.columns = ["data", "valor"]
        df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y").dt.date
        df["codigo_serie"] = cod
        partes.append(df[["codigo_serie", "data", "valor"]])
        print(f"serie {cod}: {len(df)} linhas")
    pd.concat(partes).to_sql("serie_macro", engine, if_exists="append", index=False)


def carregar_tesouro():
    arq = achar_arquivo("PrecoTaxaTesouroDireto", obrigatorio=False)
    if arq is None:
        print("PrecoTaxaTesouroDireto.csv nao encontrado - pulando Tesouro.")
        return
    df = pd.read_csv(arq, sep=";", decimal=",", encoding="utf-8-sig")
    print("Colunas do arquivo do Tesouro:", list(df.columns))
    # Mapeia pela posicao (ordem padrao do arquivo do Tesouro Transparente)
    df = df.iloc[:, :8]
    df.columns = ["tipo_titulo", "vencimento", "data_base", "taxa_compra",
                  "taxa_venda", "pu_compra", "pu_venda", "pu_base"]
    df["vencimento"] = pd.to_datetime(df["vencimento"], format="%d/%m/%Y")
    df["data_base"] = pd.to_datetime(df["data_base"], format="%d/%m/%Y")
    df = df[df["data_base"] >= DATA_INICIO_TESOURO]
    df = df.drop_duplicates(["tipo_titulo", "vencimento", "data_base"])
    with engine.begin() as con:
        con.execute(text("DELETE FROM titulo_tesouro"))
    df.to_sql("titulo_tesouro", engine, if_exists="append", index=False, chunksize=5000)
    print(f"tesouro: {len(df)} linhas")


if __name__ == "__main__":
    with engine.begin() as con:
        for ddl in DDL:
            con.execute(text(ddl))
    carregar_series()
    carregar_tesouro()
    print("Carga concluida.")
