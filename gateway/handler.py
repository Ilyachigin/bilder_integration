from fastapi import Response, Request
from fastapi.responses import JSONResponse

import config
from client.http import send_request
from schemas.payment import PaymentRequestSchema
from schemas.callback import GatewayCallbackSchema
from schemas.status import GatewayStatusSchema
from utils.logger import logger
from gateway.builder import (
    db,
    base_url,
    GatewayRequestContext,
    gateway_body,
    gateway_callback_body,
    headers_param,
    database_insert,
    response_handler,
    callback_jwt,
    gateway_status_body,
    verify_gateway_callback
)


async def handle_pay(data: PaymentRequestSchema):
    raw_data = data.model_dump(mode="json", exclude_none=True)
    logger.info(f"Business request body: {raw_data}")

    contexts: list[GatewayRequestContext] = []

    settings = raw_data.get("settings", {})
    public_key = settings.get("assets_public_key")
    merchant_token = raw_data.get("payment", {}).get("merchant_private_key")

    gateway_payload = gateway_body(raw_data)

    sandbox = base_url(settings.get('sandbox', False))
    url = f"{sandbox}/api/v1/payments"
    headers = headers_param(settings=settings, body=gateway_payload)

    response = send_request('POST', url, headers, gateway_payload)

    response_body = response.get('response', {})
    if isinstance(response_body, dict) and response_body.get("status") == "SUCCESS":
        database_insert(response_body, merchant_token, public_key)

    contexts.append(
        GatewayRequestContext(
            request_type="pay",
            request_url=url,
            request_data=gateway_payload,
            response_data=response,
            duration=response["duration"]
        )
    )

    return response_handler(contexts)


async def handle_status(data: GatewayStatusSchema):
    raw_data = data.model_dump(mode="json", exclude_none=True)
    logger.info(f"Business request body: {raw_data}")

    contexts: list[GatewayRequestContext] = []

    settings = raw_data.get("settings", {})

    gateway_token = gateway_status_body(raw_data)

    sandbox = base_url(settings.get('sandbox', False))
    url = f"{sandbox}/api/v1/payments/{gateway_token}"
    headers = headers_param(settings=settings, status=True)

    response = send_request('GET', url, headers)

    contexts.append(
        GatewayRequestContext(
            request_type="status",
            request_url=url,
            request_data=gateway_token,
            response_data=response,
            duration=response["duration"]
        )
    )

    return response_handler(contexts)


async def handle_callback(data: GatewayCallbackSchema, raw_body: bytes, request: Request):
    raw_data = data.model_dump(exclude_none=True)
    logger.info(f"Gateway callback body: {raw_data}")

    payment_id = raw_data.get("id")
    merchant_token, public_key = db.get_token(payment_id)

    gateway_signature = request.headers.get("X-Signature")

    if public_key is None or merchant_token is None:
        logger.info("Transaction token not found")
        return Response(content="ok", status_code=200)

    if verify_gateway_callback(raw_body, gateway_signature, public_key):
        gateway_token, callback_body = gateway_callback_body(raw_data)
        jwt_token = callback_jwt(callback_body, merchant_token)

        url = f"{config.BUSINESS_URL}/callbacks/v2/gateway_callbacks/{gateway_token}"
        headers = headers_param(jwt_token=jwt_token)

        send_request('POST', url, headers, callback_body, callback=True)
    else:
        logger.info(f"Transaction token not found")

    return JSONResponse(content={"code": 0}, status_code=200)

