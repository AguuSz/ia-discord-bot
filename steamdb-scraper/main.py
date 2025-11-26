import json
import time
from playwright.sync_api import sync_playwright


def get_steamdb_data(appid: str = "2651280", cc: str = "ar"):
    """
    Scraper para SteamDB que bypasea la protección de Cloudflare usando Playwright.

    Args:
        appid: ID de la aplicación en Steam
        cc: Código de país (country code)

    Returns:
        dict: JSON con los datos de precio histórico
    """
    api_url = f"https://steamdb.info/api/GetPriceHistory/?appid={appid}&cc={cc}"
    base_url = f"https://steamdb.info/app/{appid}/"

    print(f"[*] Usando Playwright (headless mode)")
    print(f"[*] URL: {base_url}")

    with sync_playwright() as p:
        # Configurar el navegador en modo headless con opciones stealth
        browser = p.chromium.launch(
            headless=True,  # Modo sin ventana visible
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
            ]
        )

        # Crear contexto con user agent y viewport realista
        context = browser.new_context(
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

        # Inyectar script para ocultar que estamos usando automatización
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => false
            });

            // Sobrescribir la propiedad chrome
            window.chrome = {
                runtime: {}
            };

            // Sobrescribir las propiedades de permisos
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)

        page = context.new_page()

        print(f"[*] Navegando a {base_url}")
        print("[*] Esperando a que Cloudflare verifique...")

        try:
            # Navegar a la página principal primero
            page.goto(base_url, wait_until='networkidle', timeout=60000)

            # Esperar un poco para que Cloudflare termine la verificación
            page.wait_for_timeout(5000)

            # Verificar si pasamos Cloudflare
            title = page.title()
            print(f"[+] Página cargada: {title}")

            # Verificar que tenemos la cookie cf_clearance
            cookies = context.cookies()
            cf_clearance = None
            for cookie in cookies:
                if cookie['name'] == 'cf_clearance':
                    cf_clearance = cookie['value']
                    print(f"[+] Cookie cf_clearance obtenida: {cf_clearance[:50]}...")
                    break

            if not cf_clearance:
                print("[!] Advertencia: No se encontró la cookie cf_clearance")

            # ESTRATEGIA: Usar JavaScript dentro de la página para hacer fetch()
            # Esto simula una petición XHR real desde el navegador
            print(f"\n[*] Haciendo petición a la API usando JavaScript: {api_url}")

            # Ejecutar fetch desde JavaScript dentro de la página
            api_data = page.evaluate("""
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

            if api_data.get('error'):
                print(f"[!] Error al obtener datos de la API")
                if 'status' in api_data:
                    print(f"[!] Status: {api_data['status']} - {api_data.get('statusText', '')}")
                if 'message' in api_data:
                    print(f"[!] Mensaje: {api_data['message']}")
                return None

            data = api_data['data']
            print(f"[+] ¡Éxito! Datos obtenidos")
            print(f"[+] Tamaño de datos: {len(str(data))} caracteres")
            return data

        except Exception as e:
            print(f"[!] Error: {str(e)}")
            # Tomar screenshot para debug
            page.screenshot(path='error_screenshot.png')
            print("[*] Screenshot guardado en error_screenshot.png")
            return None

        finally:
            browser.close()


def main():
    """Función principal"""
    print("=" * 60)
    print("SteamDB Scraper - Bypass Cloudflare")
    print("=" * 60)

    # Parámetros
    appid = "2651280"
    country_code = "ar"

    print(f"\n[*] AppID: {appid}")
    print(f"[*] Country Code: {country_code}\n")

    # Ejecutar scraper con Playwright
    result = get_steamdb_data(appid, country_code)

    if result:
        # Guardar en archivo JSON
        output_file = f"price_history_{appid}_{country_code}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(f"\n[+] Datos guardados en: {output_file}")

        # Mostrar resumen
        if 'data' in result and 'prices' in result['data']:
            prices = result['data']['prices']
            print(f"[+] Total de registros de precio: {len(prices)}")
            if prices:
                print(f"[+] Primer registro: {prices[0]}")
                print(f"[+] Último registro: {prices[-1]}")

        return result
    else:
        print("\n[!] No se pudieron obtener los datos")
        return None


if __name__ == "__main__":
    main()
