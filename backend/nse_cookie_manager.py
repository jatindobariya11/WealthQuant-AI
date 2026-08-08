import json
import logging
import os
import time

from curl_cffi import CurlHttpVersion, requests
from selenium import webdriver
from selenium.webdriver.edge.options import Options as EdgeOptions

logger = logging.getLogger("nse_cookie_manager")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    ch.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    logger.addHandler(ch)

COOKIE_FILE = os.path.join(os.path.dirname(__file__), "nse_cookies.json")


def load_cookies() -> dict:
    """Loads cookies from cached JSON file. Proactively discards if older than 45 minutes."""
    if os.path.exists(COOKIE_FILE):
        try:
            mtime = os.path.getmtime(COOKIE_FILE)
            age = time.time() - mtime
            if age > 2700:  # 45 minutes
                logger.info(
                    f"Cached cookies are {age / 60:.1f} minutes old (expired). Forcing refresh..."
                )
                return {}
            with open(COOKIE_FILE) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to read cookie file: {e}")
    return {}


def save_cookies(cookies: dict):
    """Saves cookies to cache file."""
    try:
        with open(COOKIE_FILE, "w") as f:
            json.dump(cookies, f, indent=4)
        logger.info(f"Saved fresh cookies to {COOKIE_FILE}")
    except (OSError, ValueError, TypeError) as e:
        logger.error(f"Failed to save cookies: {e}")


def refresh_cookies() -> dict:
    """Launches Microsoft Edge to solve the Akamai challenge and extract valid cookies."""
    logger.info("Launching Edge in headed mode to refresh NSE cookies...")
    options = EdgeOptions()
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Edge(options=options)
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        },
    )

    try:
        url = "https://www.nseindia.com/option-chain?symbol=NIFTY"
        logger.info(f"Navigating browser to: {url}")
        driver.get(url)

        logger.info(
            "Waiting 3 seconds for Akamai challenge to solve (reduced for 5s timeout)..."
        )
        time.sleep(3)

        selenium_cookies = driver.get_cookies()
        cookies = {}
        for c in selenium_cookies:
            if "nseindia.com" in c.get("domain", ""):
                cookies[c["name"]] = c["value"]

        if cookies:
            save_cookies(cookies)
            return cookies
        else:
            logger.error("No nseindia.com cookies found in browser session.")
    except (OSError, RuntimeError, ConnectionError, TypeError) as e:
        logger.error(f"Error during browser session cookie refresh: {e}")
    finally:
        driver.quit()
    return {}


async def async_fetch_option_chain_api(symbol: str, type_val: str = None) -> dict:
    """Async wrapper that offloads synchronous cookie management and HTTP requests to threadpool."""
    import asyncio

    from core.thread_pools import nse_pool

    loop = asyncio.get_running_loop()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(nse_pool, fetch_option_chain_api, symbol, type_val),
            timeout=8.0,
        )
    except asyncio.TimeoutError:
        logger.error(f"NSE Option Chain fetch timed out for {symbol} after 8.0s")
        return {}
    except (OSError, RuntimeError, ConnectionError, ValueError, TypeError) as e:
        logger.error(f"NSE Option Chain fetch failed for {symbol}: {e}")
        return {}


def fetch_option_chain_api(symbol: str, type_val: str = None) -> dict:
    """
    Fetches option chain using cached cookies.
    Automatically refreshes cookies and retries if request is blocked or times out.
    """
    symbol_upper = symbol.upper()

    # 1. Determine type (Indices vs Equity)
    if type_val is None:
        indices = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50"]
        type_val = "Indices" if symbol_upper in indices else "Equity"

    cookies = load_cookies()
    headers = {
        "Host": "www.nseindia.com",
        "sec-ch-ua": '"Microsoft Edge";v="129", "Not=A?Brand";v="8", "Chromium";v="129"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "accept": "application/json, text/plain, */*",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "referer": f"https://www.nseindia.com/option-chain?symbol={symbol_upper}",
        "accept-language": "en-US,en;q=0.9,en-IN;q=0.8,en-GB;q=0.7",
        "accept-encoding": "gzip, deflate, br",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0",
    }

    # Helper function for the actual GET requests
    def attempt_fetch(retry_on_expired=True) -> dict:
        nonlocal cookies
        if not cookies:
            try:
                from core.thread_pools import playwright_pool

                future = playwright_pool.submit(refresh_cookies)
                cookies = future.result(timeout=5.0)
            except (RuntimeError, TimeoutError, OSError, ConnectionError) as e:
                logger.error(f"Playwright refresh_cookies timed out or failed: {e}")
                cookies = {}
            if not cookies:
                raise ValueError("Failed to obtain valid cookies.")

        # Step A: Get Contract Info first (to get active expiry list)
        contract_url = f"https://www.nseindia.com/api/option-chain-contract-info?symbol={symbol_upper}"
        logger.info(f"Step A: Fetching contract info for {symbol_upper}...")
        try:
            r_contract = requests.get(
                contract_url,
                headers=headers,
                cookies=cookies,
                impersonate="chrome120",
                http_version=CurlHttpVersion.V1_1,
                timeout=3.0,  # Tight timeout to bypass tarpits
            )

            # If blocked (200 with empty body, or 401/403)
            if r_contract.status_code != 200 or r_contract.text.strip() == "{}":
                raise requests.exceptions.RequestException("Blocked or empty response")
        except (requests.exceptions.RequestException, ValueError, OSError) as e:
            if retry_on_expired:
                logger.info(
                    f"Contract Info fetch failed or timed out ({e}). Refreshing cookies..."
                )
                try:
                    from core.thread_pools import playwright_pool

                    cookies = playwright_pool.submit(refresh_cookies).result(
                        timeout=5.0
                    )
                except (RuntimeError, TimeoutError, OSError):
                    cookies = {}
                return attempt_fetch(retry_on_expired=False)
            else:
                raise ValueError(
                    f"NSE API blocked request even after refreshing cookies: {e}"
                )

        contract_data = r_contract.json()
        expiry_dates = contract_data.get("expiryDates", [])
        if not expiry_dates:
            raise ValueError(
                f"No expiry dates found in contract info response for {symbol_upper}"
            )

        first_expiry = expiry_dates[0]
        logger.info(
            f"Found active expiries. Fetching option chain for next expiry: {first_expiry}"
        )

        # Step B: Get Option Chain for that expiry
        chain_url = f"https://www.nseindia.com/api/option-chain-v3?type={type_val}&symbol={symbol_upper}&expiry={first_expiry}"
        try:
            r_chain = requests.get(
                chain_url,
                headers=headers,
                cookies=cookies,
                impersonate="chrome120",
                http_version=CurlHttpVersion.V1_1,
                timeout=3.0,
            )

            if r_chain.status_code != 200 or r_chain.text.strip() == "{}":
                raise requests.exceptions.RequestException("Blocked or empty response")
        except (requests.exceptions.RequestException, ValueError, OSError) as e:
            if retry_on_expired:
                logger.info(
                    f"Option Chain fetch failed or timed out ({e}). Refreshing cookies..."
                )
                try:
                    from core.thread_pools import playwright_pool

                    cookies = playwright_pool.submit(refresh_cookies).result(
                        timeout=5.0
                    )
                except (RuntimeError, TimeoutError, OSError):
                    cookies = {}
                return attempt_fetch(retry_on_expired=False)
            else:
                raise ValueError(
                    f"NSE API blocked request even after refreshing cookies: {e}"
                )

        return r_chain.json()

    try:
        return attempt_fetch()
    except (requests.exceptions.RequestException, ValueError, OSError) as e:
        logger.error(f"Error fetching option chain for {symbol_upper}: {e}")
        raise
