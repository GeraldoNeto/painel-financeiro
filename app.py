"""
Painel Financeiro Pessoal — Streamlit App
Lê dados diretamente do Google Sheets via conta de serviço.
"""

import re
import unicodedata
from datetime import date, datetime

import gspread
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from google.oauth2.service_account import Credentials

# ─── CONFIGURAÇÃO DA PÁGINA ──────────────────────────────────────────────────
st.set_page_config(
    page_title="Painel Financeiro Pessoal",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
[data-testid="stMetricValue"]  { font-size: 1.45rem !important; font-weight: 800 !important; }
[data-testid="stMetricLabel"]  { font-size: 0.78rem !important; font-weight: 600 !important; text-transform: uppercase; letter-spacing: .05em; }
[data-testid="stMetricDelta"]  { font-size: 0.80rem !important; }
div[data-testid="metric-container"] {
    background: white;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 16px 18px;
    box-shadow: 0 1px 3px rgba(0,0,0,.06);
}
thead tr th { background: #F8FAFC !important; font-size: 11px !important;
              text-transform: uppercase; letter-spacing: .05em; }
</style>
""", unsafe_allow_html=True)

# ─── CONSTANTES ───────────────────────────────────────────────────────────────
SPREADSHEET_ID = "1rFmhU8FBXEURBXYewXNWEXNTAHlWWOYDe2yFaaoUZbc"
SCOPES         = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

CAT_COLORS = {
    "Moradia": "#3B82F6", "Saúde": "#EF4444", "Cartão": "#8B5CF6",
    "Contas & Utilities": "#06B6D4", "Alimentação": "#22C55E",
    "Transporte": "#F97316", "Lazer": "#EAB308", "Investimentos": "#10B981",
    "Financiamento": "#F59E0B", "Vestuário": "#EC4899", "Educação": "#6366F1",
    "Outros": "#94A3B8",
}
MES_PT = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]

STATUS_LABEL = {
    "VENCIDO": "🔴 VENCIDO", "URGENTE": "🚨 URGENTE",
    "PRÓXIMO": "⚠️ PRÓXIMO", "ATENÇÃO": "📌 ATENÇÃO", "OK": "✅ OK",
}

# ─── HELPERS ──────────────────────────────────────────────────────────────────
def _norm(s: str) -> str:
    """Remove acentos e converte para minúsculas para comparações robustas."""
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()

def parse_brl(s) -> float:
    if not s:
        return 0.0
    s = str(s).replace("\\-", "-").replace("R$", "").replace("\xa0", "").strip()
    s = re.sub(r"\.(?=\d{3})", "", s)   # remove separador de milhar
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0

def fmt_brl(v: float) -> str:
    neg = v < 0
    s = f"R$ {abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"-{s}" if neg else s

def parse_date_br(s):
    s = str(s).strip() if s else ""
    if not s:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None

def mes_ano_from_date(d: date) -> str:
    return f"{d.month:02d}/{d.year}"

def fmt_mes_label(mm: str) -> str:
    try:
        m, y = mm.split("/")
        return f"{MES_PT[int(m) - 1]}/{y}"
    except Exception:
        return mm

def days_until(d: date) -> int:
    return (d - date.today()).days

def status_label(dias: int) -> str:
    if dias < 0:  return "VENCIDO"
    if dias <= 3: return "URGENTE"
    if dias <= 7: return "PRÓXIMO"
    if dias <= 14:return "ATENÇÃO"
    return "OK"

def sort_key_mes(mm: str):
    try:
        m, y = mm.split("/")
        return int(y) * 100 + int(m)
    except Exception:
        return 0

# ─── AUTENTICAÇÃO & CARREGAMENTO ─────────────────────────────────────────────
@st.cache_resource
def _client():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPES
    )
    return gspread.authorize(creds)

def _find_ws(wss: dict, *keywords):
    """Encontra planilha cujo nome contenha alguma das palavras-chave."""
    for ws in wss.values():
        t = _norm(ws.title)
        if any(_norm(k) in t for k in keywords):
            return ws
    return None

def _ws_to_df(ws, seek=None) -> pd.DataFrame:
    """Le a planilha localizando a linha de cabecalho correta.
    seek: lista de keywords normalizadas que devem aparecer na linha de header.
    """
    if ws is None:
        return pd.DataFrame()
    values = ws.get_all_values()
    if not values or len(values) < 2:
        return pd.DataFrame()

    def norm(s):
        import unicodedata
        return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()

    header_idx = 0
    for i, row in enumerate(values[:-1]):
        non_empty = [c.strip() for c in row if c.strip()]
        if len(non_empty) < 3:
            continue
        if seek:
            row_norm = [norm(c) for c in non_empty]
            if all(any(kw in cell for cell in row_norm) for kw in seek):
                header_idx = i
                break
        else:
            if len(set(non_empty)) == len(non_empty):
                header_idx = i
                break

    raw_headers = values[header_idx]
    seen: dict = {}
    headers = []
    for h in raw_headers:
        h = h.strip()
        if h == "" or h in seen:
            count = seen.get(h, 0) + 1
            seen[h] = count
            headers.append(f"{h}_{count}" if h else f"_vazio_{count}")
        else:
            seen[h] = 0
            headers.append(h)

    df = pd.DataFrame(values[header_idx + 1:], columns=headers)
    df = df[df.apply(lambda r: r.astype(str).str.strip().ne("").any(), axis=1)]
    return df

@st.cache_data(ttl=300, show_spinner=False)
def load_data():
    client = _client()
    ss     = client.open_by_key(SPREADSHEET_ID)
    wss    = {ws.title: ws for ws in ss.worksheets()}

    ws_lan = _find_ws(wss, "lancamento")
    ws_ent = _find_ws(wss, "entrada")

    df_lan = _ws_to_df(ws_lan, seek=["vencimento"])
    df_ent = _ws_to_df(ws_ent, seek=["responsavel"])

    sheet_names = list(wss.keys())
    lan_name    = ws_lan.title if ws_lan else None
    ent_name    = ws_ent.title if ws_ent else None

    return df_lan, df_ent, datetime.now(), sheet_names, lan_name, ent_name

# ─── TRANSFORMAÇÃO DOS DADOS ──────────────────────────────────────────────────
def _col(df: pd.DataFrame, *tests) -> str:
    """Retorna o nome da primeira coluna que passe em algum dos testes."""
    for col in df.columns:
        cn = _norm(col)
        for t in tests:
            if t(cn):
                return col
    return ""

def process_lancamentos(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()
    df = raw.copy()

    # Mapeamento dinâmico de colunas
    c_venc    = _col(df, lambda c: c == "vencimento")
    c_desc    = _col(df, lambda c: "descri" in c)
    c_cat     = _col(df, lambda c: c == "categoria")
    c_val     = _col(df, lambda c: "valor" in c)
    c_forma   = _col(df, lambda c: "forma" in c)
    c_mes     = _col(df, lambda c: c in ("mes/ano", "mês/ano", "mes", "mês"))
    c_pago    = _col(df, lambda c: c == "pago")
    c_datapag = _col(df, lambda c: "data" in c and "pag" in c)
    c_bancoC  = _col(df, lambda c: "banco" in c and "cart" in c)
    c_bancoP  = _col(df, lambda c: "banco" in c and "pago" in c)
    c_obs     = _col(df, lambda c: "observa" in c)

    get = lambda df, col: df[col].astype(str).str.strip() if col else pd.Series([""] * len(df))

    out = pd.DataFrame()
    out["vencimento"]      = get(df, c_venc)
    out["descricao"]       = get(df, c_desc)
    out["categoria"]       = get(df, c_cat)
    out["valor"]           = get(df, c_val).apply(parse_brl)
    out["forma"]           = get(df, c_forma)
    out["mes_ano_raw"]     = get(df, c_mes)
    out["pago"]            = get(df, c_pago).str.strip()
    out["data_pagamento"]  = get(df, c_datapag)
    out["banco_cartao"]    = get(df, c_bancoC)
    out["banco_pago"]      = get(df, c_bancoP)
    out["observacoes"]     = get(df, c_obs)

    out["venc_date"]     = out["vencimento"].apply(parse_date_br)
    out["data_pag_date"] = out["data_pagamento"].apply(parse_date_br)

    # Mantém apenas linhas com data de vencimento válida
    out = out[out["venc_date"].notna()].copy()

    out["dias"]   = out["venc_date"].apply(days_until)
    out["status"] = out["dias"].apply(status_label)
    out["mes_ano"] = out.apply(
        lambda r: r["mes_ano_raw"] if r["mes_ano_raw"] else mes_ano_from_date(r["venc_date"]),
        axis=1,
    )
    return out

def process_entradas(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()
    df = raw.copy()

    c_data  = _col(df, lambda c: "data" in c and "entrada" in c)
    c_val   = _col(df, lambda c: "valor" in c)
    c_banco = _col(df, lambda c: c == "banco")
    c_resp  = _col(df, lambda c: "respons" in c)

    get = lambda col: df[col].astype(str).str.strip() if col else pd.Series([""] * len(df))

    out = pd.DataFrame()
    out["data"]        = get(c_data)
    out["valor"]       = get(c_val).apply(parse_brl)
    out["banco"]       = get(c_banco)
    out["responsavel"] = get(c_resp)
    out["data_date"]   = out["data"].apply(parse_date_br)

    out = out[out["data_date"].notna() & (out["valor"] > 0)].copy()
    out["mes_ano"] = out["data_date"].apply(mes_ano_from_date)
    return out

# ─── SIDEBAR ─────────────────────────────────────────────────────────────────
def make_sidebar(df_lan: pd.DataFrame, df_ent: pd.DataFrame):
    with st.sidebar:
        st.markdown("## 🔍 Filtros")

        # Período
        all_months = sorted(
            set(df_lan["mes_ano"].dropna()) | set(df_ent["mes_ano"].dropna()),
            key=sort_key_mes,
        )
        sel_months = st.multiselect(
            "Período",
            options=all_months,
            default=all_months,
            format_func=fmt_mes_label,
        )

        # Status
        sel_status = st.radio(
            "Status", ["Todos", "Pendentes", "Pagos"], horizontal=True
        )

        # Categoria
        all_cats = sorted(df_lan["categoria"].dropna().unique())
        sel_cats = st.multiselect("Categoria", options=all_cats, default=all_cats)

        st.divider()

        if st.button("↺  Recarregar dados", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

        st.caption("⏱ Dados atualizados a cada 5 min automaticamente")

    return sel_months or all_months, sel_status, sel_cats or all_cats

def apply_filters(df_lan, df_ent, sel_months, sel_status, sel_cats):
    fl = df_lan[df_lan["mes_ano"].isin(sel_months) & df_lan["categoria"].isin(sel_cats)].copy()
    if sel_status == "Pendentes":
        fl = fl[fl["pago"].str.lower() != "sim"]
    elif sel_status == "Pagos":
        fl = fl[fl["pago"].str.lower() == "sim"]

    fe = df_ent[df_ent["mes_ano"].isin(sel_months)].copy()
    return fl, fe

# ─── KPI CARDS ────────────────────────────────────────────────────────────────
def render_kpis(df_lan, df_ent, df_lan_full, df_ent_full, sel_months):
    pend = df_lan[df_lan["pago"].str.lower() != "sim"]
    entradas   = df_ent["valor"].sum()
    a_vencer   = pend["valor"].sum()
    saldo      = entradas - a_vencer
    vence_7    = pend[(pend["dias"] >= 0) & (pend["dias"] <= 7)]["valor"].sum()
    cartao     = pend[pend["categoria"] == "Cartão"]["valor"].sum()

    # Crescimento vs mês anterior (só com filtro de 1 mês)
    d_ent = d_av = d_sld = d_cart = None
    if len(sel_months) == 1:
        cur = sel_months[0]
        all_m = sorted(
            set(df_lan_full["mes_ano"].dropna()) | set(df_ent_full["mes_ano"].dropna()),
            key=sort_key_mes,
        )
        idx = list(all_m).index(cur) if cur in all_m else -1
        if idx > 0:
            prev = all_m[idx - 1]
            pl   = df_lan_full[df_lan_full["mes_ano"] == prev]
            pe   = df_ent_full[df_ent_full["mes_ano"] == prev]
            pp   = pl[pl["pago"].str.lower() != "sim"]
            pE   = pe["valor"].sum()
            pAV  = pp["valor"].sum()
            pSld = pE - pAV
            pCar = pp[pp["categoria"] == "Cartão"]["valor"].sum()

            def pct(c, p):
                return None if p == 0 else ((c - p) / abs(p)) * 100

            d_ent  = pct(entradas, pE)
            d_av   = pct(a_vencer, pAV)
            d_sld  = pct(saldo,    pSld)
            d_cart = pct(cartao,   pCar)

    def dfmt(v):
        if v is None: return None
        a = "▲" if v > 0.5 else ("▼" if v < -0.5 else "▶")
        return f"{a} {abs(v):.1f}% vs mês ant."

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: st.metric("💰 Total Entradas",   fmt_brl(entradas), dfmt(d_ent))
    with c2: st.metric("📋 Total a Vencer",   fmt_brl(a_vencer), dfmt(d_av),   delta_color="inverse")
    with c3: st.metric("📈 Saldo Projetado",  fmt_brl(saldo),    dfmt(d_sld))
    with c4: st.metric("⏰ Vence em 7 dias",  fmt_brl(vence_7))
    with c5: st.metric("💳 Gastos no Cartão", fmt_brl(cartao),   dfmt(d_cart), delta_color="inverse")

# ─── GRÁFICOS ─────────────────────────────────────────────────────────────────
def render_charts(df_lan_full, df_ent_full, df_lan_filt):
    col1, col2 = st.columns([3, 2])

    # Histórico mensal
    with col1:
        st.subheader("📊 Histórico Mensal")
        months = sorted(
            set(df_lan_full["mes_ano"].dropna()) | set(df_ent_full["mes_ano"].dropna()),
            key=sort_key_mes,
        )
        rows = []
        for m in months:
            e = df_ent_full[df_ent_full["mes_ano"] == m]["valor"].sum()
            g = df_lan_full[df_lan_full["mes_ano"] == m]["valor"].sum()
            if e > 0 or g > 0:
                rows.append({"Mês": fmt_mes_label(m), "Entradas": e, "Gastos": g})
        if rows:
            dh = pd.DataFrame(rows)
            fig = go.Figure()
            fig.add_bar(x=dh["Mês"], y=dh["Entradas"], name="Entradas",
                        marker_color="#16A34A", opacity=0.85, marker_line_width=0)
            fig.add_bar(x=dh["Mês"], y=dh["Gastos"],   name="Gastos/A Vencer",
                        marker_color="#DC2626", opacity=0.85, marker_line_width=0)
            fig.update_layout(barmode="group", height=270,
                              margin=dict(l=0, r=0, t=8, b=0),
                              legend=dict(orientation="h", yanchor="bottom", y=1.02),
                              paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            fig.update_yaxes(tickprefix="R$ ", gridcolor="#F1F5F9", tickfont_size=11)
            fig.update_xaxes(showgrid=False, tickfont_size=11)
            st.plotly_chart(fig, use_container_width=True)

    # Gastos por categoria (donut)
    with col2:
        st.subheader("🍩 Gastos por Categoria")
        cat = (df_lan_filt[df_lan_filt["valor"] > 0]
               .groupby("categoria")["valor"].sum()
               .reset_index().sort_values("valor", ascending=False))
        if not cat.empty:
            colors = [CAT_COLORS.get(c, "#94A3B8") for c in cat["categoria"]]
            fig = go.Figure(go.Pie(
                labels=cat["categoria"], values=cat["valor"],
                hole=0.58, marker_colors=colors,
                textinfo="percent", textfont_size=11,
                hovertemplate="%{label}<br>R$ %{value:,.2f}<extra></extra>",
            ))
            fig.update_layout(height=270, margin=dict(l=0, r=0, t=8, b=0),
                              legend=dict(font_size=11),
                              paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

    col3, col4 = st.columns(2)

    # Entradas por responsável
    with col3:
        st.subheader("👥 Entradas por Responsável")
        per = (df_ent_full.groupby("responsavel")["valor"].sum()
               .reset_index().sort_values("valor"))
        if not per.empty:
            fig = px.bar(per, x="valor", y="responsavel", orientation="h",
                         color="responsavel",
                         color_discrete_sequence=["#2563EB","#16A34A","#D97706","#7C3AED"])
            fig.update_layout(height=220, showlegend=False,
                              margin=dict(l=0, r=0, t=8, b=0),
                              paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            fig.update_xaxes(tickprefix="R$ ", showgrid=False, tickfont_size=11)
            fig.update_yaxes(showgrid=False, tickfont_size=11)
            st.plotly_chart(fig, use_container_width=True)

    # Evolução do saldo
    with col4:
        st.subheader("📈 Evolução do Saldo")
        months = sorted(
            set(df_lan_full["mes_ano"].dropna()) | set(df_ent_full["mes_ano"].dropna()),
            key=sort_key_mes,
        )
        srows = []
        for m in months:
            e = df_ent_full[df_ent_full["mes_ano"] == m]["valor"].sum()
            g = df_lan_full[df_lan_full["mes_ano"] == m]["valor"].sum()
            if e > 0 or g > 0:
                srows.append({"Mês": fmt_mes_label(m), "Saldo": e - g})
        if srows:
            ds = pd.DataFrame(srows)
            pt_colors = ["#16A34A" if s >= 0 else "#DC2626" for s in ds["Saldo"]]
            fig = go.Figure()
            fig.add_scatter(
                x=ds["Mês"], y=ds["Saldo"], mode="lines+markers",
                line=dict(color="#2563EB", width=2.5),
                marker=dict(color=pt_colors, size=8,
                            line=dict(color="white", width=2)),
                fill="tozeroy", fillcolor="rgba(37,99,235,.07)",
                hovertemplate="Saldo: R$ %{y:,.2f}<extra></extra>",
            )
            fig.update_layout(height=220, margin=dict(l=0, r=0, t=8, b=0),
                              paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            fig.update_yaxes(tickprefix="R$ ", gridcolor="#F1F5F9", tickfont_size=11)
            fig.update_xaxes(showgrid=False, tickfont_size=11)
            st.plotly_chart(fig, use_container_width=True)

# ─── TABELA: ALERTAS DE VENCIMENTO ───────────────────────────────────────────
def render_alerts(df_lan: pd.DataFrame):
    st.subheader("🔔 Alertas de Vencimento")
    pend = df_lan[df_lan["pago"].str.lower() != "sim"].sort_values("dias").copy()
    st.caption(f"{len(pend)} pendente(s)")

    if pend.empty:
        st.success("✅ Nenhum vencimento pendente no período selecionado.")
        return

    disp = pend[["status","descricao","categoria","vencimento","dias","valor","forma"]].copy()
    disp["status"] = disp["status"].map(STATUS_LABEL).fillna(disp["status"])
    disp["valor"]  = disp["valor"].apply(fmt_brl)
    disp["dias"]   = disp["dias"].apply(
        lambda d: f"{abs(d)}d atrás" if d < 0 else ("Hoje" if d == 0 else f"{d}d")
    )
    disp.columns = ["Status", "Descrição", "Categoria", "Vencimento", "Dias", "Valor", "Forma Pag."]
    st.dataframe(disp, use_container_width=True, hide_index=True)

# ─── TABELA: CONTAS PAGAS ────────────────────────────────────────────────────
def render_paid(df_lan: pd.DataFrame):
    st.subheader("✅ Contas Pagas")
    pagos = (df_lan[df_lan["pago"].str.lower() == "sim"]
             .sort_values("data_pag_date", ascending=False, na_position="last")
             .copy())
    total = pagos["valor"].sum()
    st.caption(f"{len(pagos)} conta(s)  ·  Total pago: {fmt_brl(total)}")

    if pagos.empty:
        st.info("Nenhuma conta paga no período selecionado.")
        return

    disp = pagos[["descricao","categoria","vencimento","data_pagamento","valor","banco_pago","observacoes"]].copy()
    disp["valor"] = disp["valor"].apply(fmt_brl)
    disp.columns = ["Descrição","Categoria","Vencimento","Data Pagamento","Valor","Banco (Pago)","Observações"]
    st.dataframe(disp, use_container_width=True, hide_index=True)

# ─── TABELA: ENTRADAS ────────────────────────────────────────────────────────
def render_entries(df_ent: pd.DataFrame):
    st.subheader("📥 Entradas Registradas")
    total = df_ent["valor"].sum()
    st.caption(f"{len(df_ent)} entrada(s)  ·  Total: {fmt_brl(total)}")

    if df_ent.empty:
        st.info("Nenhuma entrada no período selecionado.")
        return

    disp = df_ent[["data","responsavel","banco","valor"]].copy()
    disp["valor"] = disp["valor"].apply(fmt_brl)
    disp.columns = ["Data", "Responsável", "Banco", "Valor"]
    st.dataframe(disp, use_container_width=True, hide_index=True)

# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    st.title("💰 Painel Financeiro Pessoal")

    with st.spinner("Buscando dados do Google Sheets…"):
        try:
            df_lan_raw, df_ent_raw, loaded_at, sheet_names, lan_name, ent_name = load_data()
        except Exception as e:
            st.error(f"Erro ao conectar ao Google Sheets: {e}")
            st.info("Verifique se as credenciais estão corretas em `.streamlit/secrets.toml` "
                    "e se a planilha foi compartilhada com o e-mail da conta de serviço.")
            st.stop()

    # Diagnostico
    with st.expander("Diagnostico de conexao", expanded=True):
        col_a, col_b = st.columns(2)
        with col_a:
            abas = " | ".join(sheet_names)
            st.markdown(f"**Abas na planilha:** {abas}")
            st.markdown(f"**Lancamentos:** {lan_name or 'nao encontrada'} ({len(df_lan_raw)} linhas)")
            st.markdown(f"**Entradas:** {ent_name or 'nao encontrada'} ({len(df_ent_raw)} linhas)")
        with col_b:
            if not df_lan_raw.empty:
                cols_lan = " | ".join(df_lan_raw.columns.tolist())
                st.markdown(f"**Colunas Lancamentos:** {cols_lan}")
            if not df_ent_raw.empty:
                cols_ent = " | ".join(df_ent_raw.columns.tolist())
                st.markdown(f"**Colunas Entradas:** {cols_ent}")

    # Pipeline
    df_lan = process_lancamentos(df_lan_raw)
    df_ent = process_entradas(df_ent_raw)
    sel_months, sel_status, sel_cats = make_sidebar(df_lan, df_ent)
    df_lan_f, df_ent_f = apply_filters(df_lan, df_ent, sel_months, sel_status, sel_cats)

    render_kpis(df_lan_f, df_ent_f, df_lan, df_ent, sel_months)
    render_charts(df_lan, df_ent, df_lan_f)
    render_alerts(df_lan_f)
    render_paid(df_lan_f)
    render_entries(df_ent_f)

    tz_info = loaded_at.strftime("%d/%m/%Y %H:%M:%S")
    st.caption(f"Dados atualizados em: {tz_info}")


if __name__ == "__main__":
    main()
