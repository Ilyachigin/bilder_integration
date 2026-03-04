import time
import requests

from utils.logger import logger


def send_request(method: str, url: str, headers: dict, payload: dict | str  | bytes = None, callback=False) -> dict:
    start_time = time.perf_counter()

    logger.info(f"Gateway request URL: {url}")
    logger.info(f"Gateway request params: {payload}")
    logger.info(f"Gateway request headers: {headers}")

    try:
        if callback:
            for i in range(5):
                try:
                    response = requests.post(url, headers=headers, json=payload, timeout=10)
                    if response.ok:
                        break
                except requests.RequestException:
                    pass
                if i < 4:
                    time.sleep(2 ** i)

        if method == "POST":
            response = requests.post(url, headers=headers, data=payload, timeout=30)
        else:
            response = requests.get(url, headers=headers, timeout=30)
        logger.info(f"Gateway response: {response.text}")

        response.raise_for_status()
        result = {
            "status": "ok",
            "status_code": response.status_code,
            "response": response.json()
        }
    except requests.exceptions.HTTPError as http_err:
        result = {
            "status": "declined",
            "status_code": getattr(http_err.response, "status_code", None),
            "response": getattr(http_err.response, "text", None)
        }
    except requests.exceptions.RequestException as error:
        result = {
            "status": "declined",
            "status_code": response.status_code,
            "details": error
        }
    result["duration"] = round(time.perf_counter() - start_time, 4)

    return result

