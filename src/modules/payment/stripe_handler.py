"""
Stripe webhook handler.

Configuração no painel Stripe:
  Developers → Webhooks → Add endpoint:
    https://bot-blofin.onrender.com/webhook/stripe
  Eventos a escutar:
    checkout.session.completed
    invoice.paid
    customer.subscription.deleted
    charge.refunded

Variáveis de ambiente necessárias:
  STRIPE_WEBHOOK_SECRET — começa com 'whsec_', gerado no painel Stripe

Como capturar o Telegram ID:
  No checkout Stripe, adicionar campo de texto customizado:
    metadata: { telegram_id: "123456789" }
  OU usar o campo de nome do produto com o ID.
"""
import hashlib
import hmac
import json
import logging
import os
import time
from typing import Optional

from .base import BasePaymentProvider, PaymentEvent

logger = logging.getLogger(__name__)

# Eventos que concedem acesso VIP
PURCHASE_EVENTS = {
    "checkout.session.completed",
    "invoice.paid",
    "customer.subscription.created",
    "customer.subscription.updated",
}

# Eventos que revogam acesso VIP
CANCEL_EVENTS = {
    "customer.subscription.deleted",
    "invoice.payment_failed",
    "charge.refunded",
    "charge.dispute.created",
}


class StripeProvider(BasePaymentProvider):

    def verify_signature(self, headers: dict, body: bytes) -> bool:
        secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
        if not secret:
            logger.warning("STRIPE_WEBHOOK_SECRET não configurado — pulando verificação")
            return True

        sig_header = (
            headers.get("Stripe-Signature")
            or headers.get("stripe-signature", "")
        )
        if not sig_header:
            logger.warning("Stripe: header de assinatura ausente")
            return False

        try:
            parts = {}
            for part in sig_header.split(","):
                k, v = part.split("=", 1)
                parts[k] = v

            timestamp = int(parts.get("t", 0))
            signature = parts.get("v1", "")

            # Rejeita webhooks com mais de 5 minutos (replay attack)
            if abs(time.time() - timestamp) > 300:
                logger.warning("Stripe: webhook expirado (replay attack?)")
                return False

            payload = f"{timestamp}.{body.decode('utf-8')}"
            expected = hmac.new(
                secret.encode("utf-8"),
                payload.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            valid = hmac.compare_digest(signature, expected)
            if not valid:
                logger.warning("Stripe: assinatura inválida")
            return valid
        except Exception as e:
            logger.error(f"Stripe: erro ao verificar assinatura — {e}")
            return False

    def parse_webhook(self, headers: dict, body: bytes) -> Optional[PaymentEvent]:
        try:
            data = json.loads(body)
        except Exception as e:
            logger.error(f"Stripe: JSON inválido — {e}")
            return None

        event_type = data.get("type", "")
        obj = data.get("data", {}).get("object", {})

        if not obj:
            return None

        # Extrai dados do comprador
        buyer_email = (
            obj.get("customer_email")
            or obj.get("email")
            or obj.get("customer_details", {}).get("email", "")
        )
        buyer_name = (
            obj.get("customer_details", {}).get("name")
            or obj.get("billing_details", {}).get("name", "")
        )

        # Telegram ID via metadata
        metadata = (
            obj.get("metadata", {})
            or obj.get("subscription_data", {}).get("metadata", {})
        )
        telegram_id = (
            metadata.get("telegram_id")
            or metadata.get("telegram_username")
            or metadata.get("telegram")
        )
        if telegram_id:
            telegram_id = str(telegram_id).lstrip("@")

        # Determina plano pelo intervalo de recorrência
        plan = "monthly"
        try:
            interval = (
                obj.get("plan", {}).get("interval")
                or obj.get("items", {}).get("data", [{}])[0]
                   .get("price", {}).get("recurring", {}).get("interval", "")
            )
            if interval == "year":
                plan = "annual"
        except (IndexError, AttributeError):
            pass

        # Valor (Stripe usa centavos)
        amount_cents = obj.get("amount_paid") or obj.get("amount") or 0
        amount = amount_cents / 100 if amount_cents else 0.0
        currency = (obj.get("currency") or "usd").upper()
        payment_id = obj.get("id", "")

        if event_type in PURCHASE_EVENTS:
            # Só processa checkout.session.completed se pagamento OK
            if event_type == "checkout.session.completed":
                if obj.get("payment_status") not in ("paid", "no_payment_required"):
                    logger.debug("Stripe: checkout não pago — ignorado")
                    return None

            logger.info(f"Stripe: COMPRA confirmada — {buyer_email} ({telegram_id}) plano={plan}")
            return PaymentEvent(
                event_type="purchase",
                platform="stripe",
                payment_id=payment_id,
                buyer_email=buyer_email,
                buyer_name=buyer_name or "",
                telegram_id=telegram_id,
                plan=plan,
                amount=amount,
                currency=currency,
                raw=data,
            )

        if event_type in CANCEL_EVENTS:
            logger.info(f"Stripe: CANCELAMENTO/REEMBOLSO — {buyer_email}")
            return PaymentEvent(
                event_type="refund",
                platform="stripe",
                payment_id=payment_id,
                buyer_email=buyer_email,
                buyer_name=buyer_name or "",
                telegram_id=telegram_id,
                plan=plan,
                amount=0.0,
                currency=currency,
                raw=data,
            )

        logger.debug(f"Stripe: evento '{event_type}' não mapeado — ignorado")
        return None
