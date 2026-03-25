"""
Mercado Pago webhook handler.

Configuração no painel Mercado Pago:
  Suas integrações → Webhooks → Configurar notificações:
    URL: https://bot-blofin.onrender.com/webhook/mercadopago
    Eventos: Pagamentos

Variáveis de ambiente necessárias:
  MERCADOPAGO_ACCESS_TOKEN — token de acesso da sua conta MP
  MERCADOPAGO_SECRET — (opcional) para verificar assinatura do webhook

Como vincular ao Telegram ID:
  Ao criar a preferência de pagamento, adicione:
    external_reference = f"tg_{telegram_id}"
  Exemplo:
    preference_data = {
        "items": [...],
        "external_reference": f"tg_{telegram_id}",
        "payer": {"email": buyer_email},
    }
"""
import hashlib
import hmac
import json
import logging
import os
from typing import Optional

from .base import BasePaymentProvider, PaymentEvent

logger = logging.getLogger(__name__)

# Status de pagamento aprovado no MP
APPROVED_STATUSES = {"approved", "authorized"}


class MercadoPagoProvider(BasePaymentProvider):

    def verify_signature(self, headers: dict, body: bytes) -> bool:
        secret = os.getenv("MERCADOPAGO_SECRET", "")
        if not secret:
            # MP pode enviar sem secret em ambiente de testes
            return True

        # MP usa header x-signature com formato: ts=<timestamp>,v1=<hash>
        sig_header = headers.get("x-signature") or headers.get("X-Signature", "")
        if not sig_header:
            return True  # permite sem signature (compatibilidade)

        try:
            parts = {}
            for part in sig_header.split(","):
                k, v = part.split("=", 1)
                parts[k.strip()] = v.strip()

            ts = parts.get("ts", "")
            v1 = parts.get("v1", "")

            manifest = f"id:{headers.get('x-request-id','')};request-id:{headers.get('x-request-id','')};ts:{ts};"
            expected = hmac.new(
                secret.encode(), manifest.encode(), hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(v1, expected)
        except Exception as e:
            logger.warning(f"MercadoPago: erro ao verificar assinatura — {e}")
            return True  # não bloqueia se der erro na verificação

    def parse_webhook(self, headers: dict, body: bytes) -> Optional[PaymentEvent]:
        try:
            data = json.loads(body)
        except Exception as e:
            logger.error(f"MercadoPago: JSON inválido — {e}")
            return None

        topic = data.get("type") or data.get("topic", "")
        action = data.get("action", "")

        if topic != "payment":
            logger.debug(f"MercadoPago: tópico '{topic}' — ignorado")
            return None

        # O webhook do MP envia apenas o ID — os dados reais ficam no objeto data
        resource_data = data.get("data", {})
        status = resource_data.get("status", "")
        payment_id = str(resource_data.get("id", ""))
        external_ref = resource_data.get("external_reference", "")

        payer = resource_data.get("payer", {})
        buyer_email = payer.get("email", "")
        first_name = payer.get("first_name", "")
        last_name = payer.get("last_name", "")
        buyer_name = f"{first_name} {last_name}".strip()

        # Extrai Telegram ID do external_reference (formato: tg_<id>)
        telegram_id = None
        if external_ref.startswith("tg_"):
            telegram_id = external_ref[3:].strip()

        amount = float(resource_data.get("transaction_amount") or 0)
        currency = resource_data.get("currency_id", "BRL")

        # Determina plano pelo valor (heurística — ajustar conforme seus preços)
        plan = "monthly"
        if amount >= 900:  # R$96 × 12 = R$1152, arredondado
            plan = "annual"

        if status in APPROVED_STATUSES:
            logger.info(f"MercadoPago: PAGAMENTO aprovado — {buyer_email} ({telegram_id}) plano={plan}")
            return PaymentEvent(
                event_type="purchase",
                platform="mercadopago",
                payment_id=payment_id,
                buyer_email=buyer_email,
                buyer_name=buyer_name,
                telegram_id=telegram_id,
                plan=plan,
                amount=amount,
                currency=currency,
                raw=data,
            )

        if status in ("refunded", "charged_back", "cancelled"):
            logger.info(f"MercadoPago: CANCELAMENTO/REEMBOLSO — {buyer_email}")
            return PaymentEvent(
                event_type="refund",
                platform="mercadopago",
                payment_id=payment_id,
                buyer_email=buyer_email,
                buyer_name=buyer_name,
                telegram_id=telegram_id,
                plan=plan,
                amount=0.0,
                currency=currency,
                raw=data,
            )

        logger.debug(f"MercadoPago: status '{status}' — ignorado")
        return None
