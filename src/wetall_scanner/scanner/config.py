MERCHANT_CONFIGS = {
    "amazon": {
        "in_stock_selectors": ["#add-to-cart-button", "#buy-now-button"],
        "out_of_stock_keywords": ["indisponible", "rupture"],
        "fallback_message": "Aucun indicateur de stock trouvé (Fallback)",
    },
    "cdiscount": {
        "in_stock_selectors": [".btn-buy"],
        "out_of_stock_keywords": ["vendu", "épuisé"],
        "fallback_message": "Pas de bouton d'achat détecté",
    },
}
