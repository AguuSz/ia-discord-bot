"""
Steam API Client
Maneja las llamadas a la API de Steam para obtener información de usuarios y juegos.
"""

import aiohttp
import logging

logger = logging.getLogger(__name__)

STEAM_API_BASE = "https://api.steampowered.com"


async def resolve_vanity_url(api_key: str, vanity_url: str) -> dict:
    """
    Resuelve una vanity URL (custom URL) a un Steam ID numérico.

    Args:
        api_key: Steam API Key
        vanity_url: Custom URL del usuario (ej: "Agus")

    Returns:
        dict con 'success' (bool) y 'steamid' (str) o 'error' (str)
    """
    url = f"{STEAM_API_BASE}/ISteamUser/ResolveVanityURL/v1/"
    params = {
        "key": api_key,
        "vanityurl": vanity_url
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    logger.error(f"Steam API error: status {response.status}")
                    return {
                        "success": False,
                        "error": f"Steam API retornó status {response.status}"
                    }

                data = await response.json()

                if data.get("response", {}).get("success") == 1:
                    steamid = data["response"]["steamid"]
                    logger.info(f"Vanity URL '{vanity_url}' resuelto a Steam ID: {steamid}")
                    return {
                        "success": True,
                        "steamid": steamid
                    }
                else:
                    logger.warning(f"No se pudo resolver vanity URL: {vanity_url}")
                    return {
                        "success": False,
                        "error": "No se encontró el perfil de Steam. Verifica que la URL sea correcta."
                    }

    except Exception as e:
        logger.error(f"Error al resolver vanity URL: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Error al conectar con Steam API: {str(e)}"
        }


async def get_owned_games(api_key: str, steamid: str) -> dict:
    """
    Obtiene la lista de juegos de un usuario de Steam.

    Args:
        api_key: Steam API Key
        steamid: Steam ID numérico del usuario

    Returns:
        dict con 'success' (bool) y 'games' (list) o 'error' (str)
    """
    url = f"{STEAM_API_BASE}/IPlayerService/GetOwnedGames/v1/"
    params = {
        "key": api_key,
        "steamid": steamid,
        "include_appinfo": 1,
        "include_played_free_games": 1
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    logger.error(f"Steam API error: status {response.status}")
                    return {
                        "success": False,
                        "error": f"Steam API retornó status {response.status}"
                    }

                data = await response.json()

                if "response" in data and "games" in data["response"]:
                    games = data["response"]["games"]
                    game_count = data["response"].get("game_count", len(games))

                    logger.info(f"Obtenidos {game_count} juegos para Steam ID: {steamid}")

                    # Convertir a nuestro formato
                    formatted_games = []
                    for game in games:
                        formatted_games.append({
                            "appid": game.get("appid"),
                            "name": game.get("name", "Unknown Game"),
                            "playtime_hours": round(game.get("playtime_forever", 0) / 60, 1)  # Convertir minutos a horas
                        })

                    return {
                        "success": True,
                        "games": formatted_games,
                        "game_count": game_count
                    }
                else:
                    logger.warning(f"No se encontraron juegos para Steam ID: {steamid}")
                    return {
                        "success": False,
                        "error": "No se pudieron obtener los juegos. El perfil puede ser privado."
                    }

    except Exception as e:
        logger.error(f"Error al obtener juegos: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Error al conectar con Steam API: {str(e)}"
        }


async def get_user_library(api_key: str, vanity_url_or_steamid: str) -> dict:
    """
    Obtiene la biblioteca completa de un usuario, resolviendo vanity URL si es necesario.

    Args:
        api_key: Steam API Key
        vanity_url_or_steamid: Custom URL o Steam ID del usuario

    Returns:
        dict con 'success' (bool), 'username' (str), 'games' (list) o 'error' (str)
    """
    # Intentar primero como vanity URL
    steamid = vanity_url_or_steamid
    username = vanity_url_or_steamid

    # Si no es un número, resolver como vanity URL
    if not vanity_url_or_steamid.isdigit():
        resolve_result = await resolve_vanity_url(api_key, vanity_url_or_steamid)

        if not resolve_result["success"]:
            return resolve_result

        steamid = resolve_result["steamid"]

    # Obtener juegos
    games_result = await get_owned_games(api_key, steamid)

    if not games_result["success"]:
        return games_result

    return {
        "success": True,
        "username": username,
        "steamid": steamid,
        "games": games_result["games"],
        "game_count": games_result["game_count"]
    }
