from typing import Optional
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class CallbackSchemaSettings(BaseModel):
    model_config = ConfigDict(extra="allow")


class GatewayCallbackSchema(CallbackSchemaSettings):
    id: str
    amount: Decimal | float
    currency: str
    status: str

    createdAt: Optional[str] = None
    recipientName: Optional[str] = None
    recipientAccountNumber: Optional[str] = None
    senderName: Optional[str] = None
    senderCountry: Optional[str] = None
    senderAccountNumber: Optional[str] = None
    externalPaymentId: Optional[str] = None
    externalCustomerId: Optional[str] = None
    returnUrl: Optional[str] = None
    failureReason: Optional[str] = None
    institutionId: Optional[str] = None
    description: Optional[str] = None
    sortId: Optional[str] = None
    finishedAt: Optional[str] = None
