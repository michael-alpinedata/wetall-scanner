import os

import pandas as pd
import plotly.express as px
import psycopg2
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Wetall Scan Monitor", layout="wide")


# 1. CONNEXION BDD
# Supprime le @st.cache_resource qui posait problème
def load_data():
    query = """
    SELECT 
        f.date_scan, 
        p.nom_produit, 
        p.url_wetall,
        f.status_code, 
        f.http_code_marchand, 
        f.url_marchand_finale,
        f.debug_info
    FROM fact_stock_status f
    JOIN dim_produit p ON f.produit_id = p.produit_id
    ORDER BY f.date_scan DESC
    LIMIT 1000;
    """
    try:
        # On ne met plus @st.cache_resource ici pour forcer une nouvelle
        # connexion si la précédente a été coupée par Neon
        with psycopg2.connect(os.environ.get("DATABASE_URL")) as conn:
            df = pd.read_sql(query, conn)
        return df
    except Exception as e:
        st.error(f"Erreur lors du chargement des données : {e}")
        return (
            pd.DataFrame()
        )  # Retourne un DF vide pour éviter de faire planter les graphiques


# 2. INTERFACE
st.title("📊 Wetall Stock Monitor")

try:
    df = load_data()

    # Mapping des codes pour une lecture humaine
    CODE_LABELS = {
        0: "Erreur Technique (Timeout/Crash)",
        200: "Succès (OK / Rupture détectée)",
        401: "Lien Expiré / Privé (401)",
        403: "Blocage Anti-Bot (403)",
        404: "Lien Mort (404 Not Found)",
        500: "Erreur Serveur Marchand (500)",
    }

    # Utilisation d'une fonction lambda pour le fillna dynamique si le code n'est pas
    # dans le dico
    df["label_erreur"] = df["http_code_marchand"].map(CODE_LABELS)
    df["label_erreur"] = df["label_erreur"].fillna(
        df["http_code_marchand"].apply(lambda x: f"Autre Erreur ({x})")
    )

    # On filtre pour ne garder que les anomalies
    df_anomalies = df[df["http_code_marchand"] != 200]

    # --- KPI ---
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Scans", len(df))
    with col2:
        ok_count = len(df[df["status_code"] == "OK"])
        st.metric("Succès (OK)", ok_count, delta=f"{(ok_count / len(df) * 100):.1f}%")
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
        st.subheader("Anomalies Marchands (Détails)")

        # On utilise df_anomalies (qui exclut les succès 200) pour zoomer sur ce qui
        # pose problème
        if not df_anomalies.empty:
            fig_codes = px.histogram(
                df_anomalies,
                x="label_erreur",
                color="status_code",
                labels={
                    "label_erreur": "Type d'anomalie",
                    "count": "Nombre de produits",
                },
                category_orders={
                    "label_erreur": [
                        "Lien Mort (404 Not Found)",
                        "Blocage Marchand (403 Forbidden)",
                        "Erreur Technique (Timeout/Crash)",
                        "Accès Restreint (401 Unauthorized)",
                        "Erreur Serveur Marchand (500)",
                    ]
                },
            )
            # Amélioration du design pour éviter que les longs labels se chevauchent
            fig_codes.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig_codes, use_container_width=True)
        else:
            st.success("Aucune anomalie détectée sur ce lot ! 🎉")

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
            "debug_info": st.column_config.TextColumn("Diagnostic Scanner"),
        },
        use_container_width=True,
        hide_index=True,
    )

except Exception as e:
    st.error(f"Erreur lors du chargement des données : {e}")
    st.info("Vérifie que ta variable DATABASE_URL est bien configurée.")
