"""
LinkedIn Keyword Researcher - Notifier
========================================
Envía alertas cuando se encuentran nuevos leads.

Canales soportados:
  • Consola (siempre activo, con colores)
  • Email (SMTP / Gmail)
  • Slack (webhook)
  • Archivo de log diario
"""

import logging
import os
import smtplib
from collections import defaultdict
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional

import requests
from dotenv import load_dotenv

from storage import Lead

load_dotenv()
logger = logging.getLogger(__name__)

# ANSI colors para terminal
RESET   = "\033[0m"
BOLD    = "\033[1m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
CYAN    = "\033[96m"
RED     = "\033[91m"
MAGENTA = "\033[95m"


# ---------------------------------------------------------------------------
# Consola
# ---------------------------------------------------------------------------

def print_lead(lead: Lead, index: int = 0):
    """Imprime un lead formateado en consola."""
    icon = "📢" if lead.search_type == "posts" else ("👤" if lead.search_type == "people" else "🏢")
    print(f"\n{BOLD}{CYAN}{'─'*60}{RESET}")
    print(f"{BOLD}#{index+1} {icon} [{lead.keyword_group}] keyword: '{lead.keyword}'{RESET}")
    print(f"  {BOLD}Nombre:{RESET}   {GREEN}{lead.name}{RESET}")
    if lead.title:
        print(f"  {BOLD}Cargo:{RESET}    {lead.title}")
    if lead.company:
        print(f"  {BOLD}Empresa:{RESET}  {YELLOW}{lead.company}{RESET}")
    if lead.location:
        print(f"  {BOLD}Lugar:{RESET}    {lead.location}")
    if lead.post_content:
        preview = lead.post_content[:200] + ("..." if len(lead.post_content) > 200 else "")
        print(f"  {BOLD}Post:{RESET}     {preview}")
    if lead.post_date:
        print(f"  {BOLD}Fecha:{RESET}    {lead.post_date}")
    print(f"  {BOLD}Perfil:{RESET}   {CYAN}{lead.profile_url}{RESET}")
    print(f"  {BOLD}Encontrado:{RESET} {lead.found_at}")


def print_summary(new_leads: List[Lead], total_saved: int):
    """Imprime resumen al final de la ejecución."""
    by_group = defaultdict(list)
    for l in new_leads:
        by_group[l.keyword_group].append(l)

    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}{GREEN}RESUMEN DE EJECUCIÓN{RESET}")
    print(f"{'='*60}{RESET}")
    print(f"  Nuevos leads encontrados: {BOLD}{GREEN}{len(new_leads)}{RESET}")
    print(f"  Total acumulado:          {BOLD}{total_saved}{RESET}")
    print(f"  Fecha/hora:               {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if by_group:
        print(f"\n{BOLD}Por categoría:{RESET}")
        for group, leads in sorted(by_group.items(), key=lambda x: -len(x[1])):
            print(f"  • {YELLOW}{group}{RESET}: {len(leads)} leads")

    print(f"{'='*60}{RESET}\n")


# ---------------------------------------------------------------------------
# Email (Gmail / SMTP)
# ---------------------------------------------------------------------------

def send_email_alert(new_leads: List[Lead]):
    """Envía resumen por email si hay leads nuevos."""
    smtp_host  = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port  = int(os.getenv("SMTP_PORT", "587"))
    smtp_user  = os.getenv("SMTP_USER", "")
    smtp_pass  = os.getenv("SMTP_PASS", "")
    to_email   = os.getenv("ALERT_EMAIL", "")

    if not all([smtp_user, smtp_pass, to_email]):
        logger.debug("Email no configurado. Saltando envío.")
        return

    subject = f"[LinkedIn Researcher] {len(new_leads)} nuevos leads - {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    # Construir HTML
    rows = ""
    for lead in new_leads:
        rows += f"""
        <tr>
          <td>{lead.keyword_group}</td>
          <td>{lead.keyword}</td>
          <td>{lead.search_type}</td>
          <td><a href="{lead.profile_url}">{lead.name}</a></td>
          <td>{lead.title}</td>
          <td>{lead.company}</td>
          <td>{lead.location}</td>
          <td style="max-width:300px;font-size:12px">{lead.post_content[:150]}</td>
          <td>{lead.found_at[:16]}</td>
        </tr>"""

    html = f"""
    <html><body>
    <h2 style="color:#0077b5">LinkedIn Keyword Researcher</h2>
    <p>Se encontraron <strong>{len(new_leads)} nuevos leads</strong>.</p>
    <table border="1" cellpadding="4" cellspacing="0" style="border-collapse:collapse;font-size:13px">
      <thead style="background:#0077b5;color:white">
        <tr>
          <th>Grupo</th><th>Keyword</th><th>Tipo</th><th>Nombre</th>
          <th>Cargo</th><th>Empresa</th><th>Lugar</th><th>Post</th><th>Encontrado</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
    </body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = smtp_user
    msg["To"]      = to_email
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, to_email, msg.as_string())
        logger.info(f"Email enviado a {to_email}")
    except Exception as e:
        logger.error(f"Error enviando email: {e}")


# ---------------------------------------------------------------------------
# Slack
# ---------------------------------------------------------------------------

def send_slack_alert(new_leads: List[Lead]):
    """Envía resumen a Slack via webhook."""
    webhook_url = os.getenv("SLACK_WEBHOOK_URL", "")
    if not webhook_url:
        logger.debug("Slack webhook no configurado. Saltando.")
        return

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"🔍 LinkedIn Researcher: {len(new_leads)} nuevos leads"}
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Fecha:* {datetime.now().strftime('%Y-%m-%d %H:%M')}"}
        },
        {"type": "divider"},
    ]

    # Mostrar hasta 10 leads en Slack
    for lead in new_leads[:10]:
        icon = "📢" if lead.search_type == "posts" else ("👤" if lead.search_type == "people" else "🏢")
        text = (
            f"{icon} *<{lead.profile_url}|{lead.name}>*\n"
            f">{lead.title}"
            + (f" · _{lead.company}_" if lead.company else "")
            + (f"\n>{lead.post_content[:150]}..." if lead.post_content else "")
        )
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": text}})

    if len(new_leads) > 10:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"_...y {len(new_leads)-10} más en el CSV_"}
        })

    try:
        resp = requests.post(webhook_url, json={"blocks": blocks}, timeout=10)
        if resp.status_code == 200:
            logger.info("Notificación Slack enviada.")
        else:
            logger.error(f"Slack error {resp.status_code}: {resp.text}")
    except Exception as e:
        logger.error(f"Error enviando a Slack: {e}")


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def notify(new_leads: List[Lead], total_saved: int):
    """Punto central de notificaciones."""
    if not new_leads:
        logger.info("Sin leads nuevos en esta ejecución.")
        return

    # 1. Consola
    print(f"\n{BOLD}{GREEN}✅ {len(new_leads)} NUEVOS LEADS ENCONTRADOS{RESET}\n")
    for i, lead in enumerate(new_leads):
        print_lead(lead, i)

    print_summary(new_leads, total_saved)

    # 2. Email (opcional)
    send_email_alert(new_leads)

    # 3. Slack (opcional)
    send_slack_alert(new_leads)
