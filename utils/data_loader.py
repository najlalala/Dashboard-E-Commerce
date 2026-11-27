
import pandas as pd
import os
import gdown
import streamlit as st


@st.cache_data(ttl=3600, max_entries=1)
def load_all_data(base_path="data"):

    os.makedirs(base_path, exist_ok=True)

    geolocation_url = (
        "https://drive.google.com/uc?id=1Wdq9QnJaOQZFKgFtQtey9ExTeEsQCtcJ"
    )

    geolocation_path = os.path.join(
        base_path, "geolocation_dataset.csv"
    )

    if not os.path.exists(geolocation_path):
        gdown.download(
            geolocation_url,
            geolocation_path,
            quiet=False,
            fuzzy=True
        )

    def read_csv(filename):
        return pd.read_csv(
            os.path.join(base_path, filename),
            low_memory=False
        )

    customers = read_csv("customers_dataset.csv")
    leads_qualified = read_csv(
        "marketing_qualified_leads_dataset.csv"
    )
    leads_closed = read_csv("closed_deals_dataset.csv")
    order_items = read_csv("order_items_dataset.csv")
    order_payments = read_csv("order_payments_dataset.csv")
    order_reviews = read_csv("order_reviews_dataset.csv")
    orders = read_csv("orders_dataset.csv")
    product_cat = read_csv(
        "product_category_name_translation.csv"
    )
    products = read_csv("products_dataset.csv")
    sellers = read_csv("sellers_dataset.csv")

    geo_chunks = []

    for chunk in pd.read_csv(
        geolocation_path,
        chunksize=100_000,
        low_memory=False,
        dtype={
            "geolocation_zip_code_prefix": "string"
        }
    ):

        grouped = (
            chunk.groupby("geolocation_zip_code_prefix")
            .agg(
                lat_sum=("geolocation_lat", "sum"),
                lng_sum=("geolocation_lng", "sum"),
                lat_count=("geolocation_lat", "count"),
                city=("geolocation_city", "first"),
                state=("geolocation_state", "first")
            )
            .reset_index()
        )

        geo_chunks.append(grouped)

        del chunk

    geolocation = pd.concat(
        geo_chunks,
        ignore_index=True
    )

    geolocation = (
        geolocation.groupby(
            "geolocation_zip_code_prefix",
            as_index=False
        )
        .agg(
            lat_sum=("lat_sum", "sum"),
            lng_sum=("lng_sum", "sum"),
            lat_count=("lat_count", "sum"),
            city=("city", "first"),
            state=("state", "first")
        )
    )

    geolocation["geolocation_lat"] = (
        geolocation["lat_sum"] / geolocation["lat_count"]
    )

    geolocation["geolocation_lng"] = (
        geolocation["lng_sum"] / geolocation["lat_count"]
    )

    geolocation = geolocation[
        [
            "geolocation_zip_code_prefix",
            "geolocation_lat",
            "geolocation_lng",
            "city",
            "state"
        ]
    ]

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
