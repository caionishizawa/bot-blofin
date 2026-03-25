"""
Base interface para provedores de pagamento.
Cada provedor (Hotmart, Stripe, MercadoPago) implementa esta interface.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PaymentEvent:
    """Evento de pagamento normalizado — igual para todos os provedores."""
    event_type: str       # 'purchase' | 'refund' | 'chargeback' | 'cancel'
    platform: str         # 'hotmart' | 'stripe' | 'mercadopago' | 'manual'
    payment_id: str       # ID único na plataforma
    buyer_email: str
    buyer_name: str
    telegram_id: Optional[str]   # preenchido no checkout via campo custom
    plan: str             # 'monthly' | 'annual'
    amount: float
    currency: str         # 'BRL' | 'USD'
    raw: dict = field(default_factory=dict)  # payload original


class BasePaymentProvider(ABC):
    """Classe base para todos os provedores de pagamento."""

    @abstractmethod
    def verify_signature(self, headers: dict, body: bytes) -> bool:
        """
        Verifica a assinatura do webhook para garantir autenticidade.
        Retorna True se válido, False caso contrário.
        Se a variável de secret não estiver configurada, retorna True (skip).
        """
        pass

    @abstractmethod
    def parse_webhook(self, headers: dict, body: bytes) -> Optional[PaymentEvent]:
        """
        Faz parse do payload do webhook e retorna um PaymentEvent normalizado.
        Retorna None se o evento não for relevante (ex: eventos de marketing, teste).
        """
        pass
