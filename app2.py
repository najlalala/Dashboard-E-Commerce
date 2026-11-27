import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import folium
from datetime import date, timedelta
from streamlit_folium import st_folium
from deep_translator import GoogleTranslator

from utils.data_loader import load_all_data

# =====================================================
# KONFIGURASI & TAMPILAN
# =====================================================
st.set_page_config(page_title="Dashboard E-Commerce SSDC", page_icon="📊", layout="wide")

PALETTE = ["#0F766E", "#E39B2D", "#6A7FB0", "#C2410C", "#2B8A80", "#8E6BBF"]
px.defaults.template = "plotly_white"
px.defaults.color_discrete_sequence = PALETTE

st.markdown("""
<style>
    .block-container {padding-top: 1.5rem; max-width: 1300px;}
    [data-testid="stMetric"] {
        background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px;
        padding: 14px 18px; box-shadow: 0 1px 3px rgba(15,23,42,.06);
    }
    [data-testid="stMetricLabel"] {color: #64748B; font-weight: 600;}
    [data-testid="stMetricValue"] {font-size: 1.7rem; font-weight: 700;}
    section[data-testid="stSidebar"] {border-right: 1px solid #E2E8F0;}
    .insight {
        background: #E8F3F1; border-left: 4px solid #0F766E; color: #14302C;
        padding: 12px 18px; border-radius: 8px; margin: 12px 0 18px 0;
    }
    .insight ul {margin: 6px 0 0 0; padding-left: 18px;}
    .insight li {margin: 3px 0;}
</style>
""", unsafe_allow_html=True)

# Streamlit versi baru memakai width="stretch", versi lama use_container_width
try:
    _NEW_ST = tuple(int(x) for x in st.__version__.split(".")[:2]) >= (1, 50)
except Exception:
    _NEW_ST = False


def plot(fig, h=360):
    fig.update_layout(height=h, margin=dict(l=10, r=10, t=50, b=10),
                      title_font_size=15, legend_title_text="")
    if _NEW_ST:
        st.plotly_chart(fig, width="stretch")
    else:
        st.plotly_chart(fig, use_container_width=True)


def table(df, **kw):
    if _NEW_ST:
        st.dataframe(df, width="stretch", hide_index=True, **kw)
    else:
        st.dataframe(df, use_container_width=True, hide_index=True, **kw)


def insight(lines, title="Temuan utama"):
    items = "".join(f"<li>{x}</li>" for x in lines)
    st.markdown(f'<div class="insight"><b>💡 {title}</b><ul>{items}</ul></div>',
                unsafe_allow_html=True)


def money(x):
    if abs(x) >= 1e6:
        return f"R$ {x / 1e6:,.2f} jt"
    if abs(x) >= 1e3:
        return f"R$ {x / 1e3:,.0f} rb"
    return f"R$ {x:,.0f}"


def pct_change(cur, prev):
    if prev is None or prev == 0 or pd.isna(prev):
        return None
    return (cur - prev) / prev * 100


def dstr(cur, prev):
    g = pct_change(cur, prev)
    return None if g is None else f"{g:+.1f}%"


@st.cache_data(show_spinner=False)
def translate_text(text, target_lang="id"):
    try:
        return GoogleTranslator(source="auto", target=target_lang).translate(text)
    except Exception:
        return text


# =====================================================
# DATA: satu tabel per order + satu tabel per item
# =====================================================
try:
    raw = load_all_data()
except Exception as e:
    st.error(f"Gagal memuat data: {e}")
    st.stop()


@st.cache_data(show_spinner="Menyiapkan data…")
def build_facts():
    d = load_all_data()

    o = d["orders"].copy()
    for c in ["order_purchase_timestamp", "order_approved_at",
              "order_delivered_customer_date", "order_estimated_delivery_date"]:
        o[c] = pd.to_datetime(o[c], errors="coerce")
    o = o.dropna(subset=["order_purchase_timestamp"])

    # customer_unique_id = pelanggan sebenarnya (customer_id berbeda untuk tiap order)
    cust = d["customers"][["customer_id", "customer_unique_id", "customer_city",
                           "customer_state", "customer_zip_code_prefix"]].copy()
    cust["zip"] = cust["customer_zip_code_prefix"].astype(str).str.zfill(5)
    o = o.merge(cust.drop(columns="customer_zip_code_prefix"), on="customer_id", how="left")

    geo = d["geolocation"][["geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng"]].copy()
    geo.columns = ["zip", "lat", "lng"]
    geo["zip"] = geo["zip"].astype(str)
    o = o.merge(geo, on="zip", how="left")

    pays = d["order_payments"]
    pay = pays.groupby("order_id").agg(revenue=("payment_value", "sum"),
                                       installments=("payment_installments", "max")).reset_index()
    main_pay = (pays.sort_values("payment_value", ascending=False)
                .drop_duplicates("order_id")[["order_id", "payment_type"]]
                .rename(columns={"payment_type": "main_payment"}))
    itm = d["order_items"].groupby("order_id").agg(n_items=("order_item_id", "count"),
                                                   freight=("freight_value", "sum")).reset_index()
    rev = d["order_reviews"].groupby("order_id")["review_score"].mean().reset_index()

    for t in (pay, main_pay, itm, rev):
        o = o.merge(t, on="order_id", how="left")
    o["revenue"] = o["revenue"].fillna(0)

    o["year_month"] = o["order_purchase_timestamp"].dt.to_period("M").astype(str)
    o["is_valid"] = ~o["order_status"].isin(["canceled", "unavailable"])
    o["delivery_days"] = (o["order_delivered_customer_date"] - o["order_purchase_timestamp"]).dt.total_seconds() / 86400
    o["delay_days"] = (o["order_delivered_customer_date"] - o["order_estimated_delivery_date"]).dt.total_seconds() / 86400
    o["is_late"] = (o["delay_days"] > 0).astype(float).where(o["delay_days"].notna())

    # urutan order tiap pelanggan (0 = pembelian pertama sepanjang data)
    o = o.sort_values("order_purchase_timestamp")
    o["order_seq"] = np.nan
    v = o["is_valid"]
    o.loc[v, "order_seq"] = o[v].groupby("customer_unique_id").cumcount()

    prod = d["products"][["product_id", "product_category_name"]].merge(
        d["product_cat"], on="product_category_name", how="left")
    prod["category"] = (prod["product_category_name_english"]
                        .fillna(prod["product_category_name"]).fillna("unknown"))
    it = d["order_items"][["order_id", "order_item_id", "product_id", "seller_id", "price"]].merge(
        prod[["product_id", "category"]], on="product_id", how="left")
    it = it.merge(o[["order_id", "order_purchase_timestamp", "is_valid", "customer_state",
                     "review_score", "delivery_days", "is_late"]], on="order_id", how="inner")

    rv = d["order_reviews"][["order_id", "review_score", "review_comment_message",
                             "review_creation_date"]].copy()
    return o, it, rv


orders_all, items_all, reviews_all = build_facts()
leads_q, leads_c = raw["leads_qualified"], raw["leads_closed"]


def slice_df(df, s, e):
    ts = df["order_purchase_timestamp"]
    return df[(ts >= pd.Timestamp(s)) & (ts < pd.Timestamp(e) + pd.Timedelta(days=1)) & df["is_valid"]]


# =====================================================
# SIDEBAR: navigasi + filter
# =====================================================
st.sidebar.title("📊 SSDC E-Commerce")
page = st.sidebar.radio(
    "Halaman",
    ["Ringkasan", "Pelanggan", "Produk & Seller", "Operasional & Kepuasan"],
    label_visibility="collapsed",
)
st.sidebar.markdown("---")

data_min = orders_all["order_purchase_timestamp"].min().date()
data_max = orders_all["order_purchase_timestamp"].max().date()
if page == "Ringkasan":
    year = st.sidebar.selectbox("Tahun", [2018, 2017])
    st.sidebar.caption("2018 dihitung sampai Agu (data Sep–Okt hampir kosong) dan dibandingkan "
                       "dengan Jan–Agu 2017. 2017 belum punya pembanding karena data 2016 terlalu sedikit.")
    start = max(date(year, 1, 1), data_min)
    end = min(date(year, 12, 31), date(2018, 8, 31), data_max)
    p_start = (pd.Timestamp(start) - pd.DateOffset(years=1)).date()
    p_end = (pd.Timestamp(end) - pd.DateOffset(years=1)).date()
else:
    default_start = max(data_min, date(2017, 1, 1))
    default_end = min(data_max, date(2018, 8, 31))
    picked = st.sidebar.date_input("Rentang tanggal", value=(default_start, default_end),
                                   min_value=data_min, max_value=data_max)
    if not isinstance(picked, (tuple, list)) or len(picked) != 2:
        st.info("Pilih tanggal mulai dan tanggal selesai di sidebar.")
        st.stop()
    start, end = picked
    st.sidebar.caption("Data paling lengkap ada di Jan 2017 – Agu 2018.")
    p_start = p_end = None

cur = slice_df(orders_all, start, end)
if cur.empty:
    st.warning("Tidak ada order pada rentang tanggal ini.")
    st.stop()
items = slice_df(items_all, start, end)

if p_start is not None:
    prev = slice_df(orders_all, p_start, p_end)
    has_prev = p_start >= data_min and len(prev) >= 100
    cmp_label = f"{p_start:%d %b %Y} – {p_end:%d %b %Y}"
else:
    prev, has_prev, cmp_label = orders_all.iloc[0:0], False, ""

st.title("📊 Dashboard E-Commerce SSDC")
if page == "Ringkasan":
    st.caption(
        f"Tahun **{year}** ({start:%d %b} – {end:%d %b %Y}) · {len(cur):,} order · "
        + (f"dibandingkan dengan {cmp_label}" if has_prev else "belum ada data tahun sebelumnya untuk dibandingkan")
    )
else:
    st.caption(f"Periode: **{start:%d %b %Y} – {end:%d %b %Y}** · {len(cur):,} order")


def kpis(df):
    n = len(df)
    rev = df["revenue"].sum()
    return dict(rev=rev, orders=n, cust=df["customer_unique_id"].nunique(),
                aov=rev / n if n else 0)


k = kpis(cur)
kp = kpis(prev) if has_prev else None


def d_(key):
    return dstr(k[key], kp[key]) if kp else None


# =====================================================
# HALAMAN 1: RINGKASAN
# =====================================================
if page == "Ringkasan":
    st.header("Ringkasan")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Revenue", money(k["rev"]), d_("rev"))
    c2.metric("Jumlah order", f"{k['orders']:,}", d_("orders"))
    c3.metric("Pelanggan unik", f"{k['cust']:,}", d_("cust"))
    c4.metric("Nilai rata-rata per order", f"R$ {k['aov']:,.0f}", d_("aov"))

    cat = items.groupby("category").agg(revenue=("price", "sum"), items=("order_item_id", "count")).reset_index()
    cat = cat.sort_values("revenue", ascending=False)
    state = (cur.groupby("customer_state").agg(orders=("order_id", "count"), revenue=("revenue", "sum"))
             .reset_index().sort_values("orders", ascending=False))

    lines = []
    if kp:
        g_rev, g_ord, g_aov = (pct_change(k[x], kp[x]) for x in ("rev", "orders", "aov"))
        arah = "naik" if g_rev >= 0 else "turun"
        lines.append(f"Revenue <b>{arah} {abs(g_rev):.1f}%</b> dibanding {cmp_label}. "
                     f"Perubahan jumlah order {g_ord:+.1f}%, nilai per order {g_aov:+.1f}%.")
    if len(cat):
        lines.append(f"Kategori <b>{cat.iloc[0]['category']}</b> menyumbang "
                     f"{cat.iloc[0]['revenue'] / cat['revenue'].sum() * 100:.1f}% revenue produk. "
                     f"3 kategori teratas bersama = {cat['revenue'].head(3).sum() / cat['revenue'].sum() * 100:.0f}%.")
    if len(state):
        lines.append(f"State <b>{state.iloc[0]['customer_state']}</b> menyumbang "
                     f"{state.iloc[0]['orders'] / state['orders'].sum() * 100:.0f}% order. "
                     f"3 state teratas = {state['orders'].head(3).sum() / state['orders'].sum() * 100:.0f}%, "
                     "jadi ketergantungan pada wilayah tertentu cukup tinggi.")
    insight(lines)

    m = cur.groupby("year_month").agg(orders=("order_id", "count"), revenue=("revenue", "sum")).reset_index()
    fig = go.Figure()
    fig.add_bar(x=m["year_month"], y=m["revenue"], name="Revenue (R$)", marker_color=PALETTE[2], opacity=0.75)
    fig.add_scatter(x=m["year_month"], y=m["orders"], name="Order", yaxis="y2",
                    mode="lines+markers", line=dict(color=PALETTE[1], width=3))
    fig.update_layout(title="Tren bulanan: revenue dan jumlah order",
                      yaxis=dict(title="Revenue (R$)"),
                      yaxis2=dict(title="Order", overlaying="y", side="right", showgrid=False),
                      hovermode="x unified", legend=dict(orientation="h", y=1.12))
    plot(fig, 380)

    col1, col2 = st.columns(2)
    with col1:
        t = cat.head(10).sort_values("revenue")
        plot(px.bar(t, x="revenue", y="category", orientation="h",
                    title="10 kategori dengan revenue terbesar",
                    labels={"revenue": "Revenue (R$)", "category": ""}), 400)
    with col2:
        t = state.head(10).sort_values("orders")
        plot(px.bar(t, x="orders", y="customer_state", orientation="h",
                    title="10 state dengan order terbanyak",
                    labels={"orders": "Jumlah order", "customer_state": ""}), 400)

# =====================================================
# HALAMAN 2: PELANGGAN
# =====================================================
elif page == "Pelanggan":
    st.header("Pelanggan")

    pc = cur.groupby("customer_unique_id").agg(
        orders=("order_id", "count"), spend=("revenue", "sum"),
        last=("order_purchase_timestamp", "max")).reset_index()
    ref = pd.Timestamp(end) + pd.Timedelta(days=1)
    pc["recency"] = (ref - pc["last"]).dt.days
    q80 = pc["spend"].quantile(0.8)
    pc["segment"] = np.select(
        [pc["orders"] >= 2, pc["spend"] >= q80, pc["recency"] <= 90, pc["recency"] > 180],
        ["Pembeli berulang", "Big spender (beli 1x)", "Baru beli (≤ 90 hari)", "Tidak aktif (> 180 hari)"],
        default="Beli 3–6 bulan lalu",
    )
    repeat_rate = (pc["orders"] > 1).mean() * 100
    seg = pc.groupby("segment").agg(pelanggan=("customer_unique_id", "count"),
                                    rata_belanja=("spend", "mean")).reset_index()
    seg["porsi"] = seg["pelanggan"] / seg["pelanggan"].sum() * 100
    seg = seg.sort_values("pelanggan", ascending=False)

    city = (cur.groupby(["customer_city", "customer_state"])
            .agg(orders=("order_id", "count"), revenue=("revenue", "sum"),
                 lat=("lat", "mean"), lng=("lng", "mean"))
            .reset_index().sort_values("orders", ascending=False))
    pay = cur["main_payment"].value_counts()
    inst = cur.loc[cur["main_payment"] == "credit_card", "installments"].mean()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Pelanggan unik", f"{len(pc):,}")
    c2.metric("Pelanggan yang beli ulang", f"{repeat_rate:.1f}%")
    c3.metric("Order per pelanggan", f"{pc['orders'].mean():.2f}")
    c4.metric("Median belanja", f"R$ {pc['spend'].median():,.0f}")

    lapsed = seg.loc[seg["segment"] == "Tidak aktif (> 180 hari)", "porsi"].sum()
    lines = [
        f"Hanya <b>{repeat_rate:.1f}%</b> pelanggan yang membeli lebih dari sekali. "
        "Peluang terbesar ada di program pembelian ke-2 (voucher, email follow-up).",
        f"<b>{lapsed:.0f}%</b> pelanggan sudah lebih dari 180 hari tidak membeli. "
        "Ini kandidat kampanye reaktivasi.",
        f"Kota <b>{city.iloc[0]['customer_city'].title()}</b> menyumbang "
        f"{city.iloc[0]['orders'] / city['orders'].sum() * 100:.0f}% order.",
    ]
    if len(pay):
        lines.append(f"<b>{pay.index[0]}</b> dipakai di {pay.iloc[0] / pay.sum() * 100:.0f}% order"
                     + (f", cicilan kartu kredit rata-rata {inst:.1f}x." if pd.notna(inst) else "."))
    insight(lines)

    # Baru vs kembali
    t = cur.assign(tipe=np.where(cur["order_seq"] == 0, "Pelanggan baru", "Pelanggan kembali"))
    t = t.groupby(["year_month", "tipe"]).size().reset_index(name="orders")
    col1, col2 = st.columns([3, 2])
    with col1:
        plot(px.bar(t, x="year_month", y="orders", color="tipe", barmode="stack",
                    title="Order dari pelanggan baru vs kembali",
                    labels={"year_month": "", "orders": "Order"},
                    color_discrete_map={"Pelanggan baru": PALETTE[0], "Pelanggan kembali": PALETTE[1]}), 360)
    with col2:
        plot(px.bar(seg.sort_values("porsi"), x="porsi", y="segment", orientation="h",
                    title="Segmentasi pelanggan (% dari total)",
                    labels={"porsi": "%", "segment": ""}, text=seg.sort_values("porsi")["porsi"].round(0)), 360)

    with st.expander("Detail segmen"):
        sd = seg.rename(columns={"segment": "Segmen", "pelanggan": "Pelanggan",
                                 "rata_belanja": "Rata-rata belanja (R$)", "porsi": "Porsi (%)"})
        table(sd.round(1))
        st.caption("Berulang = ≥2 order di periode ini. Big spender = 20% belanja terbesar. "
                   "Recency dihitung dari tanggal akhir filter.")

    # Geografi
    st.subheader("Sebaran kota")
    col1, col2 = st.columns([2, 3])
    with col1:
        t = city.head(10).sort_values("orders")
        plot(px.bar(t, x="orders", y="customer_city", orientation="h",
                    title="10 kota dengan order terbanyak",
                    labels={"orders": "Order", "customer_city": ""}), 440)
    with col2:
        top30 = city.head(30)
        mx = top30["orders"].max()
        fmap = folium.Map(location=[-14.2, -51.9], zoom_start=4, tiles="CartoDB positron")
        for r in top30.itertuples():
            if pd.notna(r.lat) and pd.notna(r.lng):
                folium.CircleMarker(
                    [r.lat, r.lng], radius=4 + 16 * (r.orders / mx) ** 0.5,
                    color=PALETTE[0], weight=1, fill=True, fill_opacity=0.6,
                    tooltip=f"{r.customer_city.title()} ({r.customer_state}): {r.orders:,} order",
                ).add_to(fmap)
        try:
            st_folium(fmap, height=440, use_container_width=True, returned_objects=[])
        except TypeError:
            st_folium(fmap, height=440, width=650, returned_objects=[])
        st.caption("Ukuran lingkaran = jumlah order, 30 kota teratas.")

    # Pembayaran
    st.subheader("Metode pembayaran")
    col1, col2 = st.columns(2)
    with col1:
        plot(px.pie(values=pay.values, names=pay.index, hole=0.55, title="Porsi order per metode"), 320)
    with col2:
        aov = (cur.dropna(subset=["main_payment"]).groupby("main_payment")["revenue"].mean()
               .reset_index().sort_values("revenue"))
        plot(px.bar(aov, x="revenue", y="main_payment", orientation="h",
                    title="Rata-rata nilai order per metode",
                    labels={"revenue": "R$", "main_payment": ""}), 320)

# =====================================================
# HALAMAN 3: PRODUK & SELLER
# =====================================================
elif page == "Produk & Seller":
    st.header("Produk & Seller")

    cat = items.groupby("category").agg(
        revenue=("price", "sum"), items=("order_item_id", "count"),
        avg_price=("price", "mean"), review=("review_score", "mean")).reset_index()
    cat = cat.sort_values("revenue", ascending=False)
    top = cat.head(15)
    overall_review = items["review_score"].mean()

    low = top[top["review"] < overall_review - 0.1].sort_values("review")
    lines = [f"Rating rata-rata semua produk <b>{overall_review:.2f}/5</b>."]
    if len(low):
        r = low.iloc[0]
        lines.append(f"Kategori besar dengan rating terendah: <b>{r['category']}</b> ({r['review']:.2f}), "
                     f"revenue {money(r['revenue'])}. Layak diperiksa penyebab ulasan buruknya.")
    insight(lines)

    col1, col2 = st.columns([3, 2])
    with col1:
        fig = px.scatter(top, x="avg_price", y="review", size="revenue", text="category",
                         title="Harga rata-rata vs rating (15 kategori terbesar)",
                         labels={"avg_price": "Harga rata-rata (R$)", "review": "Rating rata-rata"})
        fig.update_traces(textposition="top center", marker=dict(color=PALETTE[0], opacity=0.7))
        fig.add_hline(y=overall_review, line_dash="dot", line_color="gray",
                      annotation_text="rata-rata semua produk")
        plot(fig, 440)
    with col2:
        st.markdown("**15 kategori terbesar**")
        t = top[["category", "revenue", "items", "review"]].rename(columns={
            "category": "Kategori", "revenue": "Revenue (R$)", "items": "Item", "review": "Rating"})
        table(t.round({"Revenue (R$)": 0, "Rating": 2}), height=440)

    # Seller
    st.subheader("Seller")
    sel = items.groupby("seller_id").agg(
        orders=("order_id", "nunique"), revenue=("price", "sum"),
        review=("review_score", "mean"), late=("is_late", "mean"),
        days=("delivery_days", "mean")).reset_index()
    n_top = max(1, int(len(sel) * 0.1))
    top_share = sel["revenue"].nlargest(n_top).sum() / sel["revenue"].sum() * 100
    sel20 = sel[sel["orders"] >= 20]

    c1, c2, c3 = st.columns(3)
    c1.metric("Seller aktif", f"{len(sel):,}")
    c2.metric("Revenue dari 10% seller teratas", f"{top_share:.0f}%")
    c3.metric("Seller dengan ≥ 20 order", f"{len(sel20):,}")

    if len(sel20):
        worst = sel20.nsmallest(10, "review")
        w = worst[["seller_id", "orders", "revenue", "review", "late", "days"]].copy()
        w["seller_id"] = w["seller_id"].str[:8] + "…"
        w["late"] = w["late"] * 100
        w.columns = ["Seller", "Order", "Revenue (R$)", "Rating", "Terlambat (%)", "Lama kirim (hari)"]
        st.markdown("**10 seller dengan rating terendah** (min. 20 order)")
        table(w.round({"Revenue (R$)": 0, "Rating": 2, "Terlambat (%)": 1, "Lama kirim (hari)": 1}))
    else:
        st.info("Belum ada seller dengan minimal 20 order pada rentang ini.")

    # Leads (data asli)
    st.subheader("Konversi leads")
    st.caption("Data leads punya periode sendiri, jadi tidak ikut filter tanggal.")
    if {"mql_id", "origin"} <= set(leads_q.columns) and "mql_id" in leads_c.columns:
        mql = leads_q.merge(leads_c[["mql_id"]].drop_duplicates().assign(closed=True),
                            on="mql_id", how="left")
        mql["closed"] = mql["closed"].fillna(False)
        mql["origin"] = mql["origin"].fillna("unknown")
        n_l, n_c = len(mql), int(mql["closed"].sum())
        by = mql.groupby("origin").agg(leads=("mql_id", "count"), closed=("closed", "sum")).reset_index()
        by["conv"] = by["closed"] / by["leads"] * 100
        by = by[by["leads"] >= 100].sort_values("conv")

        c1, c2, c3 = st.columns(3)
        c1.metric("Marketing qualified leads", f"{n_l:,}")
        c2.metric("Deal berhasil", f"{n_c:,}")
        c3.metric("Konversi", f"{n_c / n_l * 100:.1f}%")
        if len(by):
            best, worst_o = by.iloc[-1], by.iloc[0]
            insight([f"Sumber lead terbaik: <b>{best['origin']}</b> ({best['conv']:.1f}% konversi, {int(best['leads'])} leads). "
                     f"Terendah: <b>{worst_o['origin']}</b> ({worst_o['conv']:.1f}%)."], title="Temuan leads")
            plot(px.bar(by, x="conv", y="origin", orientation="h", text=by["conv"].round(1),
                        title="Konversi lead ke deal per sumber (min. 100 leads)",
                        labels={"conv": "Konversi (%)", "origin": ""}), 340)
    else:
        st.info("Kolom mql_id / origin tidak ditemukan pada data leads.")

# =====================================================
# HALAMAN 4: OPERASIONAL & KEPUASAN
# =====================================================
elif page == "Operasional & Kepuasan":
    st.header("Operasional & Kepuasan")

    dv = cur[cur["delivery_days"].notna()].copy()
    if dv.empty:
        st.warning("Belum ada order terkirim pada rentang ini.")
        st.stop()

    late_rate = dv["is_late"].mean() * 100
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Lama pengiriman rata-rata", f"{dv['delivery_days'].mean():.1f} hari")
    c2.metric("Order terlambat", f"{late_rate:.1f}%")
    c3.metric("Ongkir rata-rata per order", f"R$ {cur['freight'].mean():.1f}")
    c4.metric("Rating rata-rata", f"{cur['review_score'].mean():.2f} / 5")

    labels = ["Tepat waktu / lebih cepat", "Telat 1–3 hari", "Telat 4–7 hari", "Telat > 7 hari"]
    dv["bucket"] = pd.cut(dv["delay_days"], [-np.inf, 0, 3, 7, np.inf], labels=labels)
    bk = dv.groupby("bucket", observed=True).agg(
        review=("review_score", "mean"), orders=("order_id", "count")).reset_index()

    sd = dv.groupby("customer_state").agg(days=("delivery_days", "mean"), orders=("order_id", "count")).reset_index()
    sd = sd[sd["orders"] >= 100].sort_values("days", ascending=False)

    lines = [f"<b>{late_rate:.1f}%</b> order tiba lebih lambat dari estimasi."]
    r = bk.set_index("bucket")["review"]
    if labels[0] in r.index and labels[3] in r.index:
        lines.append(f"Rating turun dari <b>{r[labels[0]]:.2f}</b> (tepat waktu) menjadi "
                     f"<b>{r[labels[3]]:.2f}</b> kalau telat lebih dari 7 hari. "
                     "Ketepatan pengiriman berdampak langsung ke kepuasan.")
    if len(sd) >= 2:
        lines.append(f"Pengiriman paling lama ke <b>{sd.iloc[0]['customer_state']}</b> "
                     f"({sd.iloc[0]['days']:.0f} hari), paling cepat ke "
                     f"<b>{sd.iloc[-1]['customer_state']}</b> ({sd.iloc[-1]['days']:.0f} hari).")
    insight(lines)

    col1, col2 = st.columns(2)
    with col1:
        t = dv[dv["delivery_days"] <= 60]
        fig = px.histogram(t, x="delivery_days", nbins=30, title="Distribusi lama pengiriman",
                           labels={"delivery_days": "Hari (dari order sampai diterima)"})
        fig.add_vline(x=dv["delivery_days"].mean(), line_dash="dash", line_color=PALETTE[3],
                      annotation_text=f"rata-rata {dv['delivery_days'].mean():.1f}")
        fig.update_layout(yaxis_title="Order")
        plot(fig, 360)
    with col2:
        fig = px.bar(bk, x="bucket", y="review", text=bk["review"].round(2),
                     title="Rating berdasarkan ketepatan pengiriman",
                     labels={"bucket": "", "review": "Rating rata-rata"})
        fig.update_yaxes(range=[1, 5])
        fig.update_traces(marker_color=[PALETTE[0], PALETTE[1], PALETTE[3], PALETTE[3]][:len(bk)])
        plot(fig, 360)

    if len(sd):
        t = sd.head(10).sort_values("days")
        plot(px.bar(t, x="days", y="customer_state", orientation="h",
                    title="10 state dengan pengiriman terlama (min. 100 order)",
                    labels={"days": "Rata-rata hari", "customer_state": ""}), 380)

    # Ulasan
    with st.expander("🔎 Baca ulasan negatif per kategori"):
        rv = reviews_all[reviews_all["order_id"].isin(cur["order_id"])]
        rv = rv[(rv["review_score"] <= 2) & rv["review_comment_message"].notna()]
        rv = rv.merge(items_all[["order_id", "category"]].drop_duplicates(), on="order_id")
        cats = rv["category"].value_counts().index.tolist()
        if not cats:
            st.info("Tidak ada ulasan negatif dengan komentar pada rentang ini.")
        else:
            col1, col2 = st.columns([2, 1])
            pick = col1.selectbox("Kategori", cats)
            tr = col2.checkbox("Terjemahkan ke Bahasa Indonesia")
            s = (rv[rv["category"] == pick].sort_values("review_creation_date", ascending=False).head(10))
            msg = s["review_comment_message"].astype(str)
            if tr:
                with st.spinner("Menerjemahkan…"):
                    msg = msg.apply(translate_text)
            out = pd.DataFrame({"Rating": s["review_score"].astype(int).values,
                                "Komentar": msg.values,
                                "Tanggal": pd.to_datetime(s["review_creation_date"]).dt.strftime("%d %b %Y").values})
            table(out)

st.markdown("---")
st.caption("📊 NAH Team | SSDC E-Commerce 2025 · Mata uang dalam Real Brasil (R$)")
