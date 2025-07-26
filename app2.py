import streamlit as st
from utils.data_loader import load_all_data
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np
import folium
from streamlit_folium import st_folium
from deep_translator import GoogleTranslator


# Konfigurasi dasar
st.set_page_config(
    page_title="E-Commerce Dashboard", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS untuk styling yang lebih baik
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .stMetric > label {
        font-size: 0.9rem !important;
        font-weight: 600 !important;
    }
    .stMetric > div {
        font-size: 1.8rem !important;
        font-weight: 700 !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("📊 Dashboard E-Commerce SSDC")

# Load data dengan error handling
@st.cache_data
def load_data():
    try:
        return load_all_data()
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return None

data = load_data()
if data is None:
    st.stop()

# Extract data
orders = data["orders"]
order_items = data["order_items"]
payments = data["order_payments"]
customers = data["customers"]
products = data["products"]
geolocation = data["geolocation"]
order_reviews = data["order_reviews"]
product_cat = data["product_cat"]
sellers = data["sellers"]
leads_qualified = data["leads_qualified"]
leads_closed = data["leads_closed"]
product_category_name_translation = data['product_cat']

# Data preprocessing
@st.cache_data
def preprocess_data():
    # Convert timestamp columns
    orders_clean = orders.copy()
    orders_clean['order_purchase_timestamp'] = pd.to_datetime(orders_clean['order_purchase_timestamp'], errors='coerce')
    
    # Create month column
    orders_clean['month'] = orders_clean['order_purchase_timestamp'].dt.to_period("M").astype(str)
    orders_clean['year_month'] = orders_clean['order_purchase_timestamp'].dt.strftime('%Y-%m')
    
    # Merge orders with payments for revenue calculation
    orders_payments = orders_clean.merge(payments, on='order_id', how='left')
    
    # Merge with order_items for product analysis
    orders_items = orders_clean.merge(order_items, on='order_id', how='left')
    
    return orders_clean, orders_payments, orders_items

orders_processed, orders_payments, orders_items = preprocess_data()

@st.cache_data(show_spinner=False)
def translate_text(text, target_lang='id'):
    try:
        return GoogleTranslator(source='auto', target=target_lang).translate(text)
    except:
        return text
    
# Sidebar Navigation
st.sidebar.title("📋 Dashboard Menu")

# Page selection
page = st.sidebar.radio(
    "Pilih halaman:",
    [
        "Executive Overview",
        "Customer & Market Analysis",
        "Product & Leads Performance", 
        "Customer Preference Analysis",
        "Operational Excellence",
        "Strategic Recommendations"
    ]
)


# Date Filter Section
st.sidebar.markdown("---")
st.sidebar.subheader(" Filter Periode")

# Check if date column exists and has valid data
has_valid_dates = (
    'order_purchase_timestamp' in orders_processed.columns and 
    not orders_processed['order_purchase_timestamp'].isna().all()
)

if has_valid_dates:
    # Get date range
    min_date = orders_processed['order_purchase_timestamp'].min().date()
    max_date = orders_processed['order_purchase_timestamp'].max().date()
    
    # Separate date inputs
    start_date = st.sidebar.date_input(
        "📅 Tanggal Mulai:",
        value=min_date,
        min_value=min_date,
        max_value=max_date
    )
    
    end_date = st.sidebar.date_input(
        "📅 Tanggal Selesai:",
        value=max_date,
        min_value=min_date,
        max_value=max_date
    )
    
    # Validate date range
    if start_date <= end_date:
        
        # Filter main orders data
        date_mask = (
            (orders_processed['order_purchase_timestamp'].dt.date >= start_date) & 
            (orders_processed['order_purchase_timestamp'].dt.date <= end_date)
        )
        orders_filtered = orders_processed[date_mask]
        
        # Get filtered order IDs for related data
        filtered_order_ids = orders_filtered['order_id'].tolist()
        orders_payments_filtered = orders_payments[orders_payments['order_id'].isin(filtered_order_ids)]
        orders_items_filtered = orders_items[orders_items['order_id'].isin(filtered_order_ids)]
        
        # Show filter info
        st.sidebar.info(f"📊 {len(orders_filtered):,} pesanan dipilih")
    else:
        # Show error if date range is invalid
        st.sidebar.error("⚠️ Tanggal mulai tidak boleh lebih besar dari tanggal selesai")
        orders_filtered = orders_processed
        orders_payments_filtered = orders_payments  
        orders_items_filtered = orders_items
else:
    # Use all data if no valid dates
    orders_filtered = orders_processed
    orders_payments_filtered = orders_payments
    orders_items_filtered = orders_items
    st.sidebar.warning("⚠️ Data tanggal tidak tersedia")

    
# ================================
# 📌 HALAMAN: EXECUTIVE OVERVIEW
# ================================
from datetime import timedelta

# Tentukan periode sebelumnya dengan panjang waktu yang sama
period_length = end_date - start_date
prev_start_date = start_date - period_length - timedelta(days=1)
prev_end_date = start_date - timedelta(days=1)

# Filter data untuk periode sebelumnya
prev_mask = (
    (orders_processed['order_purchase_timestamp'].dt.date >= prev_start_date) &
    (orders_processed['order_purchase_timestamp'].dt.date <= prev_end_date)
)
prev_orders_data = orders_processed[prev_mask]
prev_order_ids = prev_orders_data['order_id'].tolist()

prev_payments_data = orders_payments[orders_payments['order_id'].isin(prev_order_ids)]
# Fungsi untuk hitung growth
def calc_growth(current, previous):
    if previous > 0:
        return f"{((current - previous) / previous) * 100:.1f}%"
    else:
        return "N/A"

# --- EXECUTIVE OVERVIEW ---
if page == "Executive Overview":
    st.header("📌 Executive Overview")
    col1, col2, col3, col4 = st.columns(4)
    
    # Revenue
    with col1:
        total_revenue = orders_payments_filtered['payment_value'].sum()
        prev_revenue = prev_payments_data['payment_value'].sum() if not prev_payments_data.empty else 0
        st.metric("💰 Total Revenue", f"€ {total_revenue:,.0f}", delta=calc_growth(total_revenue, prev_revenue))

    # Orders
    with col2:
        total_orders = orders_filtered['order_id'].nunique()
        prev_orders = prev_orders_data['order_id'].nunique() if not prev_orders_data.empty else 0
        st.metric("📦 Total Orders", f"{total_orders:,}", delta=calc_growth(total_orders, prev_orders))

    # Customers
    with col3:
        total_customers = orders_filtered['customer_id'].nunique()
        prev_customers = prev_orders_data['customer_id'].nunique() if not prev_orders_data.empty else 0
        st.metric("🧑‍🤝‍🧑 Unique Customers", f"{total_customers:,}", delta=calc_growth(total_customers, prev_customers))

    # AOV
    with col4:
        avg_order_value = orders_payments_filtered['payment_value'].mean() or 0
        prev_avg = prev_payments_data['payment_value'].mean() or 0
        st.metric("💳 Avg Order Value", f"€ {avg_order_value:,.0f}", delta=calc_growth(avg_order_value, prev_avg))

    # ===================
    # Orders per Month - Improved
    # ===================
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📈 Order Volume & Revenue Trend")
        
        # Aggregate data by month
        monthly_stats = orders_payments_filtered.groupby('year_month').agg({
            'order_id': 'nunique',
            'payment_value': 'sum'
        }).reset_index()
        
        # Create dual-axis chart
        fig_trend = go.Figure()
        
        # Add orders line
        fig_trend.add_trace(go.Scatter(
            x=monthly_stats['year_month'],
            y=monthly_stats['order_id'],
            mode='lines+markers',
            name='Orders',
            line=dict(color='#1f77b4', width=3),
            yaxis='y'
        ))
        
        # Add revenue bars
        fig_trend.add_trace(go.Bar(
            x=monthly_stats['year_month'],
            y=monthly_stats['payment_value'],
            name='Revenue',
            opacity=0.7,
            yaxis='y2'
        ))
        
        # Update layout
        fig_trend.update_layout(
            title='Monthly Orders and Revenue Trend',
            xaxis_title='Month',
            yaxis=dict(title='Orders', side='left'),
            yaxis2=dict(title='Revenue (€)', side='right', overlaying='y'),
            hovermode='x unified',
            height=400
        )
        
        st.plotly_chart(fig_trend, use_container_width=True)
    
    with col2:
        st.subheader("📊 Quick Stats")
        
        # Additional metrics
        conversion_rate = (total_orders / total_customers * 100) if total_customers > 0 else 0
        st.metric("🎯 Orders per Customer", f"{conversion_rate:.1f}%")
        
        # Average items per order
        avg_items = orders_items_filtered.groupby('order_id')['order_item_id'].count().mean()
        st.metric("📦 Avg Items per Order", f"{avg_items:.1f}")
        
        # Top payment method
        top_payment = payments['payment_type'].value_counts().index[0] if not payments.empty else "N/A"
        st.metric("💳 Top Payment Method", top_payment)

    # ===================
    # New vs Returning Customers - Fixed
    # ===================
    st.subheader("👥 Customer Acquisition Analysis")
    
    # Calculate first order date for each customer
    first_order = orders_filtered.groupby('customer_id')['order_purchase_timestamp'].min().reset_index()
    first_order['first_order_month'] = first_order['order_purchase_timestamp'].dt.strftime('%Y-%m')
    
    # Merge with all orders
    orders_with_first = orders_filtered.merge(first_order, on='customer_id', suffixes=('', '_first'))
    orders_with_first['customer_type'] = orders_with_first.apply(
        lambda x: 'New' if x['year_month'] == x['first_order_month'] else 'Returning', axis=1
    )
    
    # Group by month and customer type
    customer_trend = orders_with_first.groupby(['year_month', 'customer_type']).size().reset_index(name='count')
    
    fig_customers = px.bar(
        customer_trend, 
        x='year_month', 
        y='count', 
        color='customer_type',
        barmode='group',
        title='New vs Returning Customers Over Time',
        labels={'year_month': 'Month', 'count': 'Number of Orders'}
    )
    fig_customers.update_layout(height=400)
    st.plotly_chart(fig_customers, use_container_width=True)

    # ===================
    # 📌 Top States by Orders (Bar Chart + Table Sejajar)
    # ===================
    st.subheader("🗺️ Top States by Orders")

    # Merge customers with orders to get state info
    customer_orders = orders_filtered.merge(customers, on='customer_id', how='left')
    # Pastikan payment_value numerik
    orders_payments_filtered['payment_value'] = pd.to_numeric(orders_payments_filtered['payment_value'], errors='coerce')
    # Join customer_orders dengan payments untuk dapatkan payment_value
    customer_orders_payments = customer_orders.merge(
        orders_payments_filtered[['order_id', 'payment_value']],
        on='order_id',
        how='left'
    )

    # Hitung total_orders & total_revenue per state
    state_orders = customer_orders_payments.groupby('customer_state').agg(
        total_orders=('order_id', 'count'),
        total_revenue=('payment_value', 'sum')
    ).reset_index()

    # Sorting biar rapi
    state_orders = state_orders.sort_values('total_orders', ascending=False)
    # state_orders = customer_orders.groupby('customer_state').agg(
    #     total_orders=('order_id', 'count'),
    #     total_revenue=('order_id', lambda x: orders_payments_filtered[orders_payments_filtered['order_id'].isin(x.index)]['payment_value'].sum())
    # ).reset_index()

    # state_orders = state_orders.sort_values('total_orders', ascending=False)

    # Dropdown pilihan jumlah state
    state_count = len(state_orders)
    state_options = [i for i in range(5, state_count + 5, 5) if i <= state_count] + (["All"] if state_count % 5 != 0 else [])
    selected_state = st.selectbox("Pilih jumlah states:", state_options, index=0)
    top_states = state_orders if selected_state == "All" else state_orders.head(int(selected_state))

    # Layout sejajar (bar chart kiri, tabel kanan)
    col1, col2 = st.columns([2, 1])  # 2:1 rasio lebar
    with col1:
        fig_states = px.bar(
            top_states,
            x='total_orders',
            y='customer_state',
            orientation='h',
            title='Orders by State',
            labels={'customer_state': 'State', 'total_orders': 'Total Orders'}
        )
        fig_states.update_layout(height=450)
        st.plotly_chart(fig_states, use_container_width=True)

    with col2:
        st.write("###### State Summary")
        st.dataframe(
            top_states.rename(columns={
                "customer_state": "State",
                "total_orders": "Total Orders",
                "total_revenue": "Total Revenue"
            }),
            use_container_width=True
        )

    # ===================
    # 📌 Top Product Categories (Bar Chart + Table Sejajar)
    # ===================
    st.subheader("🏆 Top Product Categories")

    if not products.empty and not order_items.empty:
        product_sales = order_items.merge(products, on='product_id', how='left')
        category_sales = product_sales.groupby('product_category_name').agg(
            items_sold=('order_item_id', 'count')
        ).reset_index().rename(columns={'product_category_name': 'Category'})

        category_sales = category_sales.sort_values('items_sold', ascending=False)
        category_count = len(category_sales)
        category_options = [i for i in range(5, category_count + 5, 5) if i <= category_count] + (["All"] if category_count % 5 != 0 else [])
        selected_category = st.selectbox("Pilih jumlah kategori:", category_options, index=0)

        top_categories = category_sales if selected_category == "All" else category_sales.head(int(selected_category))

        # Layout sejajar (bar chart kiri, tabel kanan)
        col1, col2 = st.columns([2, 1])  # 2:1 rasio lebar
        with col1:
            fig_categories = px.bar(
                top_categories,
                x='items_sold',
                y='Category',
                orientation='h',
                title='Top Product Categories by Items Sold',
                labels={'items_sold': 'Items Sold'}
            )
            fig_categories.update_layout(height=450)
            st.plotly_chart(fig_categories, use_container_width=True)

        with col2:
            st.write("###### Category Summary")
            st.dataframe(top_categories, use_container_width=True)
    else:
        st.info("Product category data not available")

    # ===================
    # Performance Summary
    # ===================
    st.markdown("---")
    st.subheader("📋 Performance Summary")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.info(f"""
        **Revenue Performance**
        - Total Revenue: € {total_revenue:,.0f}
        - Average Order Value: € {avg_order_value:,.0f}
        - Growth Rate: {growth_rate:.1f}%
        """)
    
    with col2:
        st.success(f"""
        **Customer Insights**
        - Total Customers: {total_customers:,}
        - Orders per Customer: {conversion_rate:.1f}%
        - Customer Growth: {customers_growth:.1f}%
        """)
    
    with col3:
        st.warning(f"""
        **Operational Metrics**
        - Total Orders: {total_orders:,}
        - Avg Items per Order: {avg_items:.1f}
        - Order Growth: {orders_growth:.1f}%
        """)

# ================================
# 📌 HALAMAN: CUSTOMER & MARKET ANALYSIS
# ================================
elif page == "Customer & Market Analysis":
    st.header("📌 Customer & Market Analysis")
    st.markdown("*Memahami customer behavior dan market opportunity*")
    
    # ===================
    # Customer Segmentation - RFM Analysis
    # ===================
    st.subheader("🎯 Customer Segmentation (RFM Analysis)")
    
    @st.cache_data
    def calculate_rfm():
        # Calculate RFM metrics
        current_date = orders_filtered['order_purchase_timestamp'].max()
        
        rfm_data = orders_payments_filtered.groupby('customer_id').agg({
            'order_purchase_timestamp': lambda x: (current_date - x.max()).days,  # Recency
            'order_id': 'nunique',  # Frequency
            'payment_value': 'sum'  # Monetary
        }).reset_index()
        
        rfm_data.columns = ['customer_id', 'recency', 'frequency', 'monetary']
        
        # Create RFM scores (1-5 scale)
        rfm_data['R_score'] = pd.qcut(rfm_data['recency'], 5, labels=[5,4,3,2,1])
        rfm_data['F_score'] = pd.qcut(rfm_data['frequency'].rank(method='first'), 5, labels=[1,2,3,4,5])
        rfm_data['M_score'] = pd.qcut(rfm_data['monetary'], 5, labels=[1,2,3,4,5])
        
        # Create RFM segment
        rfm_data['RFM_Score'] = rfm_data['R_score'].astype(str) + rfm_data['F_score'].astype(str) + rfm_data['M_score'].astype(str)
        
        # Define customer segments
        def segment_customers(row):
            if row['RFM_Score'] in ['555', '554', '544', '545', '454', '455', '445']:
                return 'Champions'
            elif row['RFM_Score'] in ['543', '444', '435', '355', '354', '345', '344', '335']:
                return 'Loyal Customers'
            elif row['RFM_Score'] in ['553', '551', '552', '541', '542', '533', '532', '531', '452', '451']:
                return 'Potential Loyalists'
            elif row['RFM_Score'] in ['512', '511', '422', '421', '412', '411', '311']:
                return 'New Customers'
            elif row['RFM_Score'] in ['155', '154', '144', '214', '215', '115', '114']:
                return 'At Risk'
            elif row['RFM_Score'] in ['155', '154', '144', '214', '215', '115']:
                return 'Cannot Lose Them'
            else:
                return 'Others'
        
        rfm_data['segment'] = rfm_data.apply(segment_customers, axis=1)
        return rfm_data
    
    try:
        rfm_data = calculate_rfm()
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # RFM Scatter Plot
            fig_rfm = px.scatter(
                rfm_data, 
                x='frequency', 
                y='monetary',
                size='recency',
                color='segment',
                title='Customer Segmentation (RFM Analysis)',
                labels={
                    'frequency': 'Frequency (Orders)',
                    'monetary': 'Monetary Value (€)',
                    'recency': 'Recency (Days)'
                },
                height=400
            )
            st.plotly_chart(fig_rfm, use_container_width=True)
        
        with col2:
            # Segment Distribution
            segment_counts = rfm_data['segment'].value_counts()
            fig_segments = px.pie(
                values=segment_counts.values,
                names=segment_counts.index,
                title='Customer Segment Distribution'
            )
            st.plotly_chart(fig_segments, use_container_width=True)
            
    except Exception as e:
        st.error(f"Error in RFM analysis: {str(e)}")
        st.info("Showing alternative customer analysis...")

    # ===================
    # 📌 Geographic Distribution - Improved Layout with Real Map
    # ===================
    
    st.subheader("🗺️ Top Cities by Orders")

    # Merge orders & customers untuk info city
    customer_geo = orders_filtered.merge(customers, on='customer_id', how='left')

    # Hitung total orders & unique customers per city
    city_stats = customer_geo.groupby(['customer_city', 'customer_state']).agg(
        total_orders=('order_id', 'nunique'),
        unique_customers=('customer_id', 'nunique')
    ).reset_index()

    # Ambil satu titik (pertama) per city-state
    geo_city_unique = geolocation.drop_duplicates(subset=['geolocation_city', 'geolocation_state'])

    # Merge dengan city stats
    city_geo = city_stats.merge(
        geo_city_unique[['geolocation_city', 'geolocation_state', 'geolocation_lat', 'geolocation_lng']],
        left_on=['customer_city', 'customer_state'],
        right_on=['geolocation_city', 'geolocation_state'],
        how='left'
    )


    # Sorting by total orders
    city_geo = city_geo.sort_values('total_orders', ascending=False)

    # Dropdown jumlah city yang ditampilkan
    city_count = len(city_geo)
    city_options = [i for i in range(5, city_count + 5, 5) if i <= city_count] + (["All"] if city_count % 5 != 0 else [])
    selected_city_count = st.selectbox("Tampilkan jumlah kota:", city_options, index=0)

    if selected_city_count == "All":
        top_cities = city_geo
    else:
        top_cities = city_geo.head(int(selected_city_count))

    # ========== Bar Chart & Map ==========
    st.markdown("#### 📊 Top Cities by Orders")
    col1, col2 = st.columns([2, 2])

    with col1:
        fig_cities = px.bar(
            top_cities,
            x='total_orders',
            y='customer_city',
            orientation='h',
            title='Top Cities by Orders',
            labels={'total_orders': 'Total Orders', 'customer_city': 'City'},
            color='total_orders',
            color_continuous_scale='Blues'
        )
        fig_cities.update_layout(height=450)
        st.plotly_chart(fig_cities, use_container_width=True)

    with col2:
        st.markdown("#### 🗺️ Map: Cities by Total Orders")
        m_city = folium.Map(location=[-2.5489, 118.0149], zoom_start=5, tiles="CartoDB positron")
        for _, row in top_cities.iterrows():
            if pd.notna(row['geolocation_lat']) and pd.notna(row['geolocation_lng']):
                folium.CircleMarker(
                    location=[row['geolocation_lat'], row['geolocation_lng']],
                    radius=6,  # <<< FIX ukuran titik jadi sama semua
                    color='blue',
                    fill=True,
                    fill_opacity=0.7,
                    popup=folium.Popup(f"""
                        <b>City:</b> {row['customer_city']}<br>
                        <b>Total Orders:</b> {row['total_orders']}<br>
                    """, max_width=250)
                ).add_to(m_city)
        st_folium(m_city, width=700, height=500)

    # ===================
    # 📌 Top States by Orders
    # ===================
    st.subheader("🗺️ Top States by Orders")

    # Hitung total orders & revenue per state
    state_geo = customer_geo.groupby('customer_state').agg(
        total_orders=('order_id', 'nunique'),
        total_revenue=('order_id', lambda x: orders_payments_filtered[orders_payments_filtered['order_id'].isin(x.index)]['payment_value'].sum())
    ).reset_index()

    # Ambil satu titik (pertama) per state
    geo_state_unique = geolocation.drop_duplicates(subset=['geolocation_state'])

    # Merge dengan state stats
    state_geo = state_geo.merge(
        geo_state_unique[['geolocation_state', 'geolocation_lat', 'geolocation_lng']],
        left_on='customer_state',
        right_on='geolocation_state',
        how='left'
    )


    # Sorting by total orders
    state_geo = state_geo.sort_values('total_orders', ascending=False)

    # Dropdown jumlah state yang ditampilkan
    state_count = len(state_geo)
    state_options = [i for i in range(5, state_count + 5, 5) if i <= state_count] + (["All"] if state_count % 5 != 0 else [])
    selected_state_count = st.selectbox("Tampilkan jumlah provinsi:", state_options, index=0)

    if selected_state_count == "All":
        top_states = state_geo
    else:
        top_states = state_geo.head(int(selected_state_count))

    # ========== Bar Chart & Map ==========
    st.markdown("#### 📊 Top States by Orders")
    col1, col2 = st.columns([2, 2])

    with col1:
        fig_states = px.bar(
            top_states,
            x='total_orders',
            y='customer_state',
            orientation='h',
            title='Top States by Orders',
            labels={'total_orders': 'Total Orders', 'customer_state': 'State'},
            color='total_orders',
            color_continuous_scale='Blues'
        )
        fig_states.update_layout(height=450)
        st.plotly_chart(fig_states, use_container_width=True)

    with col2:
        st.markdown("#### 🗺️ Map: States by Total Orders")
        m_state = folium.Map(location=[-2.5489, 118.0149], zoom_start=5, tiles="CartoDB positron")
        for _, row in top_states.iterrows():
            if pd.notna(row['geolocation_lat']) and pd.notna(row['geolocation_lng']):
                folium.CircleMarker(
                    location=[row['geolocation_lat'], row['geolocation_lng']],
                    radius=8,  # <<< FIX ukuran titik jadi sama semua
                    color='green',
                    fill=True,
                    fill_opacity=0.7,
                    popup=folium.Popup(f"""
                        <b>State:</b> {row['customer_state']}<br>
                        <b>Total Orders:</b> {row['total_orders']}<br>
                    """, max_width=250)
                ).add_to(m_state)
        st_folium(m_state, width=700, height=500)


    # ===================
    # Customer Lifetime Value & Purchase Frequency
    # ===================
    st.subheader("💰 Customer Lifetime Value & Purchase Behavior")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Customer Lifetime Value Distribution
        clv_data = orders_payments_filtered.groupby('customer_id').agg({
            'payment_value': 'sum',
            'order_id': 'nunique'
        }).reset_index()
        clv_data.columns = ['customer_id', 'total_spent', 'order_count']
        
        fig_clv = px.histogram(
            clv_data,
            x='total_spent',
            nbins=50,
            title='Customer Lifetime Value Distribution',
            labels={'total_spent': 'Total Spent (€)', 'count': 'Number of Customers'}
        )
        fig_clv.update_layout(height=350)
        st.plotly_chart(fig_clv, use_container_width=True)
        
        # CLV Statistics
        avg_clv = clv_data['total_spent'].mean()
        median_clv = clv_data['total_spent'].median()
        st.metric("Average CLV", f"€ {avg_clv:,.0f}")
        st.metric("Median CLV", f"€ {median_clv:,.0f}")
    
    with col2:
        # Purchase Frequency
        fig_freq = px.histogram(
            clv_data,
            x='order_count',
            nbins=20,
            title='Purchase Frequency Distribution',
            labels={'order_count': 'Number of Orders', 'count': 'Number of Customers'}
        )
        fig_freq.update_layout(height=350)
        st.plotly_chart(fig_freq, use_container_width=True)
        
        # Frequency Statistics
        avg_freq = clv_data['order_count'].mean()
        repeat_customers = (clv_data['order_count'] > 1).sum()
        repeat_rate = repeat_customers / len(clv_data) * 100
        st.metric("Avg Orders per Customer", f"{avg_freq:.1f}")
        st.metric("Repeat Customer Rate", f"{repeat_rate:.1f}%")

    # ===================
    # Payment Preferences
    # ===================
    st.subheader("💳 Payment Method Preferences")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Payment method distribution
        payment_dist = payments['payment_type'].value_counts()
        fig_payment = px.pie(
            values=payment_dist.values,
            names=payment_dist.index,
            title='Payment Method Distribution'
        )
        st.plotly_chart(fig_payment, use_container_width=True)
    
    with col2:
        # Payment method trend over time
        payment_trend = orders_payments_filtered.groupby(['year_month', 'payment_type']).size().reset_index(name='count')
        fig_payment_trend = px.line(
            payment_trend,
            x='year_month',
            y='count',
            color='payment_type',
            title='Payment Method Trends Over Time',
            labels={'year_month': 'Month', 'count': 'Number of Transactions'}
        )
        st.plotly_chart(fig_payment_trend, use_container_width=True)
    # ===================
    # Customer Insights Summary
    # ===================
    st.markdown("---")
    st.subheader("📊 Customer Insights Summary")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        total_customers = orders_filtered['customer_id'].nunique()
        avg_clv = clv_data['total_spent'].mean() if 'clv_data' in locals() else 0
        st.info(f"""
        **Customer Base**
        - Total Customers: {total_customers:,}
        - Average CLV: € {avg_clv:,.0f}
        - Repeat Rate: {repeat_rate:.1f}%
        """)
    
    with col2:
        top_payment = payments['payment_type'].value_counts().index[0]
        top_state = customer_geo.groupby('customer_state').size().idxmax()
        st.success(f"""
        **Market Preferences**
        - Top Payment: {top_payment}
        - Top State: {top_state}
        - Avg Orders: {avg_freq:.1f}
        """)
    
    with col3:
        if 'segment_counts' in locals():
            top_segment = segment_counts.index[0]
            segment_pct = segment_counts.iloc[0] / segment_counts.sum() * 100
            st.warning(f"""
            **Segmentation**
            - Top Segment: {top_segment}
            - Segment %: {segment_pct:.1f}%
            - Total Segments: {len(segment_counts)}
            """)
        else:
            st.warning("**Segmentation data not available**")

# ================================
# 📌 HALAMAN: PRODUCT & LEADS PERFORMANCE
# ================================
elif page == "Product & Leads Performance":
    st.header("📌 Product & Leads Performance")
    st.markdown("*Mengoptimalkan product mix dan inventory management*")
    
    # ===================
    # Category Performance - Treemap
    # ===================
    st.subheader("📊 Category Performance")
    
    @st.cache_data
    def get_category_performance():
        if not products.empty and not order_items.empty:
            # Merge order items with products
            product_sales = order_items.merge(products, on='product_id', how='left')
            
            # Filter by date range
            order_ids_filtered = orders_filtered['order_id'].tolist()
            product_sales_filtered = product_sales[product_sales['order_id'].isin(order_ids_filtered)]
            
            # Calculate category performance
            category_performance = product_sales_filtered.groupby('product_category_name').agg({
                'order_item_id': 'count',
                'price': 'sum',
                'product_id': 'nunique'
            }).reset_index()
            
            category_performance.columns = ['category', 'total_items_sold', 'total_revenue', 'unique_products']
            category_performance = category_performance.sort_values('total_revenue', ascending=False)
            
            return category_performance
        return pd.DataFrame()
    
    category_perf = get_category_performance()
    
    if not category_perf.empty:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Treemap for category revenue
            fig_treemap = px.treemap(
                category_perf.head(15),
                path=['category'],
                values='total_revenue',
                title='Revenue by Category (Top 15)',
                color='total_items_sold',
                color_continuous_scale='Viridis'
            )
            fig_treemap.update_layout(height=400)
            st.plotly_chart(fig_treemap, use_container_width=True)
        
        with col2:
            # Top categories table
            st.write("**Top 10 Categories by Revenue**")
            top_categories = category_perf.head(10)[['category', 'total_revenue', 'total_items_sold']]
            top_categories['total_revenue'] = top_categories['total_revenue'].apply(lambda x: f"€ {x:,.0f}")
            st.dataframe(top_categories, use_container_width=True)
    else:
        st.info("Product category data not available")

    # ===================
    # ⭐ Product Rating vs Sales Performance
    # ===================
    st.subheader("⭐ Product Rating vs Sales Performance")

    @st.cache_data
    def get_product_rating_sales():
        if not products.empty and not order_items.empty and not order_reviews.empty:
            # Gabungkan order_items dengan produk
            product_sales = order_items.merge(products, on='product_id', how='left')

            # Filter berdasarkan order_id dalam rentang tanggal yang dipilih
            order_ids_filtered = orders_filtered['order_id'].tolist()
            product_sales_filtered = product_sales[product_sales['order_id'].isin(order_ids_filtered)]

            # Hitung volume penjualan dan pendapatan
            product_metrics = product_sales_filtered.groupby(['product_id', 'product_category_name']).agg({
                'order_item_id': 'count',
                'price': 'sum'
            }).reset_index()

            # Tambahkan atribut produk tambahan (jika tersedia)
            selected_cols = ['product_id', 'product_name_lenght', 'product_description_lenght',
                            'product_photos_qty', 'product_weight_g', 'product_length_cm',
                            'product_height_cm', 'product_width_cm']
            selected_cols = [col for col in selected_cols if col in products.columns]
            product_metrics = product_metrics.merge(products[selected_cols], on='product_id', how='left')

            # Gabungkan dengan order_reviews untuk hitung rata-rata rating produk
            reviews_joined = order_items.merge(order_reviews[['order_id', 'review_score']], on='order_id', how='left')
            avg_rating = reviews_joined.groupby('product_id')['review_score'].mean().reset_index()
            avg_rating.rename(columns={'review_score': 'avg_rating'}, inplace=True)

            # Gabungkan dengan metrics
            product_metrics = product_metrics.merge(avg_rating, on='product_id', how='left')

            # Rename kolom untuk visualisasi
            product_metrics = product_metrics.rename(columns={
                'product_category_name': 'category',
                'order_item_id': 'sales_volume',
                'price': 'total_revenue',
                'product_name_lenght': 'name_length',
                'product_description_lenght': 'description_length',
                'product_photos_qty': 'photos_qty',
                'product_weight_g': 'weight_g',
                'product_length_cm': 'length_cm',
                'product_height_cm': 'height_cm',
                'product_width_cm': 'width_cm'
            })

            return product_metrics
        return pd.DataFrame()

    # Panggil data
    product_rating_sales = get_product_rating_sales()

    # Visualisasi
    if not product_rating_sales.empty:
        fig1 = px.scatter(
            product_rating_sales,
            x='avg_rating',
            y='sales_volume',
            size='total_revenue',
            color='category',
            title='⭐ Average Rating vs Sales Volume',
            labels={'avg_rating': 'Average Rating', 'sales_volume': 'Sales Volume'}
        )
        st.plotly_chart(fig1, use_container_width=True)

        fig2 = px.scatter(
            product_rating_sales,
            x='avg_rating',
            y='total_revenue',
            size='sales_volume',
            color='category',
            title='💰 Average Rating vs Total Revenue',
            labels={'avg_rating': 'Average Rating', 'total_revenue': 'Total Revenue'}
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Data belum tersedia atau tidak lengkap.")


    # ===================
    # Lead Funnel Analysis (Simulated)
    # ===================
    st.subheader("🔄 Lead Conversion Funnel")
    
    # Since we don't have actual lead data, we'll simulate it based on product categories
    @st.cache_data
    def simulate_lead_funnel():
        if not category_perf.empty:
            # Simulate lead data based on category performance
            funnel_data = category_perf.head(10).copy()
            
            # Simulate funnel stages
            funnel_data['leads_generated'] = funnel_data['total_items_sold'] * np.random.uniform(2, 5, len(funnel_data))
            funnel_data['leads_qualified'] = funnel_data['leads_generated'] * np.random.uniform(0.3, 0.7, len(funnel_data))
            funnel_data['leads_closed'] = funnel_data['leads_qualified'] * np.random.uniform(0.1, 0.4, len(funnel_data))
            
            # Calculate conversion rates
            funnel_data['qualification_rate'] = funnel_data['leads_qualified'] / funnel_data['leads_generated']
            funnel_data['closing_rate'] = funnel_data['leads_closed'] / funnel_data['leads_qualified']
            funnel_data['overall_conversion'] = funnel_data['leads_closed'] / funnel_data['leads_generated']
            
            return funnel_data
        return pd.DataFrame()
    
    lead_funnel = simulate_lead_funnel()
    
    if not lead_funnel.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            # Funnel visualization
            total_leads = lead_funnel['leads_generated'].sum()
            total_qualified = lead_funnel['leads_qualified'].sum()
            total_closed = lead_funnel['leads_closed'].sum()
            
            fig_funnel = go.Figure(go.Funnel(
                y=['Leads Generated', 'Leads Qualified', 'Leads Closed'],
                x=[total_leads, total_qualified, total_closed],
                textinfo="value+percent initial"
            ))
            fig_funnel.update_layout(title='Overall Lead Conversion Funnel')
            st.plotly_chart(fig_funnel, use_container_width=True)
        
        with col2:
            # Conversion rates by category
            fig_conversion = px.bar(
                lead_funnel.head(8),
                x='category',
                y='overall_conversion',
                title='Conversion Rate by Category',
                labels={'overall_conversion': 'Conversion Rate', 'category': 'Category'}
            )

            fig_conversion.update_layout(xaxis=dict(tickangle=45))
            st.plotly_chart(fig_conversion, use_container_width=True)


    # ===================
    # Lead Segmentation (Simulated)
    # ===================
    st.subheader("🎯 Lead Segmentation")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Simulated lead segmentation by business type
        business_segments = {
            'Retail': 35,
            'Wholesale': 25,
            'E-commerce': 20,
            'B2B': 15,
            'Others': 5
        }
        
        fig_segments = px.pie(
            values=list(business_segments.values()),
            names=list(business_segments.keys()),
            title='Lead Segmentation by Business Type'
        )
        st.plotly_chart(fig_segments, use_container_width=True)
    
    with col2:
        # Lead origin simulation
        lead_origins = {
            'Organic Search': 30,
            'Social Media': 25,
            'Email Campaign': 20,
            'Referral': 15,
            'Direct': 10
        }
        
        fig_origins = px.bar(
            x=list(lead_origins.keys()),
            y=list(lead_origins.values()),
            title='Lead Sources Distribution',
            labels={'x': 'Lead Source', 'y': 'Percentage (%)'}
        )
        st.plotly_chart(fig_origins, use_container_width=True)

    # ===================
    # Inventory Status (Simulated)
    # ===================
    st.subheader("📦 Inventory Status Overview")
    
    if not category_perf.empty:
        col1, col2, col3 = st.columns(3)
        
        # Simulate inventory levels
        inventory_status = {
            'In Stock': 65,
            'Low Stock': 25,
            'Out of Stock': 10
        }
        
        with col1:
            fig_stock = go.Figure(go.Indicator(
                mode="gauge+number",
                value=inventory_status['In Stock'],
                title={'text': "In Stock %"},
                gauge={'axis': {'range': [None, 100]},
                       'bar': {'color': "green"},
                       'steps': [{'range': [0, 50], 'color': "lightgray"},
                                {'range': [50, 80], 'color': "yellow"}],
                       'threshold': {'line': {'color': "red", 'width': 4},
                                   'thickness': 0.75, 'value': 90}}
            ))
            fig_stock.update_layout(height=300)
            st.plotly_chart(fig_stock, use_container_width=True)
        
        with col2:
            fig_low_stock = go.Figure(go.Indicator(
                mode="gauge+number",
                value=inventory_status['Low Stock'],
                title={'text': "Low Stock %"},
                gauge={'axis': {'range': [None, 50]},
                       'bar': {'color': "orange"},
                       'steps': [{'range': [0, 20], 'color': "lightgray"},
                                {'range': [20, 35], 'color': "yellow"}],
                       'threshold': {'line': {'color': "red", 'width': 4},
                                   'thickness': 0.75, 'value': 40}}
            ))
            fig_low_stock.update_layout(height=300)
            st.plotly_chart(fig_low_stock, use_container_width=True)
        
        with col3:
            fig_out_stock = go.Figure(go.Indicator(
                mode="gauge+number",
                value=inventory_status['Out of Stock'],
                title={'text': "Out of Stock %"},
                gauge={'axis': {'range': [None, 30]},
                       'bar': {'color': "red"},
                       'steps': [{'range': [0, 10], 'color': "lightgray"},
                                {'range': [10, 20], 'color': "yellow"}],
                       'threshold': {'line': {'color': "red", 'width': 4},
                                   'thickness': 0.75, 'value': 25}}
            ))
            fig_out_stock.update_layout(height=300)
            st.plotly_chart(fig_out_stock, use_container_width=True)

    # ===================
    # Product-Lead Correlation (Simulated)
    # ===================
    st.subheader("🎯 Product-Lead Correlation Analysis")
    
    if not lead_funnel.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            # Products with highest closing rate
            top_converting = lead_funnel.nlargest(10, 'closing_rate')[['category', 'closing_rate', 'leads_closed']]
            
            fig_top_convert = px.bar(
                top_converting,
                x='closing_rate',
                y='category',
                orientation='h',
                title='Top 10 Categories by Closing Rate',
                labels={'closing_rate': 'Closing Rate', 'category': 'Category'}
            )
            st.plotly_chart(fig_top_convert, use_container_width=True)
        
        with col2:
            # Lead volume vs conversion rate
            fig_volume_conversion = px.scatter(
                lead_funnel,
                x='leads_generated',
                y='closing_rate',
                size='total_revenue',
                color='qualification_rate',
                title='Lead Volume vs Conversion Rate',
                labels={'leads_generated': 'Leads Generated', 'closing_rate': 'Closing Rate'}
            )
            st.plotly_chart(fig_volume_conversion, use_container_width=True)

    # ===================
    # Performance Summary
    # ===================
    st.markdown("---")
    st.subheader("📊 Product & Lead Performance Summary")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if not category_perf.empty:
            top_category = category_perf.iloc[0]['category']
            top_revenue = category_perf.iloc[0]['total_revenue']
            total_categories = len(category_perf)
            
            st.info(f"""
            **Product Performance**
            - Top Category: {top_category}
            - Top Revenue: € {top_revenue:,.0f}
            - Total Categories: {total_categories}
            """)
        else:
            st.info("**Product data not available**")
    
    with col2:
        if not lead_funnel.empty:
            avg_conversion = lead_funnel['overall_conversion'].mean()
            avg_qualification = lead_funnel['qualification_rate'].mean()
            avg_closing = lead_funnel['closing_rate'].mean()
            
            st.success(f"""
            **Lead Performance**
            - Avg Conversion: {avg_conversion:.1%}
            - Avg Qualification: {avg_qualification:.1%}
            - Avg Closing: {avg_closing:.1%}
            """)
        else:
            st.success("**Lead data simulated**")
    
    with col3:
        st.warning(f"""
        **Inventory Status**
        - In Stock: {inventory_status['In Stock']}%
        - Low Stock: {inventory_status['Low Stock']}%
        - Out of Stock: {inventory_status['Out of Stock']}%
        """)

    # ===================
    # Recommendations
    # ===================
    st.markdown("---")
    st.subheader("💡 Recommendations")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Product Optimization:**")
        st.write("• Focus on top-performing categories")
        st.write("• Optimize product photos quantity")
        st.write("• Improve product descriptions")
        st.write("• Monitor inventory levels closely")
    
    with col2:
        st.write("**Lead Management:**")
        st.write("• Improve qualification process")
        st.write("• Focus on high-converting segments")
        st.write("• Optimize lead sources")
        st.write("• Enhance follow-up strategies")
# ================================
# 📌 HALAMAN: Operational Excellence
# ================================
elif page == "Operational Excellence":
    st.header("📌 Operational Excellence")
    st.markdown("**Meningkatkan efisiensi operasional dan customer satisfaction**")
    
    # Metrics Overview
    col1, col2, col3, col4 = st.columns(4)
    
    # Calculate key operational metrics using available data
    # Calculate delivery time for delivered orders
    delivered_orders = orders_filtered[
        (orders_filtered['order_status'] == 'delivered') & 
        (orders_filtered['order_delivered_customer_date'].notna()) &
        (orders_filtered['order_approved_at'].notna())
    ].copy()
    
    if not delivered_orders.empty:
        delivered_orders['order_approved_at'] = pd.to_datetime(delivered_orders['order_approved_at'])
        delivered_orders['order_delivered_customer_date'] = pd.to_datetime(delivered_orders['order_delivered_customer_date'])
        delivered_orders['delivery_time'] = (delivered_orders['order_delivered_customer_date'] - 
                                           delivered_orders['order_approved_at']).dt.days
        avg_delivery_time = delivered_orders['delivery_time'].mean()
    else:
        avg_delivery_time = 0
    
    # Use order_items from filtered data
    total_freight_cost = order_items['freight_value'].sum() if 'freight_value' in order_items.columns else 0
    avg_freight_per_order = order_items.groupby('order_id')['freight_value'].sum().mean() if 'freight_value' in order_items.columns else 0
    
    with col1:
        st.metric("📦 Avg Delivery Time", f"{avg_delivery_time:.1f} days")
    
    with col2:
        st.metric("💰 Total Freight Cost", f"€ {total_freight_cost:,.0f}")
    
    with col3:
        st.metric("📊 Avg Freight/Order", f"€ {avg_freight_per_order:.2f}")
    
    with col4:
        delivery_rate = (orders_filtered['order_status'] == 'delivered').mean() * 100
        st.metric("✅ Delivery Success Rate", f"{delivery_rate:.1f}%")
    
    # Row 1: Order Processing & Delivery Performance
    col1, col2 = st.columns(2)
        
    with col1:
        st.subheader("⏱️ Order Processing Time Distribution")
        
        if not delivered_orders.empty:
            # Filter outliers (delivery time > 100 days)
            delivered_clean = delivered_orders[delivered_orders['delivery_time'] <= 100]
            
            if not delivered_clean.empty:
                fig_processing = px.histogram(
                    delivered_clean, 
                    x='delivery_time',
                    nbins=30,
                    title="Distribution of Order Processing Time (Days)",
                    labels={'delivery_time': 'Days to Deliver', 'count': 'Number of Orders'},
                    color_discrete_sequence=['#1f77b4']
                )
                
                # Add average line
                avg_proc_time = delivered_clean['delivery_time'].mean()
                fig_processing.add_vline(x=avg_proc_time, line_dash="dash", line_color="red", 
                                    annotation_text=f"Avg: {avg_proc_time:.1f} days")
                
                st.plotly_chart(fig_processing, use_container_width=True)
            else:
                st.info("No delivery data available for processing time analysis")
        else:
            st.info("No delivered orders found in the selected date range")

    with col2:
        st.subheader("🚚 Freight Cost Analysis")
        
        if 'freight_value' in order_items.columns:
            freight_data = order_items[order_items['freight_value'] > 0].copy()
            
            if not freight_data.empty:
                q95 = freight_data['freight_value'].quantile(0.95)
                freight_clean = freight_data[freight_data['freight_value'] <= q95]
                
                fig_freight = px.histogram(
                    freight_clean,
                    x='freight_value',
                    nbins=30,
                    title="Freight Cost Distribution",
                    labels={
                        'freight_value': 'Freight Cost (€)',
                        'count': 'Number of Items'
                    },
                    color_discrete_sequence=['#2ca02c']
                )
                
                median_freight = freight_clean['freight_value'].median()
                fig_freight.add_vline(
                    x=median_freight, 
                    line_dash="dash", 
                    line_color="red",
                    annotation_text=f"Median: € {median_freight:.2f}"
                )
                
                st.plotly_chart(fig_freight, use_container_width=True)
            else:
                st.info("No freight cost data available")
        else:
            st.info("Freight cost data not available in dataset")

    # Row 2: Seller Performance (sendiri, bawah)
    st.subheader("🏆 Seller Performance Analysis")

    # Check if we have seller data and delivery times
    if not delivered_orders.empty and 'seller_id' in order_items.columns:
        # Merge delivery data with seller info
        seller_delivery = delivered_orders.merge(
            order_items[['order_id', 'seller_id']], on='order_id', how='inner'
        )
        
        if not seller_delivery.empty:
            # Calculate seller performance metrics
            seller_performance = seller_delivery.groupby('seller_id').agg({
                'delivery_time': 'mean',
                'order_id': 'nunique'
            }).reset_index()
            
            seller_performance.columns = ['seller_id', 'avg_delivery_time', 'order_volume']
            
            # Filter sellers with at least 5 orders
            seller_performance = seller_performance[seller_performance['order_volume'] >= 5]
            
            if not seller_performance.empty:
                fig_seller = px.scatter(
                    seller_performance.head(50),  # Top 50 sellers
                    x='order_volume',
                    y='avg_delivery_time',
                    size='order_volume',
                    title="Seller Performance: Volume vs Delivery Time",
                    labels={
                        'order_volume': 'Number of Orders',
                        'avg_delivery_time': 'Average Delivery Time (Days)'
                    },
                    color_discrete_sequence=['#ff7f0e']
                )
                
                st.plotly_chart(fig_seller, use_container_width=True)
            else:
                st.info("Insufficient seller data for performance analysis")
        else:
            st.info("Unable to link delivery data with seller information")
    else:
        st.info("Seller performance data not available")
    
    # Row 3: Operational Insights & Recommendations
    st.subheader("🎯 Key Operational Insights")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if not delivered_orders.empty:
            q25 = delivered_orders['delivery_time'].quantile(0.25)
            q75 = delivered_orders['delivery_time'].quantile(0.75)
            
            st.markdown("""
            **⚡ Processing Efficiency**
            - Average delivery time: {:.1f} days
            - 25% of orders delivered in <{:.1f} days
            - 75% of orders delivered in <{:.1f} days
            """.format(avg_delivery_time, q25, q75))
        else:
            st.markdown("""
            **⚡ Processing Efficiency**
            - Delivery data not available
            - Unable to calculate processing times
            """)
    
    with col2:
        if not payments.empty:
            top_payment = payments['payment_type'].value_counts().index[0]
            payment_pct = (payments['payment_type'].value_counts().iloc[0] / 
                          len(payments) * 100)
            avg_payment_value = payments['payment_value'].mean()
            avg_installments = payments['payment_installments'].mean()
            
            st.markdown("""
            **💰 Payment Insights**
            - Dominant payment: {} ({:.1f}%)
            - Average payment value: € {:.2f}
            - Payment installments avg: {:.1f}
            """.format(
                top_payment,
                payment_pct,
                avg_payment_value,
                avg_installments
            ))
        else:
            st.markdown("""
            **💰 Payment Insights**
            - Payment data not available
            """)
    
    with col3:
        if 'freight_value' in order_items.columns:
            freight_stats = order_items['freight_value'].describe()
            median_freight = freight_stats['50%']
            
            st.markdown("""
            **🚛 Logistics Optimization**
            - Median freight cost: € {:.2f}
            - High freight variance detected
            - Cost optimization opportunity
            """.format(median_freight))
        else:
            st.markdown("""
            **🚛 Logistics Optimization**
            - Freight data not available
            """)
    
    # Action Items
    st.subheader("📋 Recommended Actions")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        **🎯 Immediate Actions (1-3 months)**
        - ⚡ Focus on sellers with >30 day avg delivery
        - 📊 Implement delivery time SLAs
        - 💳 Promote faster payment methods
        - 🚚 Review freight pricing model
        """)
    
    with col2:
        st.markdown("""
        **🚀 Strategic Initiatives (3-12 months)**
        - 🤖 Automated seller performance monitoring
        - 📍 Regional fulfillment optimization
        - 💰 Dynamic freight pricing based on distance
        - 📈 Predictive delivery time estimates
        """)
    
    # Performance Summary Table
    st.subheader("📊 Order Status Summary")
    
    # Order status distribution
    if not orders_filtered.empty:
        status_summary = orders_filtered['order_status'].value_counts().reset_index()
        status_summary.columns = ['Order Status', 'Count']
        status_summary['Percentage'] = (status_summary['Count'] / status_summary['Count'].sum() * 100).round(1)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.dataframe(
                status_summary,
                column_config={
                    'Order Status': 'Order Status',
                    'Count': st.column_config.NumberColumn('Count', format="%d"),
                    'Percentage': st.column_config.NumberColumn('Percentage', format="%.1f%%")
                },
                use_container_width=True
            )
        
        with col2:
            # Create pie chart for order status
            fig_status = px.pie(
                status_summary, 
                values='Count', 
                names='Order Status',
                title='Order Status Distribution'
            )
            st.plotly_chart(fig_status, use_container_width=True)
    else:
        st.info("No order data available for the selected period")
    
    # Additional seller performance table if available
    if 'seller_performance' in locals() and not seller_performance.empty:
        st.subheader("📊 Seller Performance Summary")
        
        # Top and bottom performers
        top_performers = seller_performance.nsmallest(10, 'avg_delivery_time')
        bottom_performers = seller_performance.nlargest(10, 'avg_delivery_time')
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**🏆 Top Performers (Fastest Delivery)**")
            if not top_performers.empty:
                st.dataframe(
                    top_performers[['seller_id', 'avg_delivery_time', 'order_volume']].round(1),
                    column_config={
                        'seller_id': 'Seller ID',
                        'avg_delivery_time': st.column_config.NumberColumn(
                            'Avg Delivery (Days)',
                            format="%.1f"
                        ),
                        'order_volume': 'Total Orders'
                    },
                    use_container_width=True
                )
            else:
                st.info("No top performer data available")
        
        with col2:
            st.markdown("**⚠️ Needs Improvement (Slowest Delivery)**")
            if not bottom_performers.empty:
                st.dataframe(
                    bottom_performers[['seller_id', 'avg_delivery_time', 'order_volume']].round(1),
                    column_config={
                        'seller_id': 'Seller ID',
                        'avg_delivery_time': st.column_config.NumberColumn(
                            'Avg Delivery (Days)',
                            format="%.1f"
                        ),
                        'order_volume': 'Total Orders'
                    },
                    use_container_width=True
                )
            else:
                st.info("No underperformer data available")

# ================================
# 📌 Customer Preference Analysis
# ================================
elif page == "Customer Preference Analysis":
    st.header("📌 Customer Preference Analysis")
    st.markdown("*Analisis ulasan pelanggan untuk memahami preferensi & pengalaman customer*")

    # Merge review dengan products
    reviews_products = order_reviews.merge(order_items, on='order_id', how='left') \
                                    .merge(products, on='product_id', how='left') \
                                    .merge(product_category_name_translation, on='product_category_name', how='left')

    # Filter Section - Rapi dalam container
    with st.container():
        st.markdown("### 🔍 Filter Analisis")
        
        # Buat dua kolom untuk filter
        col_filter1, col_filter2 = st.columns([2, 1])
        
        with col_filter1:
            # Dropdown untuk pilih produk
            product_options = reviews_products['product_category_name_english'].dropna().unique().tolist()
            product_options.sort()
            selected_product = st.selectbox("📦 Pilih Kategori Produk:", product_options)
        
        with col_filter2:
            # Filter berdasarkan rating
            rating_filter = st.multiselect(
                "⭐ Filter Rating:",
                options=[1, 2, 3, 4, 5],
                default=[1, 2, 3, 4, 5]
            )
        
        # Tambahkan divider untuk pemisah visual
        st.markdown("---")

    # Filter data sesuai kriteria yang dipilih
    filtered_reviews = reviews_products[
        (reviews_products['product_category_name_english'] == selected_product) &
        (reviews_products['review_score'].isin(rating_filter))
    ]

    # Header dengan metrics utama
    st.markdown(f"### 📊 Overview: {selected_product}")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        avg_rating = filtered_reviews['review_score'].mean()
        st.metric("⭐ Rata-rata Rating", f"{avg_rating:.2f}" if not np.isnan(avg_rating) else "N/A")
    
    with col2:
        total_reviews = filtered_reviews['review_id'].nunique()
        st.metric("💬 Total Ulasan", f"{total_reviews:,}")
    
    with col3:
        # Persentase ulasan positif (rating 4-5)
        positive_reviews = filtered_reviews[filtered_reviews['review_score'] >= 4].shape[0]
        positive_pct = (positive_reviews / total_reviews * 100) if total_reviews > 0 else 0
        st.metric("👍 Ulasan Positif", f"{positive_pct:.1f}%")
    
    with col4:
        # Rata-rata harga produk dalam kategori ini
        avg_price = filtered_reviews['price'].mean()
        st.metric("💰 Rata-rata Harga", f"€ {avg_price:.2f}" if not np.isnan(avg_price) else "N/A")

    # Visualisasi utama
    col1, col2 = st.columns([2, 1])

    with col1:
        if not filtered_reviews.empty:
            # Distribusi rating dengan styling yang lebih menarik
            rating_counts = filtered_reviews['review_score'].value_counts().sort_index()
            fig_rating = px.bar(
                x=rating_counts.index,
                y=rating_counts.values,
                labels={'x': 'Review Score', 'y': 'Jumlah Ulasan'},
                title='Distribusi Rating Produk',
                color=rating_counts.index,
                color_continuous_scale='RdYlGn'
            )
            fig_rating.update_layout(
                xaxis_title="Rating",
                yaxis_title="Jumlah Ulasan",
                showlegend=False
            )
            st.plotly_chart(fig_rating, use_container_width=True)
        else:
            st.info("Tidak ada review untuk produk ini dengan filter yang dipilih.")

    with col2:
        # Pie chart untuk proporsi rating
        if not filtered_reviews.empty:
            good_reviews = filtered_reviews[filtered_reviews['review_score'] >= 4].shape[0]
            bad_reviews = filtered_reviews[filtered_reviews['review_score'] <= 2].shape[0]
            neutral_reviews = filtered_reviews[(filtered_reviews['review_score'] == 3)].shape[0]

            fig_pie = px.pie(
                names=['Positif (4-5)', 'Netral (3)', 'Negatif (1-2)'],
                values=[good_reviews, neutral_reviews, bad_reviews],
                title='Proporsi Sentiment Ulasan',
                color_discrete_map={
                    'Positif (4-5)': '#2E8B57',
                    'Netral (3)': '#FFD700', 
                    'Negatif (1-2)': '#DC143C'
                }
            )
            st.plotly_chart(fig_pie, use_container_width=True)

    # Analisis lanjutan
    st.markdown("### 📈 Analisis Mendalam")

    # Tren waktu dan heatmap
    col1, col2 = st.columns(2)
    
    with col1:
        # Tren review dari waktu ke waktu
        if not filtered_reviews.empty:
            # Konversi tanggal
            filtered_reviews['review_creation_date'] = pd.to_datetime(filtered_reviews['review_creation_date'], errors='coerce')
            trend_reviews = filtered_reviews.copy()
            trend_reviews['year_month'] = trend_reviews['review_creation_date'].dt.to_period('M')
            reviews_over_time = trend_reviews.groupby('year_month').agg({
                'review_id': 'count',
                'review_score': 'mean'
            }).reset_index()
            reviews_over_time['year_month'] = reviews_over_time['year_month'].astype(str)
            
            # Dual axis chart
            fig_trend = px.line(
                reviews_over_time,
                x='year_month',
                y='review_id',
                title='Tren Jumlah Review & Rating dari Waktu ke Waktu',
                markers=True,
                labels={'review_id': 'Jumlah Review', 'year_month': 'Bulan'}
            )
            
            # Tambahkan line kedua untuk average rating
            fig_trend.add_scatter(
                x=reviews_over_time['year_month'],
                y=reviews_over_time['review_score'] * 10,  # Scale untuk visibility
                mode='lines+markers',
                name='Avg Rating (x10)',
                yaxis='y2',
                line=dict(color='red', dash='dash')
            )
            
            fig_trend.update_layout(
                yaxis2=dict(
                    title='Average Rating (Scaled)',
                    overlaying='y',
                    side='right'
                )
            )
            st.plotly_chart(fig_trend, use_container_width=True)
    
    with col2:
        # Analisis rating berdasarkan bulan
        if not filtered_reviews.empty:
            # Pastikan tanggal sudah terkonversi
            if 'review_creation_date' not in filtered_reviews.columns or filtered_reviews['review_creation_date'].dtype == 'object':
                filtered_reviews['review_creation_date'] = pd.to_datetime(filtered_reviews['review_creation_date'], errors='coerce')
            
            filtered_reviews['month'] = filtered_reviews['review_creation_date'].dt.month
            filtered_reviews['weekday'] = filtered_reviews['review_creation_date'].dt.day_name()
            
            monthly_ratings = filtered_reviews.groupby('month')['review_score'].mean().reset_index()
            monthly_ratings['month_name'] = monthly_ratings['month'].map({
                1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
                7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'
            })
            
            fig_monthly = px.bar(
                monthly_ratings,
                x='month_name',
                y='review_score',
                title='Rata-rata Rating per Bulan',
                color='review_score',
                color_continuous_scale='RdYlGn'
            )
            fig_monthly.update_layout(showlegend=False)
            st.plotly_chart(fig_monthly, use_container_width=True)

    # Analisis kata kunci dalam ulasan
    st.markdown("### 🔍 Analisis Kata Kunci Ulasan")

    # Opsi terjemahan
    translate_option = st.checkbox("🌐 Tampilkan terjemahan ke Bahasa Indonesia")

    if not filtered_reviews.empty:
        # Ambil hanya ulasan yang memiliki komentar
        sample_reviews = filtered_reviews[filtered_reviews['review_comment_message'].notna()]
        
        if not sample_reviews.empty:
            # Tab untuk memisahkan ulasan positif dan negatif
            tab_positive, tab_negative = st.tabs(["👍 Ulasan Positif (Rating 4-5)", "👎 Ulasan Negatif (Rating 1-2)"])
            
            with tab_positive:
                positive_reviews = sample_reviews[sample_reviews['review_score'] >= 4]
                
                if not positive_reviews.empty:
                    # Siapkan data untuk tabel
                    positive_data = []
                    for _, review in positive_reviews.head(5).iterrows():
                        title = review['review_comment_title'] or "-"
                        message = review['review_comment_message']
                        
                        if translate_option:
                            title = translate_text(title, target_lang='id')
                            message = translate_text(message, target_lang='id')
                        
                        # Potong pesan jika terlalu panjang
                        message_short = message[:200] + "..." if len(message) > 200 else message
                        
                        positive_data.append({
                            "Rating": f"{review['review_score']}/5",
                            "Judul": title,
                            "Komentar": message_short,
                            "Tanggal": review.get('review_creation_time', '-')
                        })
                    
                    # Tampilkan sebagai tabel
                    positive_df = pd.DataFrame(positive_data)
                    st.dataframe(
                        positive_df,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Rating": st.column_config.TextColumn("Rating", width="small"),
                            "Judul": st.column_config.TextColumn("Judul", width="medium"),
                            "Komentar": st.column_config.TextColumn("Komentar", width="large"),
                            "Tanggal": st.column_config.TextColumn("Tanggal", width="medium")
                        }
                    )
                else:
                    st.info("Tidak ada ulasan positif dengan komentar.")
            
            with tab_negative:
                negative_reviews = sample_reviews[sample_reviews['review_score'] <= 2]
                
                if not negative_reviews.empty:
                    # Siapkan data untuk tabel
                    negative_data = []
                    for _, review in negative_reviews.head(5).iterrows():
                        title = review['review_comment_title'] or "-"
                        message = review['review_comment_message']
                        
                        if translate_option:
                            title = translate_text(title, target_lang='id')
                            message = translate_text(message, target_lang='id')
                        
                        # Potong pesan jika terlalu panjang
                        message_short = message[:200] + "..." if len(message) > 200 else message
                        
                        negative_data.append({
                            "Rating": f"{review['review_score']}/5",
                            "Judul": title,
                            "Komentar": message_short,
                            "Tanggal": review.get('review_creation_time', '-')
                        })
                    
                    # Tampilkan sebagai tabel
                    negative_df = pd.DataFrame(negative_data)
                    st.dataframe(
                        negative_df,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Rating": st.column_config.TextColumn("Rating", width="small"),
                            "Judul": st.column_config.TextColumn("Judul", width="medium"),
                            "Komentar": st.column_config.TextColumn("Komentar", width="large"),
                            "Tanggal": st.column_config.TextColumn("Tanggal", width="medium")
                        }
                    )
                else:
                    st.info("Tidak ada ulasan negatif dengan komentar.")                
        else:
            st.info("Tidak ada ulasan yang memiliki komentar.")
    else:
        st.info("Tidak ada ulasan untuk produk ini berdasarkan filter.")
    # ===============================
    # 📋 TABEL DETAIL ULASAN PELANGGAN
    # ===============================
    st.markdown("### 📋 Detail Ulasan Pelanggan")

    if not filtered_reviews.empty:
        
        # 🎛️ Panel Kontrol        
        # Container untuk kontrol dengan styling yang rapi
        with st.container():
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                # 🔍 Fitur pencarian dengan styling yang lebih baik
                search_term = st.text_input(
                    "🔍 Pencarian Cerdas", 
                    placeholder="Cari kata kunci dalam judul atau isi ulasan...",
                    help="Pencarian akan mencari di judul dan isi ulasan"
                )
            
            with col2:
                # 🧾 Sorting dengan opsi yang lebih lengkap
                sort_options = {
                    'Tanggal Ulasan': 'review_creation_date',
                    'Rating (Tinggi → Rendah)': 'review_score_desc',
                    'Rating (Rendah → Tinggi)': 'review_score_asc',
                    'Harga (Tinggi → Rendah)': 'price_desc',
                    'Harga (Rendah → Tinggi)': 'price_asc'
                }
                sort_by = st.selectbox(
                    "🧾 Urutkan berdasarkan:", 
                    options=list(sort_options.keys()),
                    index=0,
                    help="Pilih cara pengurutan data"
                )
            
            with col3:
                # 🌐 Checkbox translate dengan styling
                translate_option = st.checkbox(
                    "🌐 Terjemahkan", 
                    help="Terjemahkan judul dan isi ulasan ke Bahasa Indonesia"
                )
        
        st.markdown("---")
        
        # Siapkan data tabel
        review_table = filtered_reviews[['review_score', 'review_comment_title', 
                                    'review_comment_message', 'review_creation_date', 'price']].copy()

        # Filter berdasarkan kata kunci pencarian
        if search_term:
            mask = (
                review_table['review_comment_title'].str.contains(search_term, case=False, na=False) |
                review_table['review_comment_message'].str.contains(search_term, case=False, na=False)
            )
            review_table = review_table[mask]
            
            if review_table.empty:
                st.warning(f"🔍 Tidak ditemukan ulasan yang mengandung kata '{search_term}'")
                st.stop()

        # Terjemahan jika diperlukan
        if translate_option:
            with st.spinner("🌐 Menerjemahkan ulasan..."):
                review_table['review_comment_title'] = review_table['review_comment_title'].apply(
                    lambda x: translate_text(x, 'id') if pd.notnull(x) and str(x).strip() != '' else x
                )
                review_table['review_comment_message'] = review_table['review_comment_message'].apply(
                    lambda x: translate_text(x, 'id') if pd.notnull(x) and str(x).strip() != '' else x
                )

        # Aplikasikan pengurutan
        sort_column = sort_options[sort_by]
        if sort_column == 'review_score_desc':
            review_table_sorted = review_table.sort_values(by='review_score', ascending=False)
        elif sort_column == 'review_score_asc':
            review_table_sorted = review_table.sort_values(by='review_score', ascending=True)
        elif sort_column == 'price_desc':
            review_table_sorted = review_table.sort_values(by='price', ascending=False)
        elif sort_column == 'price_asc':
            review_table_sorted = review_table.sort_values(by='price', ascending=True)
        else:
            review_table_sorted = review_table.sort_values(by='review_creation_date', ascending=False)

        # Ganti nama kolom untuk tampilan
        display_table = review_table_sorted.rename(columns={
            'review_score': 'Rating',
            'review_comment_title': 'Judul Ulasan',
            'review_comment_message': 'Isi Ulasan',
            'review_creation_date': 'Tanggal',
            'price': 'Harga (€)'
        })

        # Format data untuk tampilan yang lebih baik
        display_table['Rating'] = display_table['Rating'].apply(lambda x: f"⭐ {x}/5" if pd.notnull(x) else "-")
        display_table['Harga (€)'] = display_table['Harga (€)'].apply(lambda x: f"€ {x:,.2f}" if pd.notnull(x) else "-")
        display_table['Judul Ulasan'] = display_table['Judul Ulasan'].fillna("(Tanpa Judul)")
        display_table['Isi Ulasan'] = display_table['Isi Ulasan'].apply(
            lambda x: x[:150] + "..." if pd.notnull(x) and len(str(x)) > 150 else (x if pd.notnull(x) else "(Tidak ada komentar)")
        )

        # 🖼️ Tampilkan tabel dengan konfigurasi yang cantik
        st.markdown("#### 📋 Data Ulasan")
        
        st.dataframe(
            display_table, 
            use_container_width=True, 
            height=500,
            column_config={
                "Rating": st.column_config.TextColumn(
                    "Rating",
                    width="small",
                    help="Rating yang diberikan pelanggan"
                ),
                "Judul Ulasan": st.column_config.TextColumn(
                    "Judul Ulasan",
                    width="medium",
                    help="Judul atau ringkasan ulasan"
                ),
                "Isi Ulasan": st.column_config.TextColumn(
                    "Isi Ulasan",
                    width="large",
                    help="Komentar detail dari pelanggan"
                ),
                "Tanggal": st.column_config.DatetimeColumn(
                    "Tanggal",
                    width="small",
                    format="DD/MM/YYYY",
                    help="Tanggal ulasan dibuat"
                ),
                "Harga (€)": st.column_config.TextColumn(
                    "Harga",
                    width="small",
                    help="Harga produk saat ulasan dibuat"
                )
            },
            hide_index=True
        )

        # 💾 Panel Download dengan opsi yang lebih lengkap
        st.markdown("---")
        st.markdown("#### 💾 Ekspor Data")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Download CSV
            csv_data = review_table_sorted.to_csv(index=False)
            st.download_button(
                label="📥 Download CSV",
                data=csv_data,
                file_name=f"ulasan_{selected_product.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                help="Download data dalam format CSV untuk Excel"
            )
        
        with col2:
            # Download JSON
            json_data = review_table_sorted.to_json(orient='records', indent=2)
            st.download_button(
                label="📥 Download JSON",
                data=json_data,
                file_name=f"ulasan_{selected_product.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json",
                help="Download data dalam format JSON"
            )

        # 📈 Insight singkat
        if total_reviews > 0:
            st.markdown("---")
            st.markdown("#### 💡 Insight Cepat")
            
            # Analisis sentimen sederhana
            excellent_reviews = len(review_table_sorted[review_table_sorted['review_score'] == 5])
            poor_reviews = len(review_table_sorted[review_table_sorted['review_score'] <= 2])
            
            insight_col1, insight_col2 = st.columns(2)
            
            with insight_col1:
                if excellent_reviews > 0:
                    st.success(f"🌟 {excellent_reviews} ulasan memberikan rating sempurna (5/5)")
                
            with insight_col2:
                if poor_reviews > 0:
                    st.error(f"⚠️ {poor_reviews} ulasan memberikan rating rendah (≤2/5)")

    else:
        st.info("📭 Tidak ada ulasan untuk produk ini dengan filter yang dipilih.")
        st.markdown("💡 **Saran:** Coba ubah filter atau pilih produk lain.")


# ================================
# 📌 PLACEHOLDER UNTUK HALAMAN LAIN
# ================================
# elif page == "Operational Excellence":
#     st.header("📌 Operational Excellence")
#     st.info("🚧 Halaman ini sedang dalam pengembangan")

elif page == "Strategic Recommendations":
    st.header("📌 Strategic Recommendations")
    st.markdown("*Actionable insights untuk growth strategy dan business optimization*")

    # ===================
    # Business Intelligence Summary
    # ===================
    st.subheader("🧠 Business Intelligence Summary")
    
    # Calculate key business metrics
    total_revenue = orders_payments_filtered['payment_value'].sum()
    total_orders = orders_filtered['order_id'].nunique()
    total_customers = orders_filtered['customer_id'].nunique()
    avg_order_value = orders_payments_filtered['payment_value'].mean()
    
    # Customer metrics
    customer_orders = orders_filtered.merge(customers, on='customer_id', how='left')
    orders_per_customer = customer_orders.groupby('customer_id').size().mean()
    
    # Product performance
    if not products.empty and not order_items.empty:
        product_sales = orders_items_filtered.merge(products, on='product_id', how='left')
        top_category = product_sales.groupby('product_category_name')['order_item_id'].count().idxmax()
        category_revenue = product_sales.groupby('product_category_name')['price'].sum().max()
    else:
        top_category = "N/A"
        category_revenue = 0

    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        **🎯 Current Performance:**
        - Revenue: € {:,.0f}
        - Total Orders: {:,}
        - Average Order Value: € {:,.0f}
        - Orders per Customer: {:.1f}
        """.format(total_revenue, total_orders, avg_order_value, orders_per_customer))
    
    with col2:
        st.markdown("""
        **🏆 Key Strengths:**
        - Top Category: {}
        - Customer Base: {:,} unique customers
        - Market Presence: Active across multiple states
        - Payment Flexibility: Multiple payment methods
        """.format(top_category, total_customers))

    # ===================
    # Priority Matrix - Impact vs Effort
    # ===================
    st.markdown("---")
    st.subheader("🎯 Strategic Priority Matrix")
    st.markdown("*Rekomendasi berdasarkan Impact vs Implementation Effort*")

    # Create priority matrix data
    recommendations_data = {
        'Initiative': [
            'Customer Retention Program',
            'Cross-selling Strategy', 
            'Geographic Expansion',
            'Payment Method Optimization',
            'Product Category Expansion',
            'Delivery Speed Improvement',
            'Mobile App Development',
            'AI Recommendation Engine',
            'Loyalty Program Launch',
            'Inventory Optimization'
        ],
        'Impact': [9, 8, 7, 6, 8, 7, 9, 8, 7, 6],
        'Effort': [4, 3, 8, 2, 7, 6, 9, 8, 5, 4],
        'Revenue_Potential': [50, 30, 100, 15, 60, 25, 80, 45, 35, 20],
        'Timeline': ['3-6 months', '1-3 months', '6-12 months', '1-2 months', 
                   '6-9 months', '3-6 months', '9-12 months', '6-9 months',
                   '3-6 months', '2-4 months']
    }
    
    recommendations_df = pd.DataFrame(recommendations_data)
    
    # Create bubble chart
    fig_matrix = px.scatter(
        recommendations_df,
        x='Effort',
        y='Impact', 
        size='Revenue_Potential',
        hover_name='Initiative',
        hover_data={'Timeline': True, 'Revenue_Potential': ':,.0f'},
        title='Strategic Priority Matrix (Impact vs Effort)',
        labels={
            'Effort': 'Implementation Effort (1-10)',
            'Impact': 'Business Impact (1-10)',
            'Revenue_Potential': 'Revenue Potential (Million €)'
        },
        size_max=30
    )
    
    # Add quadrant lines
    fig_matrix.add_hline(y=5.5, line_dash="dash", line_color="gray", opacity=0.5)
    fig_matrix.add_vline(x=5.5, line_dash="dash", line_color="gray", opacity=0.5)
    
    # Add quadrant labels
    fig_matrix.add_annotation(x=2, y=9, text="Quick Wins", showarrow=False, 
                            font=dict(size=14, color="green"))
    fig_matrix.add_annotation(x=8, y=9, text="Strategic Projects", showarrow=False,
                            font=dict(size=14, color="blue"))
    fig_matrix.add_annotation(x=2, y=2, text="Fill-ins", showarrow=False,
                            font=dict(size=14, color="orange"))
    fig_matrix.add_annotation(x=8, y=2, text="Avoid", showarrow=False,
                            font=dict(size=14, color="red"))
    
    fig_matrix.update_layout(height=500, showlegend=False)
    st.plotly_chart(fig_matrix, use_container_width=True)

    # ===================
    # Top 5 Recommendations
    # ===================
    st.markdown("---")
    st.subheader("🚀 Top 5 Strategic Recommendations")

    # Priority recommendations based on matrix
    quick_wins = recommendations_df[(recommendations_df['Impact'] > 5.5) & (recommendations_df['Effort'] <= 5.5)]
    strategic = recommendations_df[(recommendations_df['Impact'] > 5.5) & (recommendations_df['Effort'] > 5.5)]
    
    top_recommendations = pd.concat([
        quick_wins.sort_values('Impact', ascending=False).head(3),
        strategic.sort_values('Revenue_Potential', ascending=False).head(2)
    ])

    for idx, row in top_recommendations.iterrows():
        priority = "🟢 Quick Win" if row['Effort'] <= 5.5 else "🔵 Strategic"
        
        with st.expander(f"{priority}: {row['Initiative']}", expanded=True):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Impact Score", f"{row['Impact']}/10")
            with col2:
                st.metric("Effort Level", f"{row['Effort']}/10")
            with col3:
                st.metric("Revenue Potential", f"€ {row['Revenue_Potential']}M")
            
            # Add specific recommendations based on initiative
            if row['Initiative'] == 'Customer Retention Program':
                st.markdown("""
                **📋 Action Plan:**
                - Implement email marketing untuk repeat customers
                - Create customer loyalty tiers berdasarkan purchase history
                - Develop personalized offers untuk high-value customers
                - Set up automated follow-up campaigns
                
                **📈 Expected Outcome:**
                - 15-25% increase dalam customer lifetime value
                - 30% improvement dalam repeat purchase rate
                """)
            
            elif row['Initiative'] == 'Cross-selling Strategy':
                st.markdown("""
                **📋 Action Plan:**
                - Analyze product affinity dan buying patterns
                - Implement "frequently bought together" recommendations
                - Create product bundles untuk popular combinations
                - Train customer service untuk cross-selling
                
                **📈 Expected Outcome:**
                - 20-35% increase dalam average order value
                - 10-15% boost dalam overall revenue
                """)
            
            elif row['Initiative'] == 'Mobile App Development':
                st.markdown("""
                **📋 Action Plan:**
                - Develop native mobile app dengan core features
                - Implement push notifications untuk promotions
                - Add mobile-specific features (camera search, location-based offers)
                - Optimize checkout process untuk mobile users
                
                **📈 Expected Outcome:**
                - 40-60% increase dalam mobile conversion rate
                - 25% growth dalam overall customer acquisition
                """)
            
            elif row['Initiative'] == 'AI Recommendation Engine':
                st.markdown("""
                **📋 Action Plan:**
                - Implement collaborative filtering algorithm
                - Develop personalized product recommendations
                - A/B test recommendation placements
                - Monitor dan optimize recommendation accuracy
                
                **📈 Expected Outcome:**
                - 25-40% increase dalam click-through rate
                - 15-20% improvement dalam conversion rate
                """)
            
            elif row['Initiative'] == 'Product Category Expansion':
                st.markdown("""
                **📋 Action Plan:**
                - Analyze market demand untuk new categories
                - Identify reliable suppliers dan partners
                - Test market response dengan limited product launch
                - Scale successful categories gradually
                
                **📈 Expected Outcome:**
                - 30-50% expansion dalam total addressable market
                - 20-25% increase dalam customer acquisition
                """)

    # ===================
    # ROI Calculator
    # ===================
    st.markdown("---")
    st.subheader("💰 ROI Calculator")
    st.markdown("*Interactive calculator untuk estimate return on investment*")

    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.markdown("**Investment Parameters:**")
        
        investment_amount = st.slider(
            "Investment Amount (Million €)", 
            min_value=10, max_value=500, value=100, step=10
        )
        
        implementation_months = st.slider(
            "Implementation Timeline (Months)", 
            min_value=1, max_value=24, value=6
        )
        
        expected_revenue_increase = st.slider(
            "Expected Revenue Increase (%)", 
            min_value=5, max_value=100, value=25
        )
        
        selected_initiative = st.selectbox(
            "Select Initiative", 
            recommendations_df['Initiative'].tolist()
        )
    
    with col2:
        # Calculate ROI
        current_monthly_revenue = total_revenue / 12 if total_revenue > 0 else 1000000  # Assume monthly average
        projected_monthly_increase = current_monthly_revenue * (expected_revenue_increase / 100)
        annual_revenue_increase = projected_monthly_increase * 12
        roi_percentage = ((annual_revenue_increase - investment_amount) / investment_amount) * 100
        payback_months = investment_amount / projected_monthly_increase if projected_monthly_increase > 0 else float('inf')
        
        st.markdown("**📊 ROI Analysis:**")
        
        col2_1, col2_2 = st.columns(2)
        with col2_1:
            st.metric("ROI Percentage", f"{roi_percentage:.1f}%")
            st.metric("Payback Period", f"{payback_months:.1f} months")
        
        with col2_2:
            st.metric("Annual Revenue Increase", f"€ {annual_revenue_increase:,.0f}")
            st.metric("Monthly Revenue Boost", f"€ {projected_monthly_increase:,.0f}")
        
        # ROI visualization
        roi_data = pd.DataFrame({
            'Month': list(range(1, 13)),
            'Cumulative_Revenue': [projected_monthly_increase * i for i in range(1, 13)],
            'Investment': [investment_amount] * 12,
            'Net_Benefit': [projected_monthly_increase * i - investment_amount for i in range(1, 13)]
        })
        
        fig_roi = go.Figure()
        
        fig_roi.add_trace(go.Scatter(
            x=roi_data['Month'],
            y=roi_data['Cumulative_Revenue'],
            mode='lines+markers',
            name='Cumulative Revenue',
            line=dict(color='green')
        ))
        
        fig_roi.add_trace(go.Scatter(
            x=roi_data['Month'],
            y=roi_data['Investment'],
            mode='lines',
            name='Investment',
            line=dict(color='red', dash='dash')
        ))
        
        fig_roi.add_trace(go.Scatter(
            x=roi_data['Month'],
            y=roi_data['Net_Benefit'],
            mode='lines+markers',
            name='Net Benefit',
            line=dict(color='blue')
        ))
        
        fig_roi.update_layout(
            title='12-Month ROI Projection',
            xaxis_title='Month',
            yaxis_title='Amount (Million €)',
            height=350
        )
        
        st.plotly_chart(fig_roi, use_container_width=True)

    # ===================
    # Implementation Timeline
    # ===================
    st.markdown("---")
    st.subheader("📅 Implementation Timeline")
    st.markdown("*Recommended implementation schedule untuk top initiatives*")

    # Create Gantt chart data
    gantt_data = []
    start_date = datetime.now()
    
    timeline_initiatives = [
        {'name': 'Payment Method Optimization', 'duration': 2, 'priority': 'High'},
        {'name': 'Cross-selling Strategy', 'duration': 3, 'priority': 'High'}, 
        {'name': 'Customer Retention Program', 'duration': 6, 'priority': 'High'},
        {'name': 'Product Category Expansion', 'duration': 9, 'priority': 'Medium'},
        {'name': 'Mobile App Development', 'duration': 12, 'priority': 'Medium'},
        {'name': 'AI Recommendation Engine', 'duration': 9, 'priority': 'Medium'}
    ]
    
    for i, initiative in enumerate(timeline_initiatives):
        start = start_date + timedelta(days=i*30)  # Stagger starts
        end = start + timedelta(days=initiative['duration']*30)
        
        gantt_data.append({
            'Initiative': initiative['name'],
            'Start': start,
            'End': end,
            'Priority': initiative['priority'],
            'Duration': f"{initiative['duration']} months"
        })
    
    gantt_df = pd.DataFrame(gantt_data)
    
    # Create timeline visualization
    fig_timeline = px.timeline(
        gantt_df,
        x_start='Start',
        x_end='End', 
        y='Initiative',
        color='Priority',
        title='Strategic Implementation Timeline',
        hover_data={'Duration': True}
    )
    
    fig_timeline.update_layout(height=400)
    st.plotly_chart(fig_timeline, use_container_width=True)

    # ===================
    # Success Metrics & KPIs
    # ===================
    st.markdown("---")
    st.subheader("📊 Success Metrics & KPIs")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        **🎯 Revenue Metrics**
        - Monthly Revenue Growth: +25%
        - Average Order Value: +20%
        - Customer Lifetime Value: +30%
        - Market Share: +15%
        """)
    
    with col2:
        st.markdown("""
        **👥 Customer Metrics** 
        - Customer Acquisition: +40%
        - Retention Rate: +25%
        - Customer Satisfaction: 4.5+/5.0
        - Repeat Purchase Rate: +35%
        """)
    
    with col3:
        st.markdown("""
        **⚡ Operational Metrics**
        - Order Processing Time: -20%
        - Delivery Performance: 95%+ on-time
        - Inventory Turnover: +30%
        - Cost per Acquisition: -15%
        """)

    # ===================
    # Next Steps
    # ===================
    st.markdown("---")
    st.subheader("🚀 Next Steps")
    
    st.success("""
    **Immediate Actions (Next 30 Days):**
    1. **Setup tracking systems** untuk key performance indicators
    2. **Prioritize quick wins** - mulai dengan Payment Method Optimization
    3. **Form cross-functional teams** untuk setiap strategic initiative
    4. **Establish baseline metrics** sebelum implementation
    5. **Create detailed project plans** dengan milestones dan deadlines
    """)
    
    st.info("""
    **📞 Recommended Next Meeting:**
    Schedule strategic planning session dengan leadership team untuk:
    - Finalize priority initiatives
    - Allocate budget dan resources  
    - Set specific timelines dan milestones
    - Establish accountability dan review cycles
    """)

    # ===================
    # Download Report
    # ===================
    st.markdown("---")
    
    if st.button("📥 Generate Strategic Report"):
        # Create summary report
        report_data = {
            'Current Performance': {
                'Total Revenue': f"€ {total_revenue:,.0f}",
                'Total Orders': f"{total_orders:,}",
                'Unique Customers': f"{total_customers:,}",
                'Average Order Value': f"€ {avg_order_value:,.0f}"
            },
            'Top 5 Recommendations': top_recommendations[['Initiative', 'Impact', 'Effort', 'Revenue_Potential', 'Timeline']].to_dict('records'),
            'ROI Projections': {
                'Investment': f"€ {investment_amount:,.0f}M",
                'Expected ROI': f"{roi_percentage:.1f}%",
                'Payback Period': f"{payback_months:.1f} months",
                'Annual Revenue Increase': f"€ {annual_revenue_increase:,.0f}"
            }
        }
        
        st.success("✅ Strategic report generated successfully!")
        st.json(report_data)
        st.markdown("*Copy laporan di atas untuk dokumentasi atau presentasi*")
# Footer
st.markdown("---")
st.markdown("📊 NAH Team | SSDC E-Commerce 2025")
