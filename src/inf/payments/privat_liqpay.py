import base64
import hashlib
import hmac
import json
import time
import urllib.parse
from src.domain.entities import PaymentWebhookResult


class PrivatLiqPayGateway:
    CHECKOUT_URL = "https://www.liqpay.ua/api/3/checkout"

    def __init__(
        self,
        public_key: str,
        private_key: str,
        webhook_base_url: str,
        sandbox: bool = True,
    ):
        self._public_key = public_key
        self._private_key = private_key
        self._webhook_url = f"{webhook_base_url.rstrip('/')}/api/webhooks/liqpay"
        self._sandbox = sandbox

    def _make_signature(self, data_b64: str) -> str:
        raw_string = f"{self._private_key}{data_b64}{self._private_key}"
        sha1_hash = hashlib.sha1(raw_string.encode("utf-8")).digest()
        return base64.b64encode(sha1_hash).decode("utf-8")

    def generate_checkout_url(
        self, booking_id: int, amount: int, description: str
    ) -> str:
        payload = {
            "version": 3,
            "public_key": self._public_key,
            "action": "pay",
            "amount": amount,
            "currency": "UAH",
            "description": description,
            "order_id": f"booking_{booking_id}_{int(time.time())}",
            "server_url": self._webhook_url,
        }
        if self._sandbox:
            payload["sandbox"] = 1

        json_bytes = json.dumps(payload).encode("utf-8")
        data_b64 = base64.b64encode(json_bytes).decode("utf-8")
        signature = self._make_signature(data_b64)

        query = urllib.parse.urlencode({"data": data_b64, "signature": signature})
        return f"{self.CHECKOUT_URL}?{query}"

    def parse_and_verify_webhook(
        self, data: str, signature: str
    ) -> PaymentWebhookResult:
        expected_sig = self._make_signature(data)
        if not hmac.compare_digest(expected_sig, signature):
            return PaymentWebhookResult(is_valid=False)

        try:
            decoded_bytes = base64.b64decode(data)
            payload = json.loads(decoded_bytes.decode("utf-8"))

            # order_id має формат "booking_{id}_{timestamp}"
            order_id_str: str = payload.get("order_id", "")
            parts = order_id_str.split("_")
            booking_id = int(parts[1]) if len(parts) >= 2 and parts[1].isdigit() else None

            return PaymentWebhookResult(
                is_valid=True,
                booking_id=booking_id,
                status=payload.get("status"),
                transaction_id=str(payload.get("payment_id", "")),
            )
        except Exception:
            return PaymentWebhookResult(is_valid=False)