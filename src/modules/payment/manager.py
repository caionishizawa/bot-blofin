"""
PaymentManager — orquestra provedores e libera/revoga acesso VIP.

Fluxo completo:
  Checkout → Plataforma (Hotmart/Stripe/MP) → Webhook →
  dashboard.py /webhook/<platform> → PaymentManager.process_event() →
  DB.add_subscriber() + Telegram notifica assinante
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from .base import PaymentEvent
from .hotmart import HotmartProvider
from .stripe_handler import StripeProvider
from .mercadopago_handler import MercadoPagoProvider

logger = logging.getLogger(__name__)

# Duração de cada plano em dias
PLAN_DURATIONS: dict[str, int] = {
    "monthly": 31,
    "annual": 366,
}


class PaymentManager:
    """
    Centraliza o processamento de eventos de pagamento de todas as plataformas.
    Instanciado uma vez no bot.py e injetado no dashboard.py.
    """

    def __init__(self, db, bot_app=None):
        """
        db       — instância de PerformanceDB (já inicializado)
        bot_app  — instância de telegram.ext.Application (para enviar mensagens)
        """
        self._db = db
        self._bot_app = bot_app
        self._providers = {
            "hotmart":      HotmartProvider(),
            "stripe":       StripeProvider(),
            "mercadopago":  MercadoPagoProvider(),
        }

    def set_bot_app(self, bot_app) -> None:
        """Permite injetar o bot_app após a criação (evita circular import)."""
        self._bot_app = bot_app

    def get_provider(self, platform: str):
        """Retorna o provedor para a plataforma solicitada."""
        return self._providers.get(platform)

    # ──────────────────────────────────────────────
    # Processamento de eventos
    # ──────────────────────────────────────────────

    async def process_event(self, event: PaymentEvent) -> None:
        """Ponto de entrada principal — chame após parse_webhook()."""
        if event.event_type == "purchase":
            await self._handle_purchase(event)
        elif event.event_type in ("refund", "chargeback", "cancel"):
            await self._handle_refund(event)
        else:
            logger.debug(f"PaymentManager: event_type '{event.event_type}' ignorado")

    async def _handle_purchase(self, event: PaymentEvent) -> None:
        duration = PLAN_DURATIONS.get(event.plan, 31)
        expires_at = (datetime.utcnow() + timedelta(days=duration)).isoformat()

        await self._db.add_subscriber(
            email=event.buyer_email,
            name=event.buyer_name,
            telegram_id=event.telegram_id,
            plan=event.plan,
            expires_at=expires_at,
            platform=event.platform,
            payment_id=event.payment_id,
        )

        logger.info(
            f"VIP LIBERADO: {event.buyer_email} | telegram={event.telegram_id} | "
            f"plano={event.plan} | plataforma={event.platform} | expira={expires_at[:10]}"
        )

        await self._notify_welcome(event, expires_at[:10])

    async def _handle_refund(self, event: PaymentEvent) -> None:
        await self._db.revoke_subscriber(
            email=event.buyer_email,
            payment_id=event.payment_id,
        )

        logger.info(
            f"VIP REVOGADO: {event.buyer_email} | payment_id={event.payment_id} | "
            f"plataforma={event.platform}"
        )

        await self._notify_revoked(event)

    # ──────────────────────────────────────────────
    # Notificações Telegram
    # ──────────────────────────────────────────────

    async def _notify_welcome(self, event: PaymentEvent, expires_date: str) -> None:
        """Envia mensagem de boas-vindas VIP ao assinante."""
        if not event.telegram_id or not self._bot_app:
            return

        first_name = (event.buyer_name or "trader").split()[0]
        platform_display = {
            "hotmart": "Hotmart",
            "stripe": "Stripe",
            "mercadopago": "Mercado Pago",
            "manual": "Admin",
        }.get(event.platform, event.platform.capitalize())

        msg = (
            f"✅ *Pagamento confirmado via {platform_display}!*\n\n"
            f"Bem-vindo ao VIP, *{first_name}*! 🎉\n\n"
            f"Você agora tem acesso completo ao *Sid Quantt*:\n"
            f"• Sinais completos: Entry, SL e TP *antes* do trade\n"
            f"• Análise completa por IA em PT-BR\n"
            f"• Chat ilimitado com o agente educacional\n"
            f"• Dashboard pessoal de performance\n\n"
            f"📅 Acesso válido até: `{expires_date}`\n\n"
            f"Use /start para ver todos os comandos disponíveis.\n"
            f"Use /minhaconta para ver seu status de assinatura a qualquer momento."
        )

        try:
            await self._bot_app.bot.send_message(
                chat_id=int(event.telegram_id),
                text=msg,
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.warning(
                f"Não consegui notificar telegram_id={event.telegram_id}: {e}\n"
                f"Ação necessária: admin deve enviar o VIP manualmente via /addvip {event.telegram_id}"
            )

    async def _notify_revoked(self, event: PaymentEvent) -> None:
        """Notifica o usuário que seu acesso VIP foi revogado."""
        if not event.telegram_id or not self._bot_app:
            return

        msg = (
            "⚠️ *Acesso VIP encerrado*\n\n"
            "Seu acesso ao Sid Quantt VIP foi cancelado devido a "
            "reembolso, estorno ou cancelamento da assinatura.\n\n"
            "Para renovar, assine novamente em nosso canal."
        )

        try:
            await self._bot_app.bot.send_message(
                chat_id=int(event.telegram_id),
                text=msg,
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.warning(f"Não consegui notificar revogação para {event.telegram_id}: {e}")
