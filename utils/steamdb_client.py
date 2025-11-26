"""
SteamDB Client
Scraper para obtener historial de precios desde SteamDB usando Playwright.
"""

import logging
import re
from datetime import datetime
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)


def extract_steam_app_id_from_url(url: str) -> str:
    """
    Extrae el Steam App ID de una URL de Steam.

    Args:
        url: URL de Steam (e.g., https://store.steampowered.com/app/1627720/Lies_of_P/)

    Returns:
        Steam App ID o None si no se encuentra
    """
    pattern = r'store\.steampowered\.com/app/(\d+)'
    match = re.search(pattern, url)
    if match:
        return match.group(1)

    # Intentar con otros formatos
    pattern = r'steamdb\.info/app/(\d+)'
    match = re.search(pattern, url)
    if match:
        return match.group(1)

    # Si es solo el número
    if url.isdigit():
        return url

    return None


async def get_steamdb_price_history(appid: str, cc: str = "ar"):
    """
    Obtiene el historial de precios desde SteamDB usando Playwright.

    Args:
        appid: ID de la aplicación en Steam
        cc: Código de país (country code, default: "ar" para Argentina)

    Returns:
        dict: Datos del historial de precios o None si hay error
    """
    api_url = f"https://steamdb.info/api/GetPriceHistory/?appid={appid}&cc={cc}"
    base_url = f"https://steamdb.info/app/{appid}/"

    logger.info(f"[SteamDB] Obteniendo historial de precios para App ID: {appid} ({cc})")

    try:
        async with async_playwright() as p:
            # Configurar navegador en modo headless
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                ]
            )

            # Crear contexto con user agent realista
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                locale='es-AR',
                extra_http_headers={
                    'Accept-Language': 'es-AR,es;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br, zstd',
                    'sec-ch-ua': '"Chromium";v="142", "Brave";v="142", "Not_A Brand";v="99"',
                    'sec-ch-ua-mobile': '?0',
                    'sec-ch-ua-platform': '"Windows"',
                    'sec-fetch-dest': 'empty',
                    'sec-fetch-mode': 'cors',
                    'sec-fetch-site': 'same-origin',
                    'sec-gpc': '1',
                }
            )

            # Inyectar script para ocultar automatización
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => false
                });

                window.chrome = {
                    runtime: {}
                };

                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
            """)

            page = await context.new_page()

            logger.debug(f"[SteamDB] Navegando a {base_url}")

            # Navegar a la página principal
            await page.goto(base_url, wait_until='networkidle', timeout=60000)

            # Esperar a que Cloudflare termine la verificación
            await page.wait_for_timeout(5000)

            # Verificar que tenemos la cookie cf_clearance
            cookies = await context.cookies()
            cf_clearance = None
            for cookie in cookies:
                if cookie['name'] == 'cf_clearance':
                    cf_clearance = cookie['value']
                    logger.debug(f"[SteamDB] Cookie cf_clearance obtenida")
                    break

            if not cf_clearance:
                logger.warning("[SteamDB] No se encontró la cookie cf_clearance")

            # Hacer petición a la API usando JavaScript dentro de la página
            logger.debug(f"[SteamDB] Haciendo petición a la API: {api_url}")

            api_data = await page.evaluate("""
                async (apiUrl) => {
                    try {
                        const response = await fetch(apiUrl, {
                            method: 'GET',
                            headers: {
                                'accept': 'application/json',
                                'x-requested-with': 'XMLHttpRequest'
                            },
                            credentials: 'include'
                        });

                        if (!response.ok) {
                            return { error: true, status: response.status, statusText: response.statusText };
                        }

                        const data = await response.json();
                        return { error: false, data: data };
                    } catch (error) {
                        return { error: true, message: error.message };
                    }
                }
            """, api_url)

            await browser.close()

            if api_data.get('error'):
                logger.error(f"[SteamDB] Error al obtener datos de la API")
                if 'status' in api_data:
                    logger.error(f"[SteamDB] Status: {api_data['status']} - {api_data.get('statusText', '')}")
                if 'message' in api_data:
                    logger.error(f"[SteamDB] Mensaje: {api_data['message']}")
                return None

            data = api_data['data']
            logger.info(f"[SteamDB] Datos obtenidos exitosamente")
            return data

    except Exception as e:
        logger.error(f"[SteamDB] Error al obtener historial de precios: {e}", exc_info=True)
        return None


def analyze_price_data(price_data: dict, cc: str = "ar"):
    """
    Analiza los datos de precios y genera un resumen.

    Args:
        price_data: Datos del historial de precios desde SteamDB
        cc: Código de país

    Returns:
        dict con análisis del historial
    """
    if not price_data or not price_data.get('success'):
        return None

    history = price_data['data']['history']
    sales_events = price_data['data'].get('sales', {})

    if not history:
        return None

    # Extraer precios
    prices = [item['y'] for item in history]

    # Encontrar ofertas (cambios de precio con descuento)
    offers = []
    for i in range(len(history)):
        current = history[i]
        current_date = datetime.fromtimestamp(current['x'] / 1000)
        current_price = current['y']
        current_discount = current.get('d', 0)

        # Determinar duración del precio
        if i < len(history) - 1:
            next_item = history[i + 1]
            to_date = datetime.fromtimestamp(next_item['x'] / 1000)
        else:
            to_date = datetime.now()

        # Buscar evento de venta asociado
        event_name = sales_events.get(str(current['x']), "")

        offers.append({
            "date": current_date.strftime("%d/%m/%Y"),
            "date_end": to_date.strftime("%d/%m/%Y"),
            "price": current_price,
            "price_formatted": current.get('f', f"${current_price:.2f}"),
            "discount": current_discount,
            "event": event_name,
            "is_discount": current_discount > 0
        })

    # Currency symbol según el país
    currency_symbols = {
        "ar": "ARS$",
        "us": "$",
        "eu": "€",
        "gb": "£",
        "br": "R$"
    }
    currency = currency_symbols.get(cc.lower(), "$")

    analysis = {
        "success": True,
        "total_records": len(history),
        "min_price": min(prices),
        "max_price": max(prices),
        "current_price": history[-1]['y'],
        "current_price_formatted": history[-1]['f'],
        "current_discount": history[-1].get('d', 0),
        "currency": currency,
        "offers": offers,
        "has_sales_events": len(sales_events) > 0
    }

    return analysis
