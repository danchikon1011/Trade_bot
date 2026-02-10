import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import aiohttp


@dataclass
class OkxCredentials:
    api_key: str
    api_secret: str
    passphrase: str


class OkxRestClient:
    def __init__(self, creds: OkxCredentials, base_url: str, simulated: bool = True) -> None:
        self._creds = creds
        self._base_url = base_url.rstrip("/")
        self._simulated = simulated

    def _timestamp(self) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())

    def _sign(self, timestamp: str, method: str, path: str, body: str) -> str:
        message = f"{timestamp}{method}{path}{body}"
        mac = hmac.new(self._creds.api_secret.encode(), message.encode(), hashlib.sha256)
        return base64.b64encode(mac.digest()).decode()

    def _headers(self, timestamp: str, sign: str) -> Dict[str, str]:
        headers = {
            "OK-ACCESS-KEY": self._creds.api_key,
            "OK-ACCESS-SIGN": sign,
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": self._creds.passphrase,
            "Content-Type": "application/json",
        }
        if self._simulated:
            headers["x-simulated-trading"] = "1"
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        body = json.dumps(payload) if payload else ""
        timestamp = self._timestamp()
        sign = self._sign(timestamp, method, path, body)
        url = f"{self._base_url}{path}"
        headers = self._headers(timestamp, sign)
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, headers=headers, data=body) as response:
                data = await response.json()
                if response.status >= 400:
                    raise RuntimeError(f"HTTP {response.status}: {data}")
                return data

    async def get_balance(self, ccy: str = "USDT") -> Dict[str, Any]:
        return await self._request("GET", f"/api/v5/account/balance?ccy={ccy}")

    async def get_positions(self, inst_id: Optional[str] = None) -> Dict[str, Any]:
        path = "/api/v5/account/positions"
        if inst_id:
            path += f"?instId={inst_id}"
        return await self._request("GET", path)

    async def set_leverage(self, inst_id: str, lever: int, mgn_mode: str = "cross") -> Dict[str, Any]:
        payload = {"instId": inst_id, "lever": str(lever), "mgnMode": mgn_mode}
        return await self._request("POST", "/api/v5/account/set-leverage", payload)

    async def place_order(
        self,
        inst_id: str,
        side: str,
        ord_type: str,
        sz: str,
        td_mode: str = "cross",
        px: Optional[str] = None,
        reduce_only: Optional[bool] = None,
        cl_ord_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = {
            "instId": inst_id,
            "tdMode": td_mode,
            "side": side,
            "ordType": ord_type,
            "sz": sz,
        }
        if px is not None:
            payload["px"] = px
        if reduce_only is not None:
            payload["reduceOnly"] = reduce_only
        if cl_ord_id is not None:
            payload["clOrdId"] = cl_ord_id
        return await self._request("POST", "/api/v5/trade/order", payload)

    async def cancel_order(self, inst_id: str, ord_id: Optional[str] = None, cl_ord_id: Optional[str] = None) -> Dict[str, Any]:
        payload: Dict[str, str] = {"instId": inst_id}
        if ord_id:
            payload["ordId"] = ord_id
        if cl_ord_id:
            payload["clOrdId"] = cl_ord_id
        return await self._request("POST", "/api/v5/trade/cancel-order", payload)
