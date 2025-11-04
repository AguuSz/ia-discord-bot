import discord
from discord import app_commands
from discord.ext import commands
import os
import logging
from dotenv import load_dotenv
from utils.itad_client import get_steam_game_prices
from utils.steam_client import get_user_library
import json
import google.generativeai as genai
import re

# Configuración de logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Configurar nivel de logging para librerías específicas
logging.getLogger("discord").setLevel(logging.INFO)
logging.getLogger("discord.http").setLevel(logging.WARNING)

# Cargar variables de entorno
load_dotenv()

# Configuración del bot
TOKEN = os.getenv('DISCORD_TOKEN')
STEAM_API_KEY = os.getenv('STEAM_API_KEY')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash-lite')

# Configurar Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    logger.info(f"Gemini configurado con modelo: {GEMINI_MODEL}")
else:
    logger.warning("GEMINI_API_KEY no encontrada. Las funciones de IA estarán deshabilitadas.")

# Validar Steam API Key
if not STEAM_API_KEY:
    logger.warning("STEAM_API_KEY no encontrada. El bot no podrá obtener bibliotecas de Steam.")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    logger.info(f'{bot.user} se ha conectado a Discord!')
    logger.info(
        f"Invita al bot con el siguiente enlace: {discord.utils.oauth_url(bot.user.id)}"
    )
    try:
        synced = await bot.tree.sync()
        logger.info(f"Se sincronizaron {len(synced)} comandos slash")
    except Exception as e:
        logger.error(f"Fallo al sincronizar los comandos: {e}")

@app_commands.allowed_installs(guilds=True, users=False)
@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
@bot.tree.command(
    name="get-recommendations",
    description="Obtiene recomendaciones de juegos basadas en tu biblioteca de Steam con información de precios"
)
@app_commands.describe(
    url="URL del perfil de Steam (e.g., https://steamcommunity.com/id/Agus)",
    model="Modelo de Gemini a utilizar (opcional, por defecto usa el del .env)"
)
@app_commands.choices(model=[
    app_commands.Choice(name="Gemini 2.5 Pro (Más potente)", value="gemini-2.5-pro"),
    app_commands.Choice(name="Gemini 2.5 Flash (Equilibrado)", value="gemini-2.5-flash"),
    app_commands.Choice(name="Gemini 2.5 Flash Lite (Rápido y económico)", value="gemini-2.5-flash-lite"),
    app_commands.Choice(name="Gemini 2.0 Flash (Estable)", value="gemini-2.0-flash"),
    app_commands.Choice(name="Gemini 2.0 Flash Experimental", value="gemini-2.0-flash-exp"),
    app_commands.Choice(name="Gemini 2.0 Flash Lite", value="gemini-2.0-flash-lite"),
    app_commands.Choice(name="LearnLM 2.0 Flash Experimental", value="learnlm-2.0-flash-experimental")
])
async def get_recommendations(interaction: discord.Interaction, url: str, model: app_commands.Choice[str] = None):
    # Determinar qué modelo usar
    selected_model = model.value if model else GEMINI_MODEL
    logger.info(f"[BOT] Comando /get-recommendations ejecutado por {interaction.user} con URL: {url} y modelo: {selected_model}")

    # Defer la respuesta
    await interaction.response.defer(thinking=True)

    try:
        # Validar Steam API Key
        if not STEAM_API_KEY:
            await interaction.followup.send(
                "❌ Error: Steam API Key no configurada. Contacta al administrador del bot."
            )
            return

        # Validar que sea una URL de Steam válida
        if "steamcommunity.com/id/" not in url and "steamcommunity.com/profiles/" not in url:
            logger.warning(f"[BOT] URL inválida proporcionada: {url}")
            await interaction.followup.send(
                "❌ URL inválida. Debe ser una URL de perfil de Steam:\n"
                "- Custom URL: `https://steamcommunity.com/id/username`\n"
                "- Steam ID: `https://steamcommunity.com/profiles/76561198XXXXXXXXX`"
            )
            return

        # Extraer el username o Steam ID de la URL
        if "steamcommunity.com/id/" in url:
            username = url.split("steamcommunity.com/id/")[-1].rstrip('/')
        else:
            username = url.split("steamcommunity.com/profiles/")[-1].rstrip('/')

        logger.info(f"[BOT] Obteniendo biblioteca para: {username}")

        # Obtener biblioteca de Steam usando la API real
        library_result = await get_user_library(STEAM_API_KEY, username)

        if not library_result["success"]:
            logger.error(f"[BOT] Error al obtener biblioteca: {library_result.get('error')}")
            embed = discord.Embed(
                title="❌ Error al obtener biblioteca de Steam",
                description=library_result.get("error", "Error desconocido"),
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)
            return

        # Usuario encontrado, obtener sus juegos
        username = library_result["username"]
        steamid = library_result["steamid"]
        games = library_result["games"]
        total_games = library_result["game_count"]

        logger.info(f"[BOT] Biblioteca obtenida: {total_games} juegos para {username}")
        total_hours = sum(game["playtime_hours"] for game in games)

        # Crear embed principal
        embed = discord.Embed(
            title=f"🎮 Biblioteca de Steam - {username}",
            description=f"**Total de juegos:** {total_games}\n**Horas totales jugadas:** {total_hours:,} horas",
            color=discord.Color.blue(),
            url=url
        )

        # Ordenar juegos por horas jugadas (descendente)
        sorted_games = sorted(games, key=lambda x: x["playtime_hours"], reverse=True)

        # Mostrar top 10 juegos más jugados
        top_games = sorted_games[:10]
        top_games_text = ""
        for i, game in enumerate(top_games, 1):
            hours = game["playtime_hours"]
            name = game["name"]
            # Limitar el nombre a 40 caracteres para evitar líneas muy largas
            if len(name) > 40:
                name = name[:37] + "..."
            top_games_text += f"{i}. **{name}**\n   ⏱️ {hours} horas\n"

        embed.add_field(
            name="🏆 Top 10 Juegos Más Jugados",
            value=top_games_text,
            inline=False
        )

        # Agregar algunos stats adicionales
        avg_hours = total_hours / total_games if total_games > 0 else 0
        games_over_100h = len([g for g in games if g["playtime_hours"] >= 100])

        stats_text = f"📊 **Promedio:** {avg_hours:.1f} horas/juego\n"
        stats_text += f"🔥 **Juegos +100h:** {games_over_100h}"

        embed.add_field(
            name="📈 Estadísticas",
            value=stats_text,
            inline=False
        )

        embed.set_footer(text=f"Biblioteca de Steam • {username}")

        # NO enviar todavía, acumular embeds
        logger.info(f"[BOT] Biblioteca preparada, generando recomendaciones con Gemini...")
        all_embeds = [embed]  # Empezar con el embed de la biblioteca

        # Generar recomendaciones con Gemini
        if not GEMINI_API_KEY:
            logger.warning("[BOT] Gemini API Key no configurada, enviando solo biblioteca")
            await interaction.followup.send(embed=embed)
            return

        try:
            # Preparar el listado de juegos para Gemini
            games_list = []
            for game in games:
                games_list.append({
                    "name": game["name"],
                    "appid": game["appid"],
                    "playtime_hours": game["playtime_hours"]
                })

            games_json = json.dumps(games_list, indent=2, ensure_ascii=False)

            # Crear el prompt para Gemini
            prompt = f"""Aquí está un listado de juegos de Steam de un usuario, y sus correspondientes horas jugadas. Basándote en esta información, necesito que me retornes una lista de 5 juegos NUEVOS que le podrían interesar al usuario, basándote en que hay juegos que el usuario le dedicó más horas (porque seguramente le gustaron más que los otros).

IMPORTANTE: Los juegos que recomiendes NO deben estar en la lista de juegos que el usuario ya posee. Debes recomendar juegos COMPLETAMENTE NUEVOS que el usuario NO tiene en su biblioteca.

Necesito que retornes una lista de 5 juegos con su:
- URL de Steam (formato: https://store.steampowered.com/app/APPID/)
- Por qué elegiste este juego? (Si fue por ser similar a otro juego que el usuario ya tiene, o alguna otra razón, puede ser por popularidad entre los jugadores que comparten gustos)

Necesito que lo devuelvas en formato JSON y solo el JSON, sin texto agregado, limitándote a responder solo el JSON a utilizar.

El formato JSON debe ser exactamente:
[
  {{
    "name": "Nombre del juego",
    "appid": "ID_DEL_JUEGO",
    "steam_url": "https://store.steampowered.com/app/ID_DEL_JUEGO/",
    "reason": "Razón por la que se recomienda este juego (menciona similitudes con juegos que el usuario ya tiene)"
  }}
]

Juegos que el usuario YA TIENE (NO recomiendes ninguno de estos):
{games_json}"""

            logger.debug(f"[BOT] Enviando prompt a Gemini con modelo: {selected_model}")

            # Llamar a Gemini con el modelo seleccionado
            model = genai.GenerativeModel(selected_model)
            response = model.generate_content(prompt)

            logger.debug(f"[BOT] Respuesta de Gemini recibida")

            # Extraer el texto de la respuesta
            response_text = response.text.strip()

            # Limpiar la respuesta si viene con markdown
            if response_text.startswith("```json"):
                response_text = response_text[7:]  # Remover ```json
            if response_text.startswith("```"):
                response_text = response_text[3:]  # Remover ```
            if response_text.endswith("```"):
                response_text = response_text[:-3]  # Remover ```

            response_text = response_text.strip()

            logger.debug(f"[BOT] Respuesta limpiada: {response_text[:200]}...")

            # Parsear el JSON
            recommendations = json.loads(response_text)

            logger.info(f"[BOT] Se generaron {len(recommendations)} recomendaciones")

            # Crear embeds para cada recomendación con información de precios
            recommendation_embeds = []
            for i, rec in enumerate(recommendations, 1):
                game_name = rec.get('name', 'Juego desconocido')
                reason = rec.get('reason', 'Sin descripción')
                steam_url = rec.get('steam_url', '')

                logger.info(f"[BOT] Obteniendo precios para recomendación {i}: {game_name}")

                # Obtener información de precios del juego
                try:
                    price_data = await get_steam_game_prices(steam_url)

                    if price_data.get("success"):
                        # Crear embed con información de precios
                        rec_embed = discord.Embed(
                            title=f"🎮 Recomendación {i}: {game_name}",
                            description=f"**💡 Por qué te recomendamos este juego:**\n{reason}",
                            color=discord.Color.purple(),
                            url=price_data.get("game_url", steam_url)
                        )

                        # Agregar App ID
                        steam_app_id = price_data.get("steam_app_id", rec.get("appid", "N/A"))
                        rec_embed.add_field(name="Steam App ID", value=steam_app_id, inline=True)

                        # Mejor precio actual
                        current_best = price_data.get("current_best")
                        if current_best and current_best.get("price") is not None:
                            price = current_best["price"]
                            regular_price = current_best.get("regular_price")
                            cut = current_best.get("cut", 0)
                            shop = current_best.get("shop", "Unknown")
                            expiry = current_best.get("expiry", "")

                            price_text = f"**${price:.2f}**"
                            if regular_price:
                                price_text += f" ~~${regular_price:.2f}~~"
                            if cut > 0:
                                price_text += f" **(-{cut}%)**"
                            price_text += f"\n🏪 Tienda: {shop}"
                            if expiry:
                                price_text += f"\n⏰ Expira: {expiry[:10]}"

                            rec_embed.add_field(
                                name="💵 Mejor precio actual",
                                value=price_text,
                                inline=False
                            )

                        # Histórico de precios más bajos
                        history_low = price_data.get("history_low", {})
                        if history_low and "all_time" in history_low:
                            all_time = history_low["all_time"]
                            if all_time.get("price") is not None:
                                price = all_time["price"]
                                cut = all_time.get("cut", 0)
                                shop = all_time.get("shop", "Unknown")
                                recorded = all_time.get("recorded", "Unknown")

                                if recorded != "Unknown":
                                    try:
                                        recorded = recorded[:10]
                                    except:
                                        pass

                                history_text = f"**${price:.2f}**"
                                if cut > 0:
                                    history_text += f" **(-{cut}%)**"
                                history_text += f"\n🏪 Tienda: {shop}\n📅 Fecha: {recorded}"

                                rec_embed.add_field(
                                    name="🏆 Precio más bajo histórico",
                                    value=history_text,
                                    inline=False
                                )

                        rec_embed.set_footer(text=f"Gemini {selected_model} • Precios por IsThereAnyDeal.com")

                    else:
                        # Si no se pudieron obtener precios, crear embed básico
                        logger.warning(f"[BOT] No se pudieron obtener precios para {game_name}")
                        rec_embed = discord.Embed(
                            title=f"🎮 Recomendación {i}: {game_name}",
                            description=f"**💡 Por qué te recomendamos este juego:**\n{reason}",
                            color=discord.Color.purple(),
                            url=steam_url
                        )
                        rec_embed.add_field(
                            name="ℹ️ Información",
                            value="No se pudo obtener información de precios para este juego.",
                            inline=False
                        )
                        rec_embed.set_footer(text=f"Gemini {selected_model} • {username}")

                    recommendation_embeds.append(rec_embed)

                except Exception as e:
                    logger.error(f"[BOT] Error al obtener precios para {game_name}: {e}")
                    # Crear embed básico sin precios
                    rec_embed = discord.Embed(
                        title=f"🎮 Recomendación {i}: {game_name}",
                        description=f"**💡 Por qué te recomendamos este juego:**\n{reason}",
                        color=discord.Color.purple(),
                        url=steam_url
                    )
                    rec_embed.add_field(
                        name="ℹ️ Información",
                        value="No se pudo obtener información de precios para este juego.",
                        inline=False
                    )
                    rec_embed.set_footer(text=f"Gemini {selected_model} • {username}")
                    recommendation_embeds.append(rec_embed)

            # Agregar recomendaciones a todos los embeds
            if recommendation_embeds:
                all_embeds.extend(recommendation_embeds[:5])  # Limitar a 5 como se solicitó
                logger.info(f"[BOT] {len(recommendation_embeds)} recomendaciones con precios preparadas")
            else:
                logger.warning("[BOT] No se generaron recomendaciones")

            # Enviar TODO junto en un solo mensaje
            await interaction.followup.send(
                content=f"🤖 **Recomendaciones de juegos basadas en tu biblioteca:**\n*Modelo utilizado: {selected_model}*",
                embeds=all_embeds  # Biblioteca + recomendaciones
            )
            logger.info(f"[BOT] Comando /get-recommendations completado con modelo {selected_model}: enviados {len(all_embeds)} embeds para {username}")

        except json.JSONDecodeError as e:
            logger.error(f"[BOT] Error al parsear JSON de Gemini: {e}")
            logger.error(f"[BOT] Respuesta recibida: {response_text}")
            # Enviar al menos la biblioteca si falla el parseo
            await interaction.followup.send(
                content="⚠️ Se generaron recomendaciones pero hubo un error al procesarlas.",
                embeds=[embed]
            )
        except Exception as e:
            logger.error(f"[BOT] Error al generar recomendaciones con Gemini: {e}", exc_info=True)
            # Enviar al menos la biblioteca si falla Gemini
            await interaction.followup.send(
                content="⚠️ No se pudieron generar recomendaciones en este momento.",
                embeds=[embed]
            )

    except Exception as e:
        logger.error(f"[BOT] Error en comando /get-recommendations: {e}", exc_info=True)
        embed = discord.Embed(
            title="❌ Error inesperado",
            description=f"Ocurrió un error al procesar la solicitud: {str(e)}",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed)

if __name__ == '__main__':
    if not TOKEN:
        logger.error("No se encontró el token del bot en las variables de entorno.")
    else:
        bot.run(TOKEN)
