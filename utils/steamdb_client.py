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

            # Extraer nombre del juego de la página
            logger.debug(f"[SteamDB] Extrayendo nombre del juego")
            game_name = await page.evaluate("""
                () => {
                    // Intentar múltiples selectores para el nombre del juego
                    const selectors = [
                        'h1.pagehead',
                        'td[itemprop="name"]',
                        '.pagehead h1',
                        'h1',
                        '.scope-app td[itemprop="name"]'
                    ];

                    for (const selector of selectors) {
                        const elem = document.querySelector(selector);
                        if (elem) {
                            let text = elem.textContent.trim();
                            // Limpiar el texto (remover info extra como "App ID: xxx")
                            text = text.replace(/App\s*ID\s*:\s*\d+/gi, '').trim();
                            if (text && text.length > 0) {
                                return text;
                            }
                        }
                    }

                    return '';
                }
            """)

            if game_name:
                logger.debug(f"[SteamDB] Nombre del juego extraído: {game_name}")
            else:
                logger.warning(f"[SteamDB] No se pudo extraer el nombre del juego")
                game_name = f"App ID {appid}"

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
            # Agregar nombre del juego a los datos
            data['game_name'] = game_name
            logger.info(f"[SteamDB] Datos obtenidos exitosamente para {game_name}")
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


async def get_steam_sales_calendar():
    """
    Obtiene información sobre sales activas y próximas desde SteamDB.

    Returns:
        dict con información de sales o None si hay error
    """
    sales_url = "https://steamdb.info/sales/history/"

    logger.info(f"[SteamDB] Obteniendo calendario de sales desde {sales_url}")

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
                locale='en-US',
            )

            # Inyectar script para ocultar automatización
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => false
                });

                window.chrome = {
                    runtime: {}
                };
            """)

            page = await context.new_page()

            logger.debug(f"[SteamDB] Navegando a {sales_url}")

            # Navegar a la página de sales history
            await page.goto(sales_url, wait_until='networkidle', timeout=60000)

            # Esperar a que Cloudflare termine la verificación
            await page.wait_for_timeout(5000)

            logger.debug(f"[SteamDB] Página cargada, extrayendo información de sales")

            # Extraer información usando JavaScript con múltiples estrategias
            sales_info = await page.evaluate("""
                () => {
                    const result = {
                        current_sales: [],
                        upcoming_sales: [],
                        next_sale_countdown: null
                    };

                    // Estrategia 1: Buscar contador de próxima sale
                    // Buscar elementos con countdown o timer
                    const countdownElements = document.querySelectorAll('[data-time], .countdown, #countdown, time[datetime]');
                    for (let elem of countdownElements) {
                        const text = elem.textContent.trim();
                        const dataTime = elem.getAttribute('data-time');
                        const datetime = elem.getAttribute('datetime');

                        if (dataTime || datetime || text) {
                            result.next_sale_countdown = {
                                text: text,
                                data_time: dataTime,
                                datetime: datetime,
                                html: elem.outerHTML
                            };
                            break;
                        }
                    }

                    // Estrategia 2: Buscar tablas con clase específica de SteamDB
                    const allTables = document.querySelectorAll('table.table');

                    for (let table of allTables) {
                        // Buscar el header anterior a la tabla
                        let header = table.previousElementSibling;
                        while (header && !['H1', 'H2', 'H3', 'H4'].includes(header.tagName)) {
                            header = header.previousElementSibling;
                        }

                        const headerText = header ? header.textContent.trim().toLowerCase() : '';
                        const tbody = table.querySelector('tbody');
                        if (!tbody) continue;

                        const rows = tbody.querySelectorAll('tr');

                        // Detectar si es tabla de sales actuales o próximas
                        const isCurrentSales = headerText.includes('current') || headerText.includes('active') || headerText.includes('now');
                        const isUpcomingSales = headerText.includes('upcoming') || headerText.includes('future') || headerText.includes('next') || headerText.includes('scheduled');

                        for (let row of rows) {
                            const cells = row.querySelectorAll('td');
                            if (cells.length === 0) continue;

                            // Extraer información de las celdas
                            const cellTexts = Array.from(cells).map(cell => cell.textContent.trim());

                            if (isCurrentSales && cells.length >= 2) {
                                const sale = {
                                    name: cellTexts[0] || '',
                                    start: cellTexts.length >= 2 ? cellTexts[1] : '',
                                    end: cellTexts.length >= 3 ? cellTexts[2] : ''
                                };
                                if (sale.name) {
                                    result.current_sales.push(sale);
                                }
                            } else if (isUpcomingSales && cells.length >= 1) {
                                const sale = {
                                    name: cellTexts[0] || '',
                                    date: cellTexts.length >= 2 ? cellTexts[1] : cellTexts[0]
                                };
                                if (sale.name) {
                                    result.upcoming_sales.push(sale);
                                }
                            }
                        }
                    }

                    // Estrategia 3: Si no encontramos nada, buscar cualquier tabla cerca de headings relevantes
                    if (result.current_sales.length === 0 && result.upcoming_sales.length === 0) {
                        const allHeadings = document.querySelectorAll('h1, h2, h3, h4, h5, h6');

                        for (let heading of allHeadings) {
                            const headingText = heading.textContent.trim().toLowerCase();

                            // Buscar tabla siguiente
                            let sibling = heading.nextElementSibling;
                            while (sibling && sibling.tagName !== 'TABLE' && result.upcoming_sales.length === 0) {
                                if (sibling.tagName === 'TABLE' || sibling.querySelector('table')) {
                                    const targetTable = sibling.tagName === 'TABLE' ? sibling : sibling.querySelector('table');
                                    const rows = targetTable.querySelectorAll('tbody tr, tr');

                                    for (let row of rows) {
                                        const cells = row.querySelectorAll('td, th');
                                        if (cells.length >= 1) {
                                            const cellTexts = Array.from(cells).map(cell => cell.textContent.trim());

                                            // Intentar detectar el tipo basado en el contenido
                                            if (headingText.includes('upcoming') || headingText.includes('next') || headingText.includes('future')) {
                                                result.upcoming_sales.push({
                                                    name: cellTexts[0] || '',
                                                    date: cellTexts.length >= 2 ? cellTexts[1] : ''
                                                });
                                            } else if (headingText.includes('current') || headingText.includes('active')) {
                                                result.current_sales.push({
                                                    name: cellTexts[0] || '',
                                                    start: cellTexts.length >= 2 ? cellTexts[1] : '',
                                                    end: cellTexts.length >= 3 ? cellTexts[2] : ''
                                                });
                                            }
                                        }
                                    }
                                    break;
                                }
                                sibling = sibling.nextElementSibling;
                            }
                        }
                    }

                    // Estrategia 4: Buscar divs o sections con clases relacionadas
                    const saleSections = document.querySelectorAll('[class*="sale"], [class*="event"], [id*="sale"], [id*="event"]');
                    for (let section of saleSections) {
                        const text = section.textContent.toLowerCase();
                        if (text.includes('next') || text.includes('upcoming') || text.includes('starts in')) {
                            // Buscar elementos de tiempo dentro de esta sección
                            const timeElements = section.querySelectorAll('time, [data-time], .time, .date');
                            for (let timeElem of timeElements) {
                                if (!result.next_sale_countdown) {
                                    result.next_sale_countdown = {
                                        text: timeElem.textContent.trim(),
                                        data_time: timeElem.getAttribute('data-time'),
                                        datetime: timeElem.getAttribute('datetime'),
                                        context: section.textContent.trim().substring(0, 200)
                                    };
                                }
                            }
                        }
                    }

                    return result;
                }
            """)

            # Si no encontramos información, tomar screenshot para debugging
            if len(sales_info.get('current_sales', [])) == 0 and len(sales_info.get('upcoming_sales', [])) == 0:
                logger.warning("[SteamDB] No se encontró información de sales, tomando screenshot para debug")
                try:
                    await page.screenshot(path='/tmp/steamdb_sales_debug.png')
                    logger.info("[SteamDB] Screenshot guardado en /tmp/steamdb_sales_debug.png")
                except Exception as e:
                    logger.error(f"[SteamDB] Error al tomar screenshot: {e}")

            await browser.close()

            countdown_info = sales_info.get('next_sale_countdown')
            logger.info(f"[SteamDB] Sales info obtenida: {len(sales_info.get('current_sales', []))} activas, {len(sales_info.get('upcoming_sales', []))} próximas")
            if countdown_info:
                logger.info(f"[SteamDB] Countdown detectado: {countdown_info.get('text', 'N/A')}")

            return {
                "success": True,
                "current_sales": sales_info.get('current_sales', []),
                "upcoming_sales": sales_info.get('upcoming_sales', []),
                "next_sale_countdown": countdown_info,
                "has_current_sales": len(sales_info.get('current_sales', [])) > 0,
                "has_upcoming_sales": len(sales_info.get('upcoming_sales', [])) > 0,
                "has_countdown": countdown_info is not None
            }

    except Exception as e:
        logger.error(f"[SteamDB] Error al obtener sales calendar: {e}", exc_info=True)
        return None
