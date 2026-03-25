"""
Hotmart webhook handler.

Configuração no painel Hotmart:
  Ferramentas → Webhooks → adicionar URL:
    https://bot-blofin.onrender.com/webhook/hotmart

Variáveis de ambiente necessárias:
  HOTMART_SECRET — token gerado no painel Hotmart (Webhooks → Segurança)

Campo personalizado no checkout (para capturar o Telegram ID):
  Nome do campo: "Seu usuário no Telegram (ex: @seuuser)"
  O bot lê o valor e vincula automaticamente ao VIP.
"""
import hashlib
import hmac
import json
import logging
import os
from typing import Optional

from .base import BasePaymentProvider, PaymentEvent

logger = logging.getLogger(__name__)

# Eventos que concedem acesso VIP
PURCHASE_EVENTS = {
    "PURCHASE_COMPLETE",
    "PURCHASE_APPROVED",
    "SUBSCRIPTION_REACTIVATED",
    "PURCHASE_BILLET_PRINTED",  # boleto gerado → acesso imediato (risco baixo)
}

# Eventos que revogam acesso VIP
CANCEL_EVENTS = {
    "PURCHASE_REFUNDED",
    "PURCHASE_CHARGEBACK",
    "SUBSCRIPTION_CANCELLATION",
    "PURCHASE_PROTEST",
    "PURCHASE_CANCELED",
}


class HotmartProvider(BasePaymentProvider):

    def verify_signature(self, headers: dict, body: bytes) -> bool:
        secret = os.getenv("HOTMART_SECRET", "")
        if not secret:
            logger.warning("HOTMART_SECRET não configurado — pulando verificação de assinatura")
            return True

        # Hotmart envia o token no header X-Hotmart-Webhook-Token
        sig = (
            headers.get("X-Hotmart-Webhook-Token")
            or headers.get("x-hotmart-webhook-token", "")
        )
        expected = hmac.new(secret.encode(), body, hashlib.sha1).hexdigest()
        valid = hmac.compare_digest(sig, expected)
        if not valid:
            logger.warning("Hotmart: assinatura inválida")
        return valid

    def parse_webhook(self, headers: dict, body: bytes) -> Optional[PaymentEvent]:
        try:
            data = json.loads(body)
        except Exception as e:
            logger.error(f"Hotmart: JSON inválido — {e}")
            return None

        event = data.get("event", "")
        purchase = data.get("data", {}).get("purchase", {})
        buyer = data.get("data", {}).get("buyer", {})
        subscription = data.get("data", {}).get("subscription", {})

        if not purchase:
            logger.debug(f"Hotmart: evento '{event}' sem dados de compra — ignorado")
            return None

        # Determina plano (mensal ou anual)
        plan = "monthly"
        recurrency = subscription.get("plan", {}).get("recurrency_period", "")
        if recurrency in ("YEARLY", "ANNUAL", "BIANNUAL"):
            plan = "annual"

        # Telegram ID via campos personalizados do checkout
        telegram_id = None
        for field in purchase.get("custom_fields", []):
            field_name = field.get("field_name", "").lower()
            if "telegram" in field_name or "usuario" in field_name:
                raw_value = str(field.get("field_value", "")).strip().lstrip("@")
                if raw_value:
                    telegram_id = raw_value
                    break

        buyer_email = buyer.get("email", "")
        buyer_name = buyer.get("name", "")
        payment_id = purchase.get("transaction", "")
        amount = purchase.get("price", {}).get("value", 0.0)
        currency = purchase.get("price", {}).get("currency_value", "BRL")

        if event in PURCHASE_EVENTS:
            logger.info(f"Hotmart: COMPRA confirmada — {buyer_email} ({telegram_id}) plano={plan}")
            return PaymentEvent(
                event_type="purchase",
                platform="hotmart",
                payment_id=payment_id,
                buyer_email=buyer_email,
                buyer_name=buyer_name,
                telegram_id=telegram_id,
                plan=plan,
                amount=float(amount),
                currency=currency,
                raw=data,
            )

        if event in CANCEL_EVENTS:
            logger.info(f"Hotmart: CANCELAMENTO/REEMBOLSO — {buyer_email}")
            return PaymentEvent(
                event_type="refund",
                platform="hotmart",
                payment_id=payment_id,
                buyer_email=buyer_email,
                buyer_name=buyer_name,
                telegram_id=telegram_id,
                plan=plan,
                amount=0.0,
                currency=currency,
                raw=data,
            )

        logger.debug(f"Hotmart: evento '{event}' não mapeado — ignorado")
        return None
