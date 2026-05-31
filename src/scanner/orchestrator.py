"""
Orchestrateur du scan d'un produit Wetall avec support Auto-Healing IA.
"""

import logging
import random
import time
import os
import smtplib
from email.message import EmailMessage

import httpx
from bs4 import BeautifulSoup
from github import Github

from .analyzer import analyze_merchant_status
from .http_client import build_headers, fetch_with_fallback, resolve_affiliation_link
from .parser import get_buy_link_from_wetall, normalize_amazon_url

logger = logging.getLogger(__name__)

ScanOutput = tuple[str, int, str | None, str]


def _execute_auto_healing(merchant_name: str, url: str, debug_info: str) -> str:
    """
    Appelle l'API LLM (Gemini/Groq) pour analyser le blocage de scraping 
    et formuler une proposition de modification de code.
    """
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GROQ_API_KEY")
    if not api_key:
        return "# Clé API LLM manquante pour la génération du correctif."

    prompt = f"""
    En tant que Senior Data Engineer expert en Python et Web Scraping, analyse ce blocage survenu sur le site : {merchant_name}.
    URL cible : {url}
    Logs d'erreur : {debug_info}
    
    Génère uniquement une fonction d'analyse python privée à injecter à la fin de 'analyzer.py' nommée `_check_{merchant_name.lower()}(url: str, html: str) -> ScanResult | None:`.
    Ajoute également le marqueur de chaînes de caractères de rupture au début du fichier.
    Rends uniquement le code brut à ajouter, sans commentaires markdown additionnels.
    """
    try:
        # Exemple d'appel standardisé via HTTP POST pour éviter d'imposer une lib lourde
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        # Endpoint Gemini (à adapter selon le fournisseur sélectionné)
        url_api = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
        
        with httpx.Client() as client:
            r = client.post(f"{url_api}?key={api_key}", json=payload, timeout=20)
            if r.status_code == 200:
                return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip("`python\n")
    except Exception as e:
        logger.error("Échec génération correctif LLM : %s", e)
    return f"# Échec de la génération automatique du code de résolution."


def _deploy_pull_request_healing(merchant_name: str, code_proposal: str):
    """Crée une branche et soumet une Pull Request directement sur le dépôt GitHub."""
    gh_token = os.environ.get("GH_TOKEN")
    repo_slug = os.environ.get("GITHUB_REPOSITORY") # Format 'user/repo'
    
    if not gh_token or not repo_slug:
        logger.warning("Variables d'environnement GITHUB manquantes. Annulation de la PR.")
        return None

    try:
        gh = Github(gh_token)
        repo = gh.get_repo(repo_slug)
        main_ref = repo.get_git_ref("heads/main")
        
        feature_branch = f"feature/auto-fix-{merchant_name.lower().replace(' ', '-')}"
        repo.create_git_ref(ref=f"refs/heads/{feature_branch}", sha=main_ref.object.sha)
        
        file_path = "analyzer.py"
        contents = repo.get_contents(file_path, ref=feature_branch)
        current_code = contents.decoded_content.decode("utf-8")
        
        # Injection propre de la nouvelle règle générée par l'IA
        updated_code = current_code + f"\n\n# --- RÈGLE AUTO-HEALING POUR {merchant_name.upper()} ---\n" + code_proposal
        
        repo.update_file(
            path=file_path,
            message=f"fix(engine): ajout de la règle d'analyse pour {merchant_name}",
            content=updated_code,
            sha=contents.sha,
            branch=feature_branch
        )
        
        pr = repo.create_pull(
            title=f"🤖 [Auto-Healing] Support correctif pour {merchant_name}",
            body=f"Une anomalie récurrente ou un blocage a été détecté sur **{merchant_name}**.\n\n### Proposition de code :\n```python\n{code_proposal}\n
```",
            head=feature_branch,
            base="main"
        )
        return pr.html_url
    except Exception as e:
        logger.error("Impossible de pousser la Pull Request : %s", e)
        return None


def _send_email_report(merchant_name: str, url: str, debug_msg: str, pr_url: str | None):
    """Envoie un rapport structuré sur ta boîte mail, interceptable par tes filtres."""
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASSWORD")
    
    if not smtp_user or not smtp_pass:
        return

    msg = EmailMessage()
    msg["Subject"] = f"[SCANNER-ALERT] [{merchant_name}] Incident de Traitement"
    msg["From"] = smtp_user
    msg["To"] = "michael-alpinedata@gmail.com"
    
    content = f"""Rapport d'incident de scraping automatisé.
    
Marchand : {merchant_name}
URL Source : {url}
Détails d'erreur : {debug_msg}

Action corrective IA : {"Pull Request ouverte avec succès : " + pr_url if pr_url else "Échec de l'auto-healing Git."}
"""
    msg.set_content(content)
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
    except Exception as e:
        logger.error("Échec de l'envoi de l'e-mail d'alerte : %s", e)


def _scan_merchant(client: httpx.Client, buy_link: str, headers: dict) -> ScanOutput:
    """Scanne le marchand final en résolvant au préalable les liens d'affiliation."""
    # Résolution transparente de Link Synergy avant requêtage de contenu
    buy_link = resolve_affiliation_link(buy_link)
    buy_link = normalize_amazon_url(buy_link)
    
    # Extraction propre du nom de domaine pour le rapport d'erreur
    merchant_name = buy_link.split("//")[-1].split("/")[0].replace("www.", "")

    logger.info("Scan marchand : %s...", buy_link[:40])
    time.sleep(random.uniform(5, 10))

    resp_m = fetch_with_fallback(client, buy_link, headers)

    # Détection des murs de sécurité ou des échecs d'accès persistants
    if resp_m.status_code in (401, 403, 503):
        debug_info = f"Code HTTP {resp_m.status_code} - Pare-feu ou blocage actif."
        
        # Enclenchement de la boucle auto-healing
        logger.warning("Lancement de la remédiation IA pour %s", merchant_name)
        code_fix = _execute_auto_healing(merchant_name, buy_link, debug_info)
        pr_link = _deploy_pull_request_healing(merchant_name, code_fix)
        _send_email_report(merchant_name, buy_link, debug_info, pr_link)

        return "Vérification bloquée (403)", resp_m.status_code, str(resp_m.url), f"Pare-feu marchand. PR: {pr_link}"
        
    if resp_m.status_code == 404:
        return "Lien Brisé (404)", 404, str(resp_m.url), "Erreur 404 serveur"

    status, msg = analyze_merchant_status(str(resp_m.url), resp_m.text)
    return status, resp_m.status_code, str(resp_m.url), msg


def smart_scan(client: httpx.Client, url_wetall: str) -> ScanOutput:
    headers = build_headers()
    try:
        wetall_result = _fetch_wetall_page(client, url_wetall, headers)
        if isinstance(wetall_result, tuple): return wetall_result
        resp_wetall = wetall_result

        link_result = _extract_buy_link(resp_wetall)
        if isinstance(link_result, tuple): return link_result
        buy_link = link_result

        return _scan_merchant(client, buy_link, headers)
    except Exception as exc:
        return "Erreur technique", 0, None, f"Exception: {str(exc)[:50]}"

# Conservation des stubs de fonctions internes héritées pour le fonctionnement nominal
def _fetch_wetall_page(client: httpx.Client, url_wetall: str, headers: dict):
    time.sleep(random.uniform(2, 4))
    resp = client.get(url_wetall, headers=headers)
    if resp.status_code != 200:
        return (f"Erreur Wetall {resp.status_code}", resp.status_code, None, "Fail Wetall")
    return resp

def _extract_buy_link(resp_wetall: httpx.Response):
    soup = BeautifulSoup(resp_wetall.text, "html.parser")
    buy_link, _ = get_buy_link_from_wetall(soup)
    if not buy_link:
        if soup.find("form", class_="variations_form"): return "Variations (Taille/Couleur)", 200, None, "Structure variations"
        if "en rupture" in resp_wetall.text.lower(): return "Rupture de stock", 200, None, "Marqueur rupture Wetall"
        return "Bouton non trouvé", 200, None, "Aucun lien extrait"
    return buy_link
