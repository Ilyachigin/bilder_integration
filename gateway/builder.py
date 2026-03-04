import json

import jwt
import base64
from typing import Dict, Any
from datetime import datetime
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

import config
from utils.db import DatabaseStorage


db = DatabaseStorage()


@dataclass
class GatewayRequestContext:
    request_type: str
    request_url: str
    request_data: Dict[str, Any] | str | bytes
    response_data: Dict[str, Any] | str
    duration: float
    refund: bool = False


def gateway_body(business_data: Dict) -> bytes:
    params = business_data.get("params")

    main_dict = main_params(business_data)
    customer_dict = customer_params(params)

    gateway_payload = {
        **main_dict,
        **customer_dict
    }
    return json.dumps(gateway_payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def gateway_status_body(business_data: Dict) -> str:
    payment = business_data.get("payment", {})

    return payment.get("gateway_token")


def gateway_callback_body(data: dict) -> tuple:
    gateway_currency = data.get("currency")
    gateway_amount = data.get("amount")
    token = data.get("id")

    gateway_status = status_mapping(data.get("status"))
    details = data.get("failureReason") or f"Transaction is {gateway_status}"

    context = [
        GatewayRequestContext(
            request_type="callback",
            request_url=f"{config.BUSINESS_URL}/callbacks/v2/gateway_callbacks/{token}",
            request_data=data,
            response_data={},
            duration=0.1
        )
    ]

    callback_body = {
        "status": gateway_status,
        "reason": details,
        "currency": gateway_currency,
        "amount": amount_convert(gateway_amount, reverse=True),
        "logs": response_logs_params(context)
    }

    return token, callback_body


def gateway_pay_response(contexts: list[GatewayRequestContext]) -> Dict:
    main_context = find_request(contexts)

    gateway_response = main_context.response_data.get("response", {})
    gateway_payload = gateway_response.get("payload", {})

    processing_url = gateway_payload.get("redirectUrl", {})
    token = gateway_payload.get("paymentId")

    return {
        "result": "OK",
        "status": "pending",
        "gateway_token": token,
        "processing_url": processing_url,
        "redirect_request": response_redirect_params(processing_url),
        "logs": response_logs_params(contexts)
    }


def gateway_status_response(contexts: list[GatewayRequestContext]) -> Dict:
    main_context = find_request(contexts)

    gateway_response = main_context.response_data.get("response", {})
    gateway_payload = gateway_response.get("payload", {})

    transaction_status = status_mapping(gateway_payload.get("status"))
    details = gateway_payload.get("failureReason") or f"Transaction is {transaction_status}"

    gateway_currency = gateway_payload.get("currency")
    gateway_amount = gateway_payload.get("amount")

    result = {
        "result": "OK",
        "amount": amount_convert(gateway_amount, reverse=True),
        "currency": gateway_currency,
        "details": details,
        "status": transaction_status,
        "logs": response_logs_params(contexts)
    }

    return result


def gateway_declined_response(contexts: list[GatewayRequestContext]) -> Dict:
    main_context = find_request(contexts)

    gateway_response = main_context.response_data.get("response")

    if not isinstance(gateway_response, dict):
        declination_reason = "Transaction declined"
    else:
        declination_reason = gateway_response.get("payload", {}).get("description")

    return {
        "result": False,
        "status": "declined",
        "details": declination_reason,
        "logs": response_logs_params(contexts)
    }


def response_handler(contexts: list[GatewayRequestContext]) -> dict | None:
    main_context = find_request(contexts)
    response = main_context.response_data

    gateway_response = response.get("response", {})

    if response.get("status") == "ok" and gateway_response.get("payload"):
        if main_context.request_type == "pay":
            return gateway_pay_response(contexts)
        elif main_context.request_type == "status":
            return gateway_status_response(contexts)
        return None
    else:
        return gateway_declined_response(contexts)


def customer_params(data: dict) -> Dict:
    customer = data.get("customer")

    params = {
        "externalCustomerId": customer.get("email"),
        "senderCountry": customer.get("country"),
        "senderName": customer.get("first_name")
    }
    return clean_data(params)


def main_params(business_data: dict) -> Dict:
    payment_params = business_data.get("payment", {})

    params = {
        "amount": amount_convert(payment_params.get("gateway_amount")),
        "currency": payment_params.get("gateway_currency"),
        "externalPaymentId": payment_params.get("token"),
        "returnUrl": business_data.get("processing_url")
    }
    return clean_data(params)


def response_redirect_params(redirect_url: str) -> Dict:
    redirect_type = "get_with_processing"

    return {
        "url": redirect_url,
        "type": "post_iframes" if redirect_type == "post" else redirect_type,
        "param": "{}"
    }


def response_logs_params(contexts: list[GatewayRequestContext]) -> list:
    logs_list = []

    for context in contexts:
        gateway_log = {
            "gateway": "bilder",
            "request": {
                "url": context.request_url,
                "params": context.request_data
            },
            "status": context.response_data.get("status_code") or "200",
            "response": context.response_data,
            "kind": context.request_type,
            "created_at": datetime.now().isoformat(),
            "duration": context.duration
        }
        logs_list.append(gateway_log)

    return logs_list


def status_mapping(status: str) -> str:
    approved_status = "approved"
    declined_status = "declined"

    mapping = {
        "CONFIRMED": approved_status,
        "CANCELED": declined_status,
        "FAILED": declined_status,
        "EXPIRED": declined_status
    }

    return mapping.get(status, "pending")


def callback_jwt(callback_body: dict, merchant_token: str) -> str:
    sign_key = config.SIGN_KEY
    secure_data = merchant_token_encrypt(merchant_token, sign_key)

    return jwt.encode(
        payload={**callback_body, "secure": secure_data},
        key=sign_key,
        algorithm="HS512"
    )


def merchant_token_encrypt(merchant_token: str, sign_key: str) -> dict:
    def pad(data: bytes) -> bytes:
        pad_len = 16 - (len(data) % 16)
        return data + bytes([pad_len] * pad_len)

    key = sign_key.encode('utf-8')[:32]
    iv = get_random_bytes(16)

    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded_data = pad(merchant_token.encode('utf-8'))
    encrypted = cipher.encrypt(padded_data)

    return {
        "encrypted_data": base64.b64encode(encrypted).decode('utf-8'),
        "iv_value": base64.b64encode(iv).decode('utf-8')
    }


def headers_param(settings: dict = None, body: bytes = None, jwt_token: str = None, status=False) -> dict:
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json;charset=UTF-8"
    }
    if jwt_token:
        headers["Authorization"] = f"Bearer {jwt_token}"
    else:
        headers["X-Profile"] = settings.get('x_profile')
        headers["X-User"] = settings.get('x_user')

        if status:
            headers["X-Token"] = settings.get('x_token')
        else:
            headers["X-Key-Id"] = settings.get('x_key')
            headers["X-Signature"] = gateway_signature(body, settings.get('assets_private_key'))

    return headers


def database_insert(data: dict, bearer_token: str, public_key: str):
    payload_data = data.get("payload", {})
    token = payload_data.get("paymentId")

    if token:
        db.insert_token(token, bearer_token, public_key)
        db.delete_old_tokens()


def clean_data(params: dict) -> dict:
    return {k: v for k, v in params.items() if v is not None and v != ""}


def amount_convert(value, reverse: bool = False, exponent: int = 2) -> int | float:
    factor = Decimal(10) ** exponent

    if not reverse:
        amount = (Decimal(value) / factor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return int(amount) if amount == amount.to_integral_value() else float(amount)

    return int((Decimal(str(value)) * factor).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def find_request(contexts: list[GatewayRequestContext]) -> GatewayRequestContext:
    return next(
        (c for c in reversed(contexts) if c.request_type in {"pay", "status"}),
        None
    )


def verify_gateway_callback(body: bytes, signature: str, public_key_pem: str) -> bool:
    try:
        decoded_key = base64.b64decode(public_key_pem)
        public_key = serialization.load_pem_public_key(decoded_key)

        signature_bytes = base64.b64decode(signature)

        public_key.verify(
            signature_bytes,
            body,
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        return True
    except (ValueError, InvalidSignature, TypeError):
        return False


def base_url(sandbox: bool) -> str:
    if sandbox:
        return config.GATEWAY_SANDBOX_URL
    return config.GATEWAY_URL


def gateway_signature(body: bytes, private_key_pem: str) -> str:
    decoded_key = base64.b64decode(private_key_pem)

    private_key = serialization.load_pem_private_key(
        decoded_key,
        password=None
    )

    signature_bytes = private_key.sign(
        body,
        padding.PKCS1v15(),
        hashes.SHA256()
    )

    return base64.b64encode(signature_bytes).decode("ascii")

