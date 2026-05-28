import streamlit as st
import pandas as pd
import psycopg2
import os
from dotenv import load_dotenv
import plotly.express as px

load_dotenv()

st.set_page_config(page_title="Wetall Scan Monitor", layout="wide")


# 1. CONNEXION BDD
@st.cache_resource
def get_connection():
    return psycopg2.connect(os.environ.get("DATABASE_URL"))


def load_data():
    query = """
    SELECT 
        f.date_scan, 
        p.nom_produit, 
        p.url_wetall, -- Ajout de l'URL source
        f.status_code, 
        f.http_code_marchand, 
        f.url_marchand_finale
    FROM fact_stock_status f
    JOIN dim_produit p ON f.produit_id = p.produit_id
    ORDER BY f.date_scan DESC
    LIMIT 1000;
    """
    conn = get_connection()
    df = pd.read_sql(query, conn)
    return df


# 2. INTERFACE
st.title("📊 Wetall Stock Monitor")

try:
    df = load_data()

    # --- KPI ---
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Scans", len(df))
    with col2:
        ok_count = len(df[df["status_code"] == "OK"])
        st.metric("Succès (OK)", ok_count, delta=f"{(ok_count/len(df)*100):.1f}%")
    with col3:
        err_count = len(df[df["status_code"].str.contains("Erreur|bloquée|Brisé")])
        st.metric("Alertes / Erreurs", err_count, delta_color="inverse")

    st.divider()

    # --- ANALYSE DES STATUTS ---
    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Répartition des Statuts")
        fig_status = px.pie(
            df,
            names="status_code",
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Safe,
        )
        st.plotly_chart(fig_status, use_container_width=True)

    with c2:
        st.subheader("HTTP Codes Marchands")
        # On filtre les codes 0 (erreurs techniques) pour l'analyse
        codes_df = df[df["http_code_marchand"] > 0]
        fig_codes = px.histogram(codes_df, x="http_code_marchand", color="status_code")
        st.plotly_chart(fig_codes, use_container_width=True)

    # --- TABLEAU DÉTAILLÉ ---
    st.subheader("Derniers Scans")

    # Filtre interactif
    status_filter = st.multiselect(
        "Filtrer par statut",
        options=df["status_code"].unique(),
        default=df["status_code"].unique(),
    )
    filtered_df = df[df["status_code"].isin(status_filter)]

    st.dataframe(
        filtered_df,
        column_config={
            "url_wetall": st.column_config.LinkColumn(
                "Page Wetall"
            ),  # Colonne cliquable
            "url_marchand_finale": st.column_config.LinkColumn("Lien Marchand"),
            "date_scan": st.column_config.DatetimeColumn(
                "Date", format="DD/MM/YY HH:mm"
            ),
        },
        use_container_width=True,
        hide_index=True,
    )

except Exception as e:
    st.error(f"Erreur lors du chargement des données : {e}")
    st.info("Vérifie que ta variable DATABASE_URL est bien configurée.")
