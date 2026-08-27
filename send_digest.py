#!/usr/bin/env python3
"""Dispara o resumo diário por e-mail. Pensado para rodar via cron/launchd.

Uso: python3 send_digest.py
(as variáveis de ambiente de SMTP precisam estar definidas — veja automations.py)
"""
from automations import send_digest_email

if __name__ == "__main__":
    result = send_digest_email()
    if result["ok"]:
        print(f"Resumo enviado para {', '.join(result['recipients'])} ({result['total']} pendências).")
    else:
        print(f"Não enviado: {result['reason']}")
