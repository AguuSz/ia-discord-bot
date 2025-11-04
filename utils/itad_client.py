import logging
import re
from typing import Optional, Dict, List
import aiohttp

logger = logging.getLogger(__name__)

# Credenciales de IsThereAnyDeal
ITAD_API_KEY = "212adbd710ea857d8b3817badcd1e12578ba524b"

# Base URL de la API
ITAD_API_BASE = "https://api.isthereanydeal.com"

def extract_steam_app_id(url: str) -> Optional[str]:
    """
    Extrae el ID del juego desde una URL de Steam.

    Args:
        url: URL de Steam (e.g., https://store.steampowered.com/app/1627720/Lies_of_P/)

    Returns:
        El ID del juego o None si no se encuentra
    """
    pattern = r'store\.steampowered\.com/app/(\d+)'
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    return None

async def convert_steam_id_to_itad(steam_app_id: str) -> Optional[str]:
    """
    Convierte un Steam App ID a un ITAD Game ID.

    Args:
        steam_app_id: ID del juego en Steam (ej: "1627720")

    Returns:
        ITAD Game ID (UUID) o None si hay error
    """
    url = f"{ITAD_API_BASE}/lookup/id/shop/61/v1"

    # Formato requerido: "app/{steam_app_id}"
    steam_id_format = f"app/{steam_app_id}"

    logger.info(f"[ITAD] Convirtiendo Steam ID {steam_app_id} a ITAD Game ID...")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=[steam_id_format],
                params={"key": ITAD_API_KEY},  # Usar query parameter
                headers={
                    "Content-Type": "application/json"
                }
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"[ITAD] Error HTTP {response.status} al convertir Steam ID")
                    logger.error(f"[ITAD] Respuesta de error: {error_text}")
                    return None

                data = await response.json()
                logger.debug(f"[ITAD] Respuesta de conversión: {data}")

                # La respuesta es un dict con el formato: {"app/1627720": "uuid..."}
                itad_game_id = data.get(steam_id_format)

                if itad_game_id:
                    logger.info(f"[ITAD] Steam ID convertido exitosamente: {itad_game_id}")
                    return itad_game_id
                else:
                    logger.warning(f"[ITAD] No se encontró el juego en ITAD para Steam ID {steam_app_id}")
                    return None

    except Exception as e:
        logger.error(f"[ITAD] Error al convertir Steam ID: {e}", exc_info=True)
        return None

async def get_price_info(itad_game_id: str, country: str = "US") -> Dict:
    """
    Obtiene información de precios para un juego.

    Args:
        itad_game_id: ITAD Game ID (UUID)
        country: Código de país (default: "US")

    Returns:
        Diccionario con información de precios
    """
    url = f"{ITAD_API_BASE}/games/prices/v3"

    logger.info(f"[ITAD] Obteniendo información de precios para {itad_game_id}...")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=[itad_game_id],
                params={
                    "country": country,
                    "key": ITAD_API_KEY  # Intentar con query parameter
                },
                headers={
                    "Content-Type": "application/json"
                }
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"[ITAD] Error HTTP {response.status} al obtener precios")
                    logger.error(f"[ITAD] Respuesta de error: {error_text}")
                    return {
                        "success": False,
                        "error": f"Error HTTP {response.status}"
                    }

                data = await response.json()
                logger.debug(f"[ITAD] Respuesta de precios: {data}")

                # La respuesta es un array con la info del juego
                if not data or len(data) == 0:
                    return {
                        "success": False,
                        "error": "No se encontró información de precios"
                    }

                game_data = data[0]

                # Extraer información relevante
                result = {
                    "success": True,
                    "game_id": itad_game_id,
                    "deals": []
                }

                # Información del juego si está disponible
                if "game" in game_data:
                    result["game_name"] = game_data["game"].get("title", "Unknown")

                # Precio actual en diferentes tiendas
                if "deals" in game_data:
                    for deal in game_data["deals"]:
                        shop = deal.get("shop", {}).get("name", "Unknown")
                        price = deal.get("price", {})

                        deal_info = {
                            "shop": shop,
                            "price": price.get("amount"),
                            "currency": price.get("currency"),
                            "cut": deal.get("cut", 0),  # Porcentaje de descuento
                            "url": deal.get("url")
                        }
                        result["deals"].append(deal_info)

                logger.info(f"[ITAD] Se encontraron {len(result['deals'])} ofertas")
                return result

    except Exception as e:
        logger.error(f"[ITAD] Error al obtener precios: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Error inesperado: {str(e)}"
        }

async def get_game_overview(itad_game_id: str, country: str = "US") -> Dict:
    """
    Obtiene resumen de precios incluyendo histórico.

    Args:
        itad_game_id: ITAD Game ID (UUID)
        country: Código de país (default: "US")

    Returns:
        Diccionario con resumen de precios e histórico
    """
    url = f"{ITAD_API_BASE}/games/overview/v2"

    logger.info(f"[ITAD] Obteniendo overview para {itad_game_id}...")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=[itad_game_id],
                params={
                    "country": country,
                    "key": ITAD_API_KEY  # Intentar con query parameter
                },
                headers={
                    "Content-Type": "application/json"
                }
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"[ITAD] Error HTTP {response.status} al obtener overview")
                    logger.error(f"[ITAD] Respuesta de error: {error_text}")
                    return {
                        "success": False,
                        "error": f"Error HTTP {response.status}: {error_text}"
                    }

                data = await response.json()
                logger.debug(f"[ITAD] Respuesta de overview: {data}")

                # La estructura es: {"prices": [...], "bundles": [...]}
                if not data or "prices" not in data or len(data["prices"]) == 0:
                    return {
                        "success": False,
                        "error": "No se encontró información de precios"
                    }

                game_data = data["prices"][0]

                result = {
                    "success": True,
                    "game_id": itad_game_id,
                    "game_name": None,  # Esta API no devuelve el nombre en overview
                    "current_best": None,
                    "history_low": {}
                }

                # Mejor precio actual
                if "current" in game_data:
                    current_data = game_data["current"]
                    shop = current_data.get("shop", {}).get("name", "Unknown")
                    price_info = current_data.get("price", {})
                    regular_info = current_data.get("regular", {})

                    result["current_best"] = {
                        "price": price_info.get("amount"),
                        "regular_price": regular_info.get("amount"),
                        "cut": current_data.get("cut", 0),
                        "shop": shop,
                        "url": current_data.get("url"),
                        "expiry": current_data.get("expiry")
                    }

                # Precio histórico más bajo
                if "lowest" in game_data:
                    lowest_data = game_data["lowest"]
                    shop = lowest_data.get("shop", {}).get("name", "Unknown")
                    price_info = lowest_data.get("price", {})

                    result["history_low"]["all_time"] = {
                        "price": price_info.get("amount"),
                        "cut": lowest_data.get("cut", 0),
                        "shop": shop,
                        "recorded": lowest_data.get("timestamp")
                    }

                # URL del juego
                if "urls" in game_data:
                    result["game_url"] = game_data["urls"].get("game")

                logger.info(f"[ITAD] Overview obtenido exitosamente")
                return result

    except Exception as e:
        logger.error(f"[ITAD] Error al obtener overview: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Error inesperado: {str(e)}"
        }

async def get_game_info(itad_game_id: str) -> Dict:
    """
    Obtiene información básica del juego (incluyendo nombre).

    Args:
        itad_game_id: ITAD Game ID (UUID)

    Returns:
        Diccionario con información del juego
    """
    url = f"{ITAD_API_BASE}/games/info/v2"

    logger.info(f"[ITAD] Obteniendo información del juego {itad_game_id}...")

    try:
        async with aiohttp.ClientSession() as session:
            # Intentar con GET primero
            async with session.get(
                url,
                params={
                    "id": itad_game_id,
                    "key": ITAD_API_KEY
                }
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"[ITAD] Error HTTP {response.status} al obtener info del juego")
                    logger.error(f"[ITAD] Respuesta de error: {error_text}")
                    return {
                        "success": False,
                        "error": f"Error HTTP {response.status}"
                    }

                data = await response.json()
                logger.debug(f"[ITAD] Respuesta de info: {data}")

                # Puede ser un dict directo o un array
                if isinstance(data, list):
                    if not data or len(data) == 0:
                        return {
                            "success": False,
                            "error": "No se encontró información del juego"
                        }
                    game_info = data[0]
                elif isinstance(data, dict):
                    game_info = data
                else:
                    return {
                        "success": False,
                        "error": "Formato de respuesta inesperado"
                    }

                return {
                    "success": True,
                    "game_name": game_info.get("title", "Unknown"),
                    "type": game_info.get("type"),
                    "mature": game_info.get("mature", False)
                }

    except Exception as e:
        logger.error(f"[ITAD] Error al obtener info: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Error inesperado: {str(e)}"
        }

async def get_steam_game_prices(steam_url: str, country: str = "US") -> Dict:
    """
    Función principal que obtiene precios de un juego de Steam.

    Args:
        steam_url: URL del juego en Steam
        country: Código de país (default: "US")

    Returns:
        Diccionario con toda la información de precios
    """
    logger.info(f"[ITAD] Procesando URL de Steam: {steam_url}")

    # Extraer Steam App ID
    steam_app_id = extract_steam_app_id(steam_url)
    if not steam_app_id:
        return {
            "success": False,
            "error": "No se pudo extraer el Steam App ID de la URL"
        }

    logger.info(f"[ITAD] Steam App ID: {steam_app_id}")

    # Convertir a ITAD Game ID
    itad_game_id = await convert_steam_id_to_itad(steam_app_id)
    if not itad_game_id:
        return {
            "success": False,
            "error": f"No se pudo encontrar el juego en IsThereAnyDeal (Steam ID: {steam_app_id})"
        }

    # Obtener información del juego (nombre, etc.)
    game_info = await get_game_info(itad_game_id)
    game_name = game_info.get("game_name", "Unknown") if game_info.get("success") else "Unknown"

    # Obtener información completa de precios
    overview = await get_game_overview(itad_game_id, country)

    if not overview["success"]:
        return overview

    # Combinar información
    result = {
        "success": True,
        "steam_app_id": steam_app_id,
        "game_name": game_name,
        "current_best": overview.get("current_best"),
        "history_low": overview.get("history_low"),
        "game_url": overview.get("game_url")
    }

    logger.info(f"[ITAD] Información completa obtenida para {result['game_name']}")
    return result
