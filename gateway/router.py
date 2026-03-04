from fastapi import APIRouter, Request

from schemas.payment import PaymentRequestSchema
from schemas.status import GatewayStatusSchema
from schemas.callback import GatewayCallbackSchema
from gateway.handler import (
    handle_pay,
    handle_status,
    handle_callback
)

router = APIRouter()


@router.post("/pay")
async def pay(data: PaymentRequestSchema):
    return await handle_pay(data)


@router.post("/status")
async def status(data: GatewayStatusSchema):
    return await handle_status(data)


@router.post("/callback")
async def callback(request: Request, data: GatewayCallbackSchema):
    raw_body = await request.body()
    return await handle_callback(data, raw_body, request)
