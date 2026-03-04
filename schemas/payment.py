from pydantic import BaseModel, HttpUrl
from typing import Optional


class CustomerParams(BaseModel):
    email: str
    first_name: str
    country: str


class InnerParams(BaseModel):
    customer: CustomerParams


class PaymentInfo(BaseModel):
    token: str
    order_number: Optional[str] = None
    gateway_amount: int
    gateway_currency: str
    merchant_private_key: str


class SettingsInfo(BaseModel):
    sandbox: bool
    assets_private_key: str
    assets_public_key: str
    x_profile: str
    x_key: str
    x_user: str
    sign_key: str


class PaymentRequestSchema(BaseModel):
    params: Optional[InnerParams]
    payment: PaymentInfo
    settings: SettingsInfo
    processing_url: Optional[HttpUrl]
