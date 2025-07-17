import pandas as pd
import os

def load_all_data(base_path="data"):
    customers = pd.read_csv(os.path.join(base_path, 'customers_dataset.csv'))
    geolocation = pd.read_csv(os.path.join(base_path, 'geolocation_dataset.csv'))
    leads_qualified = pd.read_csv(os.path.join(base_path, 'marketing_qualified_leads_dataset.csv'))
    leads_closed = pd.read_csv(os.path.join(base_path, 'closed_deals_dataset.csv'))  
    order_items = pd.read_csv(os.path.join(base_path, 'order_items_dataset.csv'))
    order_payments = pd.read_csv(os.path.join(base_path, 'order_payments_dataset.csv'))
    order_reviews = pd.read_csv(os.path.join(base_path, 'order_reviews_dataset.csv'))
    orders = pd.read_csv(os.path.join(base_path, 'orders_dataset.csv'))
    product_cat = pd.read_csv(os.path.join(base_path, 'product_category_name_translation.csv'))
    products = pd.read_csv(os.path.join(base_path, 'products_dataset.csv'))
    sellers = pd.read_csv(os.path.join(base_path, 'sellers_dataset.csv'))

    return {
        "orders": orders,
        "order_items": order_items,
        "order_payments": order_payments,
        "order_reviews": order_reviews,
        "products": products,
        "product_cat": product_cat,
        "customers": customers,
        "sellers": sellers,
        "geolocation": geolocation,
        "leads_qualified": leads_qualified,
        "leads_closed": leads_closed,
    }
