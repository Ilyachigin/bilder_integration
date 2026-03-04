from pydantic import BaseModel
from typing import Dict, Any, Union


class StatusParams(BaseModel):
    gateway_token: str


class SettingsInfo(BaseModel):
    sandbox: bool
    assets_private_key: str
    assets_public_key: str
    x_profile: str
    x_key: str
    x_user: str
    x_token: str
    sign_key: str


class GatewayStatusSchema(BaseModel):
    settings: SettingsInfo
    payment: StatusParams
    method_name: str
