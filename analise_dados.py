"""
Analise da relacao entre indicadores macroeconomicos e titulos publicos
(base: banco MySQL merc_financeiro, criado por extracao_dados.py).

Responde aos objetivos do projeto:
  1. Visao mensal integrada (Selic, IPCA, desocupacao, IBC-Br + titulos)
  2. Sensibilidade: correlacao entre cada indicador e a marcacao a mercado dos titulos
  3. Defasagens temporais: correlacao com indicadores atrasados 0, 1, 2 e 3 meses
  4. Estudo de caso: reacao dos titulos a cada decisao de Selic (antes x depois)
  5. Graficos (linhas, mapa de calor, dispersao) na pasta "resultados"

Como usar (terminal, na pasta do script):
    py -m pip install pandas sqlalchemy pymysql cryptography matplotlib
    py analise_dados.py
"""
import os
import sys
from urllib.parse import quote_plus

import pandas as pd
import matplotlib

matplotlib.use("Agg")  # salva PNGs sem abrir janelas
import matplotlib.pyplot as plt
from sqlalchemy import create_engine, text

# ====== AJUSTE AQUI ======
USUARIO = "root"
SENHA = "amigo1234"
HOST = "localhost"
PORTA = 3306
BANCO = "merc_financeiro"

# Janela de analise (os indicadores macro baixados cobrem 2025)
JANELA_INI = "2025-01-01"
JANELA_FIM = "2025-12-31"
BASE_INI = "2024-12-01"   # mes anterior, so para calcular a variacao de janeiro

# Titulos analisados: (rotulo, tipo_titulo, vencimento). Veja os disponiveis com a
# consulta 3.1 do arquivo .sql e troque aqui se quiser outros.
TITULOS = [
    ("Selic 2029",     "Tesouro Selic",     "2029-03-01"),
    ("Prefixado 2029", "Tesouro Prefixado", "2029-01-01"),
    ("IPCA+ 2029",     "Tesouro IPCA+",     "2029-05-15"),
    ("IPCA+ 2035",     "Tesouro IPCA+",     "2035-05-15"),
]
JANELA_EVENTO_DIAS = 15   # dias antes/depois de cada decisao de Selic
MAX_DEFASAGEM = 3
PASTA_SAIDA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resultados")
# =========================

# valor critico de |r| a 5% (bicaudal) depende do n; usamos t de Student tabelado
T_CRIT_5 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365,
            8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160,
            14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086}


def r_critico(n):
    gl = n - 2
    if gl < 1:
        return float("nan")
    t = T_CRIT_5.get(gl, 2.0)
    return t / (t * t + gl) ** 0.5


# ---------------------------------------------------------------------------
# 1. CARGA (MySQL -> pandas)
# ---------------------------------------------------------------------------
def carregar_dados(engine):
    """Devolve (macro_long, titulos): macro_long com colunas nome/data/valor e
    um dict rotulo -> DataFrame(data_base, taxa_venda, pu_venda)."""
    with engine.connect() as con:
        macro = pd.read_sql(text(
            "SELECT d.nome, m.data, m.valor FROM serie_macro m "
            "JOIN serie_def d USING (codigo_serie) "
            "WHERE m.data BETWEEN :i AND :f"),
            con, params={"i": JANELA_INI, "f": JANELA_FIM})
        titulos = {}
        for rotulo, tipo, venc in TITULOS:
            df = pd.read_sql(text(
                "SELECT data_base, taxa_venda, pu_venda FROM titulo_tesouro "
                "WHERE tipo_titulo = :t AND vencimento = :v "
                "AND data_base BETWEEN :i AND :f ORDER BY data_base"),
                con, params={"t": tipo, "v": venc, "i": BASE_INI, "f": JANELA_FIM})
            if df.empty:
                print(f"AVISO: titulo '{tipo} {venc}' sem dados - ignorando '{rotulo}'.")
                continue
            titulos[rotulo] = df
    macro["valor"] = macro["valor"].astype(float)
    macro["data"] = pd.to_datetime(macro["data"])
    for rotulo, df in titulos.items():
        df["data_base"] = pd.to_datetime(df["data_base"])
        df[["taxa_venda", "pu_venda"]] = df[["taxa_venda", "pu_venda"]].astype(float)
        titulos[rotulo] = df.set_index("data_base")
    return macro, titulos


# ---------------------------------------------------------------------------
# 2. TABELAS MENSAIS
# ---------------------------------------------------------------------------
def montar_macro_mensal(macro):
    d = macro.pivot(index="data", columns="nome", values="valor").sort_index()
    selic = d["selic_meta"].dropna()
    por_mes = selic.groupby(selic.index.to_period("M"))
    m = pd.DataFrame({"selic_media": por_mes.mean(), "selic_fim": por_mes.last()})
    prev = m["selic_fim"].shift(1)
    prev.iloc[0] = selic.iloc[0]                  # Selic do inicio de janeiro
    m["d_selic_pp"] = m["selic_fim"] - prev
    for col, novo in [("ipca_mensal", "ipca_mm"), ("ibc_br", "ibc_br"), ("desocupacao", "desocupacao")]:
        s = d[col].dropna()
        m[novo] = s.groupby(s.index.to_period("M")).last()
    m["ipca_acum_ano"] = ((1 + m["ipca_mm"] / 100).cumprod() - 1) * 100
    m["d_desocupacao_pp"] = m["desocupacao"].diff()
    m["d_ibc_pct"] = m["ibc_br"].pct_change() * 100
    return m, selic


def montar_titulos_mensal(titulos):
    saida = {}
    for rotulo, df in titulos.items():
        fim = df.groupby(df.index.to_period("M")).last()
        t = pd.DataFrame({"taxa_fim": fim["taxa_venda"], "pu_fim": fim["pu_venda"]})
        t["var_taxa_pp"] = t["taxa_fim"].diff()
        t["var_pu_pct"] = t["pu_fim"].pct_change() * 100
        saida[rotulo] = t.loc[JANELA_INI[:7]:JANELA_FIM[:7]]
    return saida


# ---------------------------------------------------------------------------
# 3. CORRELACAO COM DEFASAGENS
# ---------------------------------------------------------------------------
INDICADORES = {
    "d_selic_pp":        "Δ Selic (pp)",
    "ipca_mm":           "IPCA m/m (%)",
    "d_desocupacao_pp":  "Δ Desocupação (pp)",
    "d_ibc_pct":         "Δ IBC-Br (%)",
}


def correlacoes(macro_m, tit_m):
    linhas = []
    for rotulo, t in tit_m.items():
        for y_col, y_nome in [("var_pu_pct", "Δ Preço (%)"), ("var_taxa_pp", "Δ Taxa (pp)")]:
            for col, nome in INDICADORES.items():
                for lag in range(MAX_DEFASAGEM + 1):
                    par = pd.concat([t[y_col], macro_m[col].shift(lag)], axis=1,
                                    keys=["y", "x"]).dropna()
                    n = len(par)
                    r = par["y"].corr(par["x"]) if n >= 4 else float("nan")
                    sig = (abs(r) > r_critico(n)) if n >= 4 and r == r else False
                    linhas.append({"titulo": rotulo, "y": y_nome, "indicador": nome,
                                   "defasagem_meses": lag, "correlacao": r, "n": n,
                                   "significativa_5pct": sig})
    return pd.DataFrame(linhas)


# ---------------------------------------------------------------------------
# 4. ESTUDO DE CASO: antes x depois de cada decisao da Selic
# ---------------------------------------------------------------------------
def estudo_selic(selic, titulos):
    dif = selic.diff()
    dif.iloc[0] = 0
    decisoes = dif[dif != 0]
    linhas = []
    for dt, delta in decisoes.items():
        for rotulo, df in titulos.items():
            antes = df.loc[dt - pd.Timedelta(days=JANELA_EVENTO_DIAS): dt - pd.Timedelta(days=1)]
            depois = df.loc[dt: dt + pd.Timedelta(days=JANELA_EVENTO_DIAS)]
            if antes.empty or depois.empty:
                continue
            linhas.append({
                "decisao": dt.date(), "selic_nova": selic.loc[dt], "mudanca_pp": delta,
                "titulo": rotulo,
                "taxa_antes": antes["taxa_venda"].mean(), "taxa_depois": depois["taxa_venda"].mean(),
                "var_taxa_pp": depois["taxa_venda"].mean() - antes["taxa_venda"].mean(),
                "var_pu_pct": (depois["pu_venda"].mean() / antes["pu_venda"].mean() - 1) * 100,
            })
    return pd.DataFrame(linhas), decisoes


# ---------------------------------------------------------------------------
# 5. GRAFICOS
# ---------------------------------------------------------------------------
def grafico_macro(macro_m, selic, decisoes, caminho):
    fig, ax = plt.subplots(3, 1, figsize=(10, 9), sharex=False)
    ax[0].step(selic.index, selic.values, where="post", color="tab:blue")
    ax[0].set_title("Meta Selic (% a.a.)")
    for dt in decisoes.index:
        ax[0].axvline(dt, color="gray", ls=":", lw=0.8)
    x = macro_m.index.to_timestamp()
    ax[1].bar(x, macro_m["ipca_mm"], width=20, color="tab:orange", label="IPCA m/m (%)")
    ax[1].plot(x, macro_m["ipca_acum_ano"], color="tab:red", marker="o", label="IPCA acumulado no ano (%)")
    ax[1].set_title("Inflação (IPCA)"); ax[1].legend()
    ax[2].plot(x, macro_m["desocupacao"], color="tab:green", marker="o")
    ax[2].set_title("Taxa de desocupação (%)")
    fig.tight_layout(); fig.savefig(caminho, dpi=130); plt.close(fig)


def grafico_titulos(titulos, selic, decisoes, caminho):
    fig, ax = plt.subplots(2, 1, figsize=(10, 9), sharex=True)
    for rotulo, df in titulos.items():
        d = df.loc[JANELA_INI:JANELA_FIM]
        if rotulo.startswith("Selic"):
            ax[1].plot(d.index, d["pu_venda"] / d["pu_venda"].iloc[0] * 100, label=rotulo)
        else:
            ax[0].plot(d.index, d["taxa_venda"], label=rotulo)
            ax[1].plot(d.index, d["pu_venda"] / d["pu_venda"].iloc[0] * 100, label=rotulo)
    ax0b = ax[0].twinx()
    ax0b.step(selic.index, selic.values, where="post", color="black", ls="--", lw=1, label="Meta Selic")
    ax0b.set_ylabel("Selic (% a.a.)")
    ax[0].set_ylabel("Taxa do título (% a.a.)")
    ax[0].set_title("Taxa dos títulos (venda) x meta Selic")
    ax[1].set_title("Preço unitário (base 100 = início de 2025) - marcação a mercado")
    for a in ax:
        for dt in decisoes.index:
            a.axvline(dt, color="gray", ls=":", lw=0.8)
    h1, l1 = ax[0].get_legend_handles_labels(); h2, l2 = ax0b.get_legend_handles_labels()
    ax[0].legend(h1 + h2, l1 + l2, loc="best"); ax[1].legend(loc="best")
    fig.tight_layout(); fig.savefig(caminho, dpi=130); plt.close(fig)


def grafico_heatmap(corr, caminho):
    base = corr[corr["y"] == "Δ Preço (%)"]
    rotulos = list(dict.fromkeys(base["titulo"]))
    inds = list(INDICADORES.values())
    fig, axes = plt.subplots(1, MAX_DEFASAGEM + 1, figsize=(4.2 * (MAX_DEFASAGEM + 1), 4.4), sharey=True)
    im = None
    for lag, ax in enumerate(axes):
        sub = base[base["defasagem_meses"] == lag]
        mat = sub.pivot(index="indicador", columns="titulo", values="correlacao").loc[inds, rotulos]
        sig = sub.pivot(index="indicador", columns="titulo", values="significativa_5pct").loc[inds, rotulos]
        im = ax.imshow(mat.values.astype(float), cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
        ax.set_xticks(range(len(rotulos))); ax.set_xticklabels(rotulos, rotation=45, ha="right")
        ax.set_yticks(range(len(inds))); ax.set_yticklabels(inds)
        ax.set_title(f"Defasagem {lag} mês(es)")
        for i in range(len(inds)):
            for j in range(len(rotulos)):
                v = mat.values[i, j]
                if v == v:
                    ax.text(j, i, f"{v:.2f}" + ("*" if sig.values[i, j] else ""),
                            ha="center", va="center", fontsize=8)
    fig.colorbar(im, ax=axes, shrink=0.8, label="Correlação (Pearson)")
    fig.suptitle("Correlação entre indicadores (defasados) e variação mensal do preço dos títulos  (* = significativa a 5%)")
    fig.savefig(caminho, dpi=130, bbox_inches="tight"); plt.close(fig)


def grafico_dispersao(macro_m, tit_m, caminho):
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.6))
    for rotulo, t in tit_m.items():
        d = t.dropna(subset=["var_taxa_pp", "var_pu_pct"])
        ax[0].scatter(d["var_taxa_pp"], d["var_pu_pct"], label=rotulo)
    ax[0].axhline(0, color="gray", lw=0.6); ax[0].axvline(0, color="gray", lw=0.6)
    ax[0].set_xlabel("Δ taxa do título no mês (pp)"); ax[0].set_ylabel("Δ preço no mês (%)")
    ax[0].set_title("Marcação a mercado: taxa sobe, preço cai"); ax[0].legend(fontsize=8)
    alvo = next((k for k in tit_m if k.startswith("Prefixado")), next(iter(tit_m)))
    d = pd.concat([macro_m["d_selic_pp"], tit_m[alvo]["var_taxa_pp"]], axis=1, keys=["x", "y"]).dropna()
    ax[1].scatter(d["x"], d["y"], color="tab:red")
    ax[1].set_xlabel("Δ Selic no mês (pp)"); ax[1].set_ylabel(f"Δ taxa {alvo} (pp)")
    ax[1].set_title(f"Selic x taxa do {alvo}")
    fig.tight_layout(); fig.savefig(caminho, dpi=130); plt.close(fig)


# ---------------------------------------------------------------------------
# 6. EXECUCAO
# ---------------------------------------------------------------------------
def analisar(macro, titulos, saida=PASTA_SAIDA):
    os.makedirs(saida, exist_ok=True)
    pd.set_option("display.width", 200); pd.set_option("display.max_columns", 30)
    macro_m, selic = montar_macro_mensal(macro)
    tit_m = montar_titulos_mensal(titulos)

    # --- 1. visao mensal integrada
    painel = macro_m.copy()
    for rotulo, t in tit_m.items():
        painel[f"taxa_{rotulo}"] = t["taxa_fim"]
        painel[f"dPU%_{rotulo}"] = t["var_pu_pct"]
    painel.index = painel.index.astype(str)
    painel.round(3).to_csv(os.path.join(saida, "painel_mensal.csv"), sep=";", decimal=",")
    print("\n=== 1. PAINEL MENSAL (resumo) ===")
    print(painel[["selic_fim", "ipca_mm", "desocupacao"] +
                 [c for c in painel.columns if c.startswith("taxa_")]].round(2).to_string())

    # --- 2/3. correlacoes e defasagens
    corr = correlacoes(macro_m, tit_m)
    corr.round(4).to_csv(os.path.join(saida, "correlacoes_defasagens.csv"), sep=";", decimal=",", index=False)
    print("\n=== 2/3. MAIORES CORRELACOES COM A VARIACAO DO PRECO (|r| e defasagem) ===")
    melhor = (corr[(corr["y"] == "Δ Preço (%)") & corr["correlacao"].notna()]
              .assign(abs_r=lambda d: d["correlacao"].abs())
              .sort_values("abs_r", ascending=False).groupby("titulo").head(3))
    print(melhor[["titulo", "indicador", "defasagem_meses", "correlacao", "n", "significativa_5pct"]]
          .round(3).to_string(index=False))
    print("\nATENCAO: com poucos meses (n pequeno) so correlacoes fortes sao significativas;"
          " trate os resultados como indicios, nao como prova.")

    # --- 4. estudo de caso
    ev, decisoes = estudo_selic(selic, titulos)
    ev.round(3).to_csv(os.path.join(saida, "estudo_caso_selic.csv"), sep=";", decimal=",", index=False)
    print(f"\n=== 4. ESTUDO DE CASO: decisoes de Selic (janela de {JANELA_EVENTO_DIAS} dias) ===")
    print(ev.round(2).to_string(index=False) if not ev.empty else "sem eventos na janela")

    # --- 5. graficos
    grafico_macro(macro_m, selic, decisoes, os.path.join(saida, "01_macro.png"))
    grafico_titulos(titulos, selic, decisoes, os.path.join(saida, "02_titulos_vs_selic.png"))
    grafico_heatmap(corr, os.path.join(saida, "03_heatmap_correlacao.png"))
    grafico_dispersao(macro_m, tit_m, os.path.join(saida, "04_dispersao.png"))
    print(f"\nArquivos gerados em: {saida}")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    engine = create_engine(
        f"mysql+pymysql://{USUARIO}:{quote_plus(SENHA)}@{HOST}:{PORTA}/{BANCO}?charset=utf8mb4")
    macro, titulos = carregar_dados(engine)
    if macro.empty or not titulos:
        print("Sem dados: rode antes o extracao_dados.py e confira os titulos em TITULOS.")
        sys.exit(1)
    analisar(macro, titulos)


if __name__ == "__main__":
    main()