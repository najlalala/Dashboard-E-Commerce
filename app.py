import streamlit as st
from utils.data_loader import load_all_data
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np

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

# Sidebar navigasi
st.sidebar.title("📋 Navigasi")
page = st.sidebar.radio("Pilih Halaman", [
    "Executive Overview",
    "Customer & Market Analysis",
    "Product & Leads Performance", 
    "Operational Excellence",
    "Strategic Recommendations"
])

# Date filter
st.sidebar.markdown("---")
st.sidebar.subheader("🗓️ Filter Tanggal")
if not orders_processed['order_purchase_timestamp'].isna().all():
    min_date = orders_processed['order_purchase_timestamp'].min().date()
    max_date = orders_processed['order_purchase_timestamp'].max().date()
    
    date_range = st.sidebar.date_input(
        "Pilih rentang tanggal:",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )
    
    if len(date_range) == 2:
        start_date, end_date = date_range
        # Create mask using processed orders
        mask = (orders_processed['order_purchase_timestamp'].dt.date >= start_date) & (orders_processed['order_purchase_timestamp'].dt.date <= end_date)
        orders_filtered = orders_processed[mask]
        
        # Filter merged dataframes using order_id
        filtered_order_ids = orders_filtered['order_id'].tolist()
        orders_payments_filtered = orders_payments[orders_payments['order_id'].isin(filtered_order_ids)]
        orders_items_filtered = orders_items[orders_items['order_id'].isin(filtered_order_ids)]
    else:
        orders_filtered = orders_processed
        orders_payments_filtered = orders_payments
        orders_items_filtered = orders_items
else:
    orders_filtered = orders_processed
    orders_payments_filtered = orders_payments
    orders_items_filtered = orders_items

# ================================
# 📌 HALAMAN: EXECUTIVE OVERVIEW
# ================================
if page == "Executive Overview":
    st.header("📌 Executive Overview")
    st.markdown("*Gambaran menyeluruh performa bisnis untuk decision makers*")

    # ===================
    # KPI Cards dengan Growth Rate
    # ===================
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_revenue = orders_payments_filtered['payment_value'].sum()
        # Calculate growth rate (comparing with previous period)
        current_month = orders_payments_filtered['month'].max()
        prev_month_data = orders_payments[orders_payments['month'] < current_month]
        prev_revenue = prev_month_data['payment_value'].sum() if not prev_month_data.empty else 0
        growth_rate = ((total_revenue - prev_revenue) / prev_revenue * 100) if prev_revenue > 0 else 0
        
        st.metric(
            "💰 Total Revenue", 
            f"Rp {total_revenue:,.0f}",
            delta=f"{growth_rate:.1f}%" if growth_rate != 0 else None
        )
    
    with col2:
        total_orders = orders_filtered['order_id'].nunique()
        prev_orders = len(prev_month_data) if not prev_month_data.empty else 0
        orders_growth = ((total_orders - prev_orders) / prev_orders * 100) if prev_orders > 0 else 0
        
        st.metric(
            "📦 Total Orders", 
            f"{total_orders:,}",
            delta=f"{orders_growth:.1f}%" if orders_growth != 0 else None
        )
    
    with col3:
        total_customers = orders_filtered['customer_id'].nunique()
        prev_customers = prev_month_data['customer_id'].nunique() if not prev_month_data.empty else 0
        customers_growth = ((total_customers - prev_customers) / prev_customers * 100) if prev_customers > 0 else 0
        
        st.metric(
            "🧑‍🤝‍🧑 Unique Customers", 
            f"{total_customers:,}",
            delta=f"{customers_growth:.1f}%" if customers_growth != 0 else None
        )
    
    with col4:
        avg_order_value = orders_payments_filtered['payment_value'].mean()
        prev_avg = prev_month_data['payment_value'].mean() if not prev_month_data.empty else 0
        aov_growth = ((avg_order_value - prev_avg) / prev_avg * 100) if prev_avg > 0 else 0
        
        st.metric(
            "💳 Avg Order Value", 
            f"Rp {avg_order_value:,.0f}",
            delta=f"{aov_growth:.1f}%" if aov_growth != 0 else None
        )

    st.markdown("---")

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
            yaxis2=dict(title='Revenue (Rp)', side='right', overlaying='y'),
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
    # Geographic Analysis - Improved
    # ===================
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🗺️ Top 10 States by Orders")
        
        # Merge customers with orders to get state info
        customer_orders = orders_filtered.merge(customers, on='customer_id', how='left')
        state_orders = customer_orders.groupby('customer_state').size().reset_index(name='total_orders')
        state_orders = state_orders.sort_values('total_orders', ascending=False).head(10)
        
        fig_states = px.bar(
            state_orders, 
            x='total_orders', 
            y='customer_state',
            orientation='h',
            title='Orders by State (Top 10)',
            labels={'customer_state': 'State', 'total_orders': 'Total Orders'}
        )
        fig_states.update_layout(height=400)
        st.plotly_chart(fig_states, use_container_width=True)
    
    with col2:
        st.subheader("🏆 Top 5 Product Categories")
        
        # Get top product categories
        if not products.empty and not order_items.empty:
            product_sales = order_items.merge(products, on='product_id', how='left')
            category_sales = product_sales.groupby('product_category_name').agg({
                'order_item_id': 'count',
                'price': 'sum'
            }).reset_index()
            category_sales = category_sales.sort_values('order_item_id', ascending=False).head(5)
            
            fig_categories = px.bar(
                category_sales, 
                x='order_item_id', 
                y='product_category_name',
                orientation='h',
                title='Top 5 Categories by Sales Volume',
                labels={'product_category_name': 'Category', 'order_item_id': 'Items Sold'}
            )
            fig_categories.update_layout(height=400)
            st.plotly_chart(fig_categories, use_container_width=True)
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
        - Total Revenue: Rp {total_revenue:,.0f}
        - Average Order Value: Rp {avg_order_value:,.0f}
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
                    'monetary': 'Monetary Value (Rp)',
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
    # Geographic Distribution
    # ===================
    st.subheader("🗺️ Geographic Distribution")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Top Cities Analysis
        customer_geo = orders_filtered.merge(customers, on='customer_id', how='left')
        city_stats = customer_geo.groupby(['customer_city', 'customer_state']).agg({
            'order_id': 'nunique',
            'customer_id': 'nunique'
        }).reset_index()
        city_stats['city_state'] = city_stats['customer_city'] + ', ' + city_stats['customer_state']
        city_stats = city_stats.sort_values('order_id', ascending=False).head(10)
        
        fig_cities = px.bar(
            city_stats,
            x='order_id',
            y='city_state',
            orientation='h',
            title='Top 10 Cities by Orders',
            labels={'order_id': 'Total Orders', 'city_state': 'City, State'}
        )
        fig_cities.update_layout(height=500)
        st.plotly_chart(fig_cities, use_container_width=True)
    
    with col2:
        # Revenue by State
        state_revenue = orders_payments_filtered.merge(customers, on='customer_id', how='left')
        state_revenue_stats = state_revenue.groupby('customer_state').agg({
            'payment_value': 'sum',
            'order_id': 'nunique'
        }).reset_index()
        state_revenue_stats['avg_order_value'] = state_revenue_stats['payment_value'] / state_revenue_stats['order_id']
        state_revenue_stats = state_revenue_stats.sort_values('payment_value', ascending=False).head(10)
        
        fig_state_revenue = px.bar(
            state_revenue_stats,
            x='payment_value',
            y='customer_state',
            orientation='h',
            title='Top 10 States by Revenue',
            labels={'payment_value': 'Total Revenue (Rp)', 'customer_state': 'State'}
        )
        fig_state_revenue.update_layout(height=500)
        st.plotly_chart(fig_state_revenue, use_container_width=True)

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
            labels={'total_spent': 'Total Spent (Rp)', 'count': 'Number of Customers'}
        )
        fig_clv.update_layout(height=350)
        st.plotly_chart(fig_clv, use_container_width=True)
        
        # CLV Statistics
        avg_clv = clv_data['total_spent'].mean()
        median_clv = clv_data['total_spent'].median()
        st.metric("Average CLV", f"Rp {avg_clv:,.0f}")
        st.metric("Median CLV", f"Rp {median_clv:,.0f}")
    
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
    # New vs Returning Customer Analysis (Enhanced)
    # ===================
    st.subheader("👥 Customer Acquisition & Retention Analysis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Customer acquisition trend
        first_order = orders_filtered.groupby('customer_id')['order_purchase_timestamp'].min().reset_index()
        first_order['acquisition_month'] = first_order['order_purchase_timestamp'].dt.strftime('%Y-%m')
        acquisition_trend = first_order.groupby('acquisition_month').size().reset_index(name='new_customers')
        
        fig_acquisition = px.line(
            acquisition_trend,
            x='acquisition_month',
            y='new_customers',
            title='Customer Acquisition Trend',
            labels={'acquisition_month': 'Month', 'new_customers': 'New Customers'}
        )
        st.plotly_chart(fig_acquisition, use_container_width=True)
    
    with col2:
        # Cohort retention analysis (simplified)
        cohort_data = orders_filtered.merge(first_order, on='customer_id', suffixes=('', '_first'))
        cohort_data['period_number'] = (
            cohort_data['order_purchase_timestamp'].dt.to_period('M') - 
            cohort_data['order_purchase_timestamp_first'].dt.to_period('M')
        ).apply(lambda x: x.n)
        
        cohort_table = cohort_data.groupby(['acquisition_month', 'period_number'])['customer_id'].nunique().reset_index()
        cohort_sizes = cohort_data.groupby('acquisition_month')['customer_id'].nunique()
        
        # Calculate retention rates
        cohort_retention = cohort_table.set_index(['acquisition_month', 'period_number'])['customer_id'].unstack(fill_value=0)
        
        if not cohort_retention.empty:
            for i in cohort_retention.index:
                cohort_retention.loc[i] = cohort_retention.loc[i] / cohort_sizes[i]
            
            fig_cohort = px.imshow(
                cohort_retention.values,
                x=[f'Month {i}' for i in cohort_retention.columns],
                y=cohort_retention.index,
                title='Customer Retention Cohort Analysis',
                aspect='auto'
            )
            st.plotly_chart(fig_cohort, use_container_width=True)
        else:
            st.info("Insufficient data for cohort analysis")

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
        - Average CLV: Rp {avg_clv:,.0f}
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
            top_categories['total_revenue'] = top_categories['total_revenue'].apply(lambda x: f"Rp {x:,.0f}")
            st.dataframe(top_categories, use_container_width=True)
    else:
        st.info("Product category data not available")

    # ===================
    # Product Rating vs Sales Analysis
    # ===================
    st.subheader("⭐ Product Rating vs Sales Performance")
    
    @st.cache_data
    def get_product_rating_sales():
        if not products.empty and not order_items.empty:
            # Get product sales data
            product_sales = order_items.merge(products, on='product_id', how='left')
            order_ids_filtered = orders_filtered['order_id'].tolist()
            product_sales_filtered = product_sales[product_sales['order_id'].isin(order_ids_filtered)]
            
            # Aggregate by product
            product_metrics = product_sales_filtered.groupby(['product_id', 'product_category_name']).agg({
                'order_item_id': 'count',
                'price': 'sum'
            }).reset_index()
            
            # Cek kolom yang tersedia di products
            available_cols = products.columns.tolist()
            expected_cols = ['product_id', 'product_name_length', 'product_description_length', 
                            'product_photos_qty', 'product_weight_g', 'product_length_cm', 
                            'product_height_cm', 'product_width_cm']

            selected_cols = [col for col in expected_cols if col in available_cols]

            # Merge with product details
            product_metrics = product_metrics.merge(
                products[selected_cols],
                on='product_id', how='left'
            )

            # Rename kolom dasar saja (sisanya biarkan otomatis)
            product_metrics = product_metrics.rename(columns={
                'product_category_name': 'category',
                'order_item_id': 'sales_volume',
                'price': 'total_revenue',
                'product_name_length': 'name_length',
                'product_description_length': 'description_length',
                'product_photos_qty': 'photos_qty',
                'product_weight_g': 'weight_g',
                'product_length_cm': 'length_cm',
                'product_height_cm': 'height_cm',
                'product_width_cm': 'width_cm'
            })

            return product_metrics
        return pd.DataFrame()

    
    product_rating_sales = get_product_rating_sales()
    
    if not product_rating_sales.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            # Scatter plot: Photos vs Sales
            fig_photos_sales = px.scatter(
                product_rating_sales,
                x='photos_qty',
                y='sales_volume',
                size='total_revenue',
                color='category',
                title='Product Photos vs Sales Volume',
                labels={'photos_qty': 'Number of Photos', 'sales_volume': 'Sales Volume'}
            )
            st.plotly_chart(fig_photos_sales, use_container_width=True)
        
        with col2:
            # Weight vs Revenue
            fig_weight_revenue = px.scatter(
                product_rating_sales,
                x='weight_g',
                y='total_revenue',
                size='sales_volume',
                color='category',
                title='Product Weight vs Revenue',
                labels={'weight_g': 'Weight (g)', 'total_revenue': 'Total Revenue'}
            )
            st.plotly_chart(fig_weight_revenue, use_container_width=True)
    else:
        st.info("Product metrics data not available")

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
    # Product Attributes Impact
    # ===================
    st.subheader("🔍 Product Attributes Impact Analysis")

    if not product_rating_sales.empty:
        # Kolom numerik yang ingin dianalisis korelasinya
        numeric_cols = ['sales_volume', 'total_revenue', 'name_length', 'product_description_length', 
                        'photos_qty', 'weight_g', 'length_cm', 'height_cm', 'width_cm']

        # Filter kolom yang benar-benar tersedia
        available_cols = [col for col in numeric_cols if col in product_rating_sales.columns]

        if len(available_cols) >= 2:
            correlation_data = product_rating_sales[available_cols].corr()

            # Visualisasi matrix korelasi
            fig_corr = px.imshow(
                correlation_data,
                title='Product Attributes Correlation Matrix',
                color_continuous_scale='RdBu_r',
                aspect='auto'
            )
            st.plotly_chart(fig_corr, use_container_width=True)

            # Key correlation metrics
            st.write("**Key Correlations:**")
            col1, col2 = st.columns(2)

            with col1:
                if {'photos_qty', 'sales_volume'}.issubset(correlation_data.columns):
                    photos_sales_corr = correlation_data.loc['photos_qty', 'sales_volume']
                    st.metric("Photos vs Sales", f"{photos_sales_corr:.3f}")
                else:
                    st.metric("Photos vs Sales", "N/A")

                if {'weight_g', 'total_revenue'}.issubset(correlation_data.columns):
                    weight_revenue_corr = correlation_data.loc['weight_g', 'total_revenue']
                    st.metric("Weight vs Revenue", f"{weight_revenue_corr:.3f}")
                else:
                    st.metric("Weight vs Revenue", "N/A")

            with col2:
                if {'description_length', 'sales_volume'}.issubset(correlation_data.columns):
                    desc_sales_corr = correlation_data.loc['description_length', 'sales_volume']
                    st.metric("Description vs Sales", f"{desc_sales_corr:.3f}")
                else:
                    st.metric("Description vs Sales", "N/A")

                if {'name_length', 'total_revenue'}.issubset(correlation_data.columns):
                    name_revenue_corr = correlation_data.loc['name_length', 'total_revenue']
                    st.metric("Name Length vs Revenue", f"{name_revenue_corr:.3f}")
                else:
                    st.metric("Name Length vs Revenue", "N/A")
        else:
            st.warning("Tidak cukup kolom numerik tersedia untuk analisis korelasi.")
    else:
        st.info("Data produk belum tersedia untuk analisis korelasi.")



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
            - Top Revenue: Rp {top_revenue:,.0f}
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
# 📌 PLACEHOLDER UNTUK HALAMAN LAIN
# ================================
elif page == "Operational Excellence":
    st.header("📌 Operational Excellence")
    st.info("🚧 Halaman ini sedang dalam pengembangan")

elif page == "Strategic Recommendations":
    st.header("📌 Strategic Recommendations")
    st.info("🚧 Halaman ini sedang dalam pengembangan")

# Footer
st.markdown("---")
st.markdown("*Dashboard E-Commerce SSDC - Built with Streamlit & Plotly*")