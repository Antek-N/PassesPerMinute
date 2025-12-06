import logging
import random
import time
from typing import Any

import requests
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger(__name__)

_session = None


def _get_session() -> Session:
    """
    Create (or return an existing) configured HTTP session with retries and connection pooling.

    The session is cached globally to reuse connections efficiently.
    Retries are applied for transient errors such as 429 (Too Many Requests) and 5xx server errors.

    :return: A configured `requests.Session` object with retry strategy and connection pooling.
    """
    global _session
    if _session is None:
        log.info("Creating HTTP session")  # Log start
        s = requests.Session()

        # Configure retry strategy
        retries = Retry(
            total=6,
            connect=3,
            read=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods={"GET"},
            raise_on_status=False,
        )

        # Attach adapter with retry and connection pooling
        adapter = HTTPAdapter(max_retries=retries, pool_connections=100, pool_maxsize=100)
        s.mount("https://", adapter)

        _session = s
        log.info("HTTP session ready with retries and pooling")  # Log success

    return _session


def get_json(
    url: str,
    timeout: float | tuple[float, float] = (5, 30),
    max_attempts: int = 5,
) -> Any:
    """
    Fetch JSON data from a given URL with retry logic and exponential backoff.

    :param url: The HTTP(S) URL to fetch JSON from.
    :param timeout: Timeout for the request in seconds.
                    Can be a single float (applies to both connect and read),
                    or a tuple (connect timeout, read timeout).
    :param max_attempts: Maximum number of retry attempts before failing.
    :return: Parsed JSON data from the response if successful.
    :raises requests.exceptions.RequestException: If all retry attempts fail.
    """
    s = _get_session()
    last_exc = None
    for attempt in range(1, max_attempts + 1):
        try:
            # Send GET request with timeout
            log.info(f"HTTP GET {url} attempt={attempt} timeout={timeout}")  # Log start
            req = s.get(url, timeout=timeout, stream=False)
            req.raise_for_status()  # raise error if status is 4xx/5xx
            log.info(f"HTTP GET ok {url} status={req.status_code} attempt={attempt}")  # Log success
            return req.json()  # parse and return JSON if success
        except (
            requests.exceptions.ChunkedEncodingError,
            requests.exceptions.ConnectionError,
            requests.exceptions.ReadTimeout,
            requests.exceptions.HTTPError,
        ) as e:
            last_exc = e
            log.warning(f"HTTP GET failed {url} attempt={attempt} error={e}")  # Log retry
            # Wait before retry. Expotential backoff / jitter / max time 5s
            time.sleep(min((2**attempt) * 0.25 + random.random() * 0.25, 5))

    log.error(f"HTTP GET giving up {url} attempts={max_attempts} last_error={last_exc}")  # Log failure

    if last_exc is not None:
        raise RuntimeError(f"HTTP GET failed after {max_attempts} attempts") from last_exc
    else:
        raise RuntimeError(f"HTTP GET failed after {max_attempts} attempts")
