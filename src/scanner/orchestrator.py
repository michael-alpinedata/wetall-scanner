"""
Orchestrateur du scan d'un produit Wetall avec support Auto-Healing IA.
"""

import logging
import os
import random
import smtplib
import time
from email.message import EmailMessage

import httpx
from bs4 import BeautifulSoup
from github import Github

from .analyzer import analyze_merchant_status
from .http_client import build_headers, fetch_with_fallback, resolve_affiliation_link
from .parser import get_buy_link_from_wetall, normalize_amazon_url

logger = logging.getLogger(__name__)

# Type alias
ScanOutput = tuple[str, int, str | None, str]


# def is_bot_blocked(html_content: str, is_amazon: bool = False) -> bool:
#     """BUGGY (unused, left for possible future evolution): 
#     - gros risque de faux positif blocked alors que ras 
#     (mot clé 'captcha' détecté sur page saine et produit avec ou sans stock)
#     - Détecte les blocages et logue le coupable si le niveau de log est DEBUG."""
#     # On ne scanne que les 2000 premiers caractères pour éviter les faux positifs du footer
#     context = html_content[:2000].lower()

#     amazon_block_signatures = [
#         "to discuss automated access to amazon data",
#         "verify you are human",
#         "enter the characters you see",
#     ]

#     # On définit les signatures à vérifier
#     # attention gros risque de faux positif blocked alors que ras (mot clé captcha détecté)
#     signatures = amazon_block_signatures if is_amazon else ["captcha", "robot"]

#     for sig in signatures:
#         if sig in context:
#             # ICI LE DEBUG : logue uniquement si on est en mode debug
#             logger.debug(f"Détection bot : Signature '{sig}' trouvée sur le site.")
#             return True

#     return False


# def _execute_auto_healing(
#     merchant_name: str, url: str, debug_info: str, html_content: str = ""
# ) -> str:
#     """Appelle l'API Gemini avec un contexte tronqué pour éviter les timeouts."""
#     api_key = os.environ.get("GEMINI_API_KEY")
#     if not api_key:
#         return "# Clé API manquante."

#     # Tronquage agressif du HTML pour le LLM (800 chars suffisent pour diagnostiquer le WAF)
#     short_html = html_content[:800]
#     prompt = f"Analyse le blocage sur {merchant_name}. URL: {url}. Logs: {debug_info}. HTML: {short_html}. Propose un correctif headers."

#     url_api = "https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent"
#     try:
#         # Timeout augmenté à 45s pour la résilience
#         with httpx.Client(timeout=45.0) as client:
#             r = client.post(
#                 f"{url_api}?key={api_key}",
#                 json={"contents": [{"parts": [{"text": prompt}]}]},
#             )
#             r.raise_for_status()
#             return (
#                 r.json()["candidates"][0]["content"]["parts"][0]["text"]
#                 .strip("`python\n")
#                 .strip()
#             )
#     except Exception as e:
#         logger.error(f"Échec LLM (Auto-healing) : {e}")
#         return f"# Échec diagnostic IA : {e}"


# def _deploy_pull_request_healing(merchant_name: str, code_proposal: str) -> str | None:
#     """Crée une branche et soumet une Pull Request via PyGithub."""
#     token, repo_slug = os.environ.get("GH_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
#     if not (token and repo_slug):
#         return None
#     if not (token and repo_slug):
#         return None
#     try:
#         repo = Github(token).get_repo(repo_slug)
#         ts = int(time.time())
#         branch = f"feature/auto-fix-{merchant_name.lower().replace(' ', '-')}-{ts}"
#         repo.create_git_ref(
#             ref=f"refs/heads/{branch}", sha=repo.get_git_ref("heads/main").object.sha
#         )

#         path = "src/scanner/analyzer.py"
#         file_content = repo.get_contents(path, ref=branch)
#         new_content = (
#             file_content.decoded_content.decode("utf-8")
#             + f"\n\n# Auto-Healing {merchant_name}\n{code_proposal}"
#         )

#         repo.update_file(
#             path,
#             f"fix: auto-healing {merchant_name}",
#             new_content,
#             file_content.sha,
#             branch=branch,
#         )
#         pr_body = f"""### 🤖 Auto-Healing Report for {merchant_name}\n\n```python\n{code_proposal}\n```"""
#         pr = repo.create_pull(
#             title=f"🤖 [Auto-Healing] {merchant_name}",
#             body=pr_body,
#             head=branch,
#             base="main",
#         )
#         pr = repo.create_pull(
#             title=f"🤖 [Auto-Healing] {merchant_name}",
#             body=pr_body,
#             head=branch,
#             base="main",
#         )
#         logger.info(f"PR créée : {pr.html_url}")
#         return pr.html_url
#     except Exception as e:
#         logger.error(f"Erreur Git : {e}")
#         return None
#         logger.error(f"Erreur Git : {e}")
#         return None


# def _send_email_report(
#     merchant_name: str, url: str, debug_msg: str, pr_url: str | None
# ):
#     """Envoie un rapport structuré sur ta boîte mail."""
#     smtp_user = os.environ.get("SMTP_USER")
#     smtp_pass = os.environ.get("SMTP_PASSWORD")


#     if not smtp_user or not smtp_pass:
#         return

#     msg = EmailMessage()
#     msg["Subject"] = f"[SCANNER-ALERT] [{merchant_name}] Incident de Traitement"
#     msg["From"] = smtp_user
#     msg["To"] = "michael-alpinedata@gmail.com"


#     content = f"""Rapport d'incident de scraping automatisé.
    
# Marchand : {merchant_name}
# URL Source : {url}
# Détails d'erreur : {debug_msg}

# Action corrective IA : {"Pull Request ouverte avec succès : " + pr_url if pr_url else "Échec de l'auto-healing Git."}
# """
#     msg.set_content(content)
#     try:
#         with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
#             server.login(smtp_user, smtp_pass)
#             server.send_message(msg)
#     except Exception as e:
#         logger.error("Échec de l'envoi de l'e-mail d'alerte : %s", e)

# temporairement désactivé pour gagner du temps 
def _scan_merchant(client: httpx.Client, buy_link: str, headers: dict) -> ScanOutput:
    """Scanne le marchand final avec gestion intelligente des blocages."""
    buy_link = resolve_affiliation_link(buy_link)
    if not buy_link or "://" not in buy_link:
        if buy_link and (buy_link.startswith("/dp/") or buy_link.startswith("dp/")):
            buy_link = normalize_amazon_url(buy_link)
        else:
            raise ValueError("Lien Marchand Invalide")

    # Nom du marchand pour les logs et debug
    merchant = buy_link.split("//")[-1].split("/")[0].replace("www.", "")

    headers["Referer"] = "https://www.google.com/"

    # logger.info(f"Scan marchand : {merchant} | URL: {buy_link[:40]}")
    # time.sleep(random.uniform(3, 7))
    # resp = fetch_with_fallback(client, buy_link, headers)

    # 1. Erreur Réseau / Pare-feu
    # if resp.status_code in (401, 403, 503):
    #     logger.warning(f"Blocage {resp.status_code} sur {merchant}.")
     #    return (
       #      "Vérification bloquée (403)",
       #      resp.status_code,
        #     str(resp.url),
      #       f"ERR_HTTP_BLOCK | {merchant}",
    #     )

    # 2. Gestion 404
   # if resp.status_code in (404):
        # logger.warning(f"Blocage {resp.status_code} détecté sur {merchant}. Auto-healing...")
        # fix = _execute_auto_healing(merchant, buy_link, f"HTTP {resp.status_code}")
        # pr = _deploy_pull_request_healing(merchant, fix)
        # _send_email_report(merchant, buy_link, f"HTTP {resp.status_code}", pr)
     #    return (
      #       "Vérification bloquée (403)",
      #       resp.status_code,
       #      str(resp.url),
     #        "Pare-feu marchand",
     #    )

   #  if resp.status_code == 404:
   #      return "Lien Brisé (404)", 404, str(resp.url), "ERR_404_SERVER"

    # 3. Analyse standard (Le parser se chargera de dire si le produit est là ou pas)
 #    status, msg = analyze_merchant_status(str(resp.url), resp.text)

    # Si le status est OK mais qu'on suspecte quand même une page de challenge
    # (parce que le parser a échoué), on marquera ça comme ERR_PARSER
  #   if status == "Bouton non trouvé":
  #       return (
  #           status,
  #           resp.status_code,
  #           str(resp.url),
  #           f"ERR_PARSER_MISSING_ELEMENT | {merchant}",
  #       )

    # return status, resp.status_code, str(resp.url), msg
    return 'not yet scanned', 0, str(buy_link), 'not yet scanned'
    


def smart_scan(client: httpx.Client, url_wetall: str) -> ScanOutput:
    """Orchestre le scan complet d'un produit Wetall."""
    headers = build_headers()
    try:
        wetall_result = _fetch_wetall_page(client, url_wetall, headers)
        if isinstance(wetall_result, tuple):
            return wetall_result
        resp_wetall = wetall_result

        link_result = _extract_buy_link(resp_wetall)
        if isinstance(link_result, tuple):
            return link_result
        buy_link = link_result

        return _scan_merchant(client, buy_link, headers)
    except Exception as exc:
        return "Erreur technique", 0, None, f"Exception: {str(exc)[:50]}"


def _fetch_wetall_page(client: httpx.Client, url_wetall: str, headers: dict):
    time.sleep(random.uniform(2, 4))
    resp = client.get(url_wetall, headers=headers)
    if resp.status_code != 200:
        return (
            f"Erreur Wetall {resp.status_code}",
            resp.status_code,
            None,
            "Fail Wetall",
        )
    return resp


def _extract_buy_link(resp_wetall: httpx.Response):
    soup = BeautifulSoup(resp_wetall.text, "html.parser")
    buy_link, _ = get_buy_link_from_wetall(soup)
    if not buy_link:
        if soup.find("form", class_="variations_form"):
            return "Variations (Taille/Couleur)", 200, None, "Structure variations"
        if "en rupture" in resp_wetall.text.lower():
            return "Rupture de stock", 200, None, "Marqueur rupture Wetall"
        return "Bouton non trouvé", 200, None, "Aucun lien extrait"
    return buy_link
