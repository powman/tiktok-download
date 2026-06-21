import json

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Possíveis ids de script tag onde o TikTok embute o estado da página (SIGI_STATE é o
# formato legado, __UNIVERSAL_DATA_FOR_REHYDRATION__ é o atual no momento da implementação).
STATE_SCRIPT_IDS = ["__UNIVERSAL_DATA_FOR_REHYDRATION__", "SIGI_STATE"]

# Chaves que, se presentes num dict, indicam que ele provavelmente descreve um produto.
PRODUCT_TITLE_KEYS = ["title", "name", "product_name", "productName"]
PRODUCT_PRICE_KEYS = ["price", "real_price", "formatted_price", "price_text", "min_price"]
PRODUCT_IMAGE_KEYS = ["cover", "image", "main_image", "image_url", "thumb_url", "url_list"]
PRODUCT_LINK_KEYS = ["url", "link", "product_url", "schema"]


class ShopScraperError(Exception):
    """Erro ao raspar dados do TikTok Shop (bloqueio, captcha, login-wall, etc)."""


def extract_shop_products(video_url: str) -> list:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        )
        try:
            page = browser.new_page(user_agent=USER_AGENT, viewport={"width": 1280, "height": 900})
            data = _load_state_json(page, video_url)
            candidates = _find_product_candidates(data)
            products = []
            for candidate in candidates:
                product = _normalize_product(candidate)
                if product is None:
                    continue
                if product.get("_needs_resolution") and product.get("link"):
                    resolved = _resolve_product_link(page, product["link"])
                    if resolved:
                        product = resolved
                    else:
                        continue
                product.pop("_needs_resolution", None)
                product.pop("link", None)
                if product.get("title") or product.get("price"):
                    products.append(product)
            return _dedupe(products)
        finally:
            browser.close()


def _load_state_json(page, url: str) -> dict:
    try:
        page.goto(url, wait_until="networkidle", timeout=30000)
    except PlaywrightTimeoutError:
        raise ShopScraperError("Timeout ao carregar a página do TikTok")

    if _looks_blocked(page):
        raise ShopScraperError("TikTok bloqueou o acesso (captcha ou login necessário)")

    for script_id in STATE_SCRIPT_IDS:
        try:
            raw = page.locator(f"script#{script_id}").inner_text(timeout=2000)
        except PlaywrightTimeoutError:
            continue
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            continue
    return {}


def _looks_blocked(page) -> bool:
    # Usa o texto visível (não o HTML/JS bruto, que contém nomes de arquivo como
    # "captcha-ttp.js" carregados em toda página e geram falso positivo).
    try:
        visible_text = page.inner_text("body").lower()
    except PlaywrightTimeoutError:
        return False
    return any(
        marker in visible_text
        for marker in ["verify you are human", "verify to continue", "log in to continue", "enter the captcha"]
    )


def _find_product_candidates(data, _depth=0) -> list:
    candidates = []
    if _depth > 12:
        return candidates

    if isinstance(data, dict):
        if _is_product_like(data):
            candidates.append(data)
        for value in data.values():
            candidates.extend(_find_product_candidates(value, _depth + 1))
    elif isinstance(data, list):
        for item in data:
            candidates.extend(_find_product_candidates(item, _depth + 1))

    return candidates


def _is_product_like(obj: dict) -> bool:
    has_title = any(k in obj for k in PRODUCT_TITLE_KEYS)
    if not has_title:
        return False
    if any(k in obj for k in PRODUCT_PRICE_KEYS):
        return True
    # Sem preço embutido: só considera produto se o link apontar explicitamente
    # para o TikTok Shop (evita falsos positivos em objetos não relacionados,
    # como música ou autor, que também têm "title"/links genéricos).
    link = _first_value(obj, PRODUCT_LINK_KEYS)
    return bool(link and isinstance(link, str) and "shop.tiktok.com" in link)


def _normalize_product(obj: dict) -> dict:
    title = _first_value(obj, PRODUCT_TITLE_KEYS)
    price = _first_value(obj, PRODUCT_PRICE_KEYS)
    image = _first_image(obj)
    link = _first_value(obj, PRODUCT_LINK_KEYS)

    if not title and not price and not image:
        return None

    needs_resolution = not price and link
    return {
        "title": title,
        "price": _format_price(price),
        "image": image,
        "link": link,
        "_needs_resolution": needs_resolution,
    }


def _first_value(obj: dict, keys: list):
    for key in keys:
        value = obj.get(key)
        if isinstance(value, (str, int, float)) and str(value).strip():
            return value
    return None


def _first_image(obj: dict):
    for key in PRODUCT_IMAGE_KEYS:
        value = obj.get(key)
        if isinstance(value, str) and value.startswith("http"):
            return value
        if isinstance(value, dict):
            urls = value.get("url_list") or value.get("urls")
            if isinstance(urls, list) and urls:
                return urls[0]
        if isinstance(value, list) and value and isinstance(value[0], str):
            return value[0]
    return None


def _format_price(price):
    if price is None:
        return None
    if isinstance(price, str):
        return price.strip()
    # Preços em centavos costumam vir como inteiro (ex: 1990 -> 19.90)
    if isinstance(price, (int, float)) and price > 1000:
        return f"{price / 100:.2f}"
    return str(price)


def _resolve_product_link(page, link: str):
    if not link.startswith("http"):
        return None
    try:
        data = _load_state_json(page, link)
    except ShopScraperError:
        return None
    for candidate in _find_product_candidates(data):
        product = _normalize_product(candidate)
        if product and (product.get("title") or product.get("price")):
            return product
    return None


def _dedupe(products: list) -> list:
    seen = set()
    result = []
    for product in products:
        key = (product.get("title"), product.get("price"), product.get("image"))
        if key in seen:
            continue
        seen.add(key)
        result.append(product)
    return result
