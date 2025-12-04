import discord
from discord import app_commands
from discord.ext import commands
import os
import logging
from dotenv import load_dotenv
from utils.itad_client import get_steam_game_prices
from utils.steam_client import get_user_library
from utils.steamdb_client import extract_steam_app_id_from_url, get_steamdb_price_history, analyze_price_data, get_steam_sales_calendar
import json
import google.generativeai as genai
import re
import io

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

# Vista con botón para descargar JSON del historial de precios
class DownloadHistoryView(discord.ui.View):
    def __init__(self, price_data: dict, analysis: dict, appid: str, cc: str, sales_calendar: dict = None):
        super().__init__(timeout=300)  # 5 minutos de timeout
        self.price_data = price_data
        self.analysis = analysis
        self.appid = appid
        self.cc = cc
        self.sales_calendar = sales_calendar

    @discord.ui.button(label="📥 Descargar JSON Completo", style=discord.ButtonStyle.primary, custom_id="download_json")
    async def download_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # Crear JSON con formato estructurado
            history_json = {
                "appid": self.appid,
                "country": self.cc.upper(),
                "statistics": {
                    "total_records": self.analysis['total_records'],
                    "min_price": self.analysis['min_price'],
                    "max_price": self.analysis['max_price'],
                    "current_price": self.analysis['current_price'],
                    "current_discount": self.analysis['current_discount'],
                    "currency": self.analysis['currency']
                },
                "steam_sales": self.sales_calendar if self.sales_calendar else {
                    "success": False,
                    "message": "Sales information not available"
                },
                "offers": self.analysis['offers'],
                "raw_data": self.price_data
            }

            # Convertir a JSON con formato bonito
            json_content = json.dumps(history_json, indent=2, ensure_ascii=False)

            # Crear archivo en memoria usando BytesIO
            json_bytes = io.BytesIO(json_content.encode('utf-8'))
            json_file = discord.File(
                fp=json_bytes,
                filename=f"steamdb_history_{self.appid}_{self.cc}.json"
            )

            # Enviar archivo como respuesta
            await interaction.response.send_message(
                f"📊 **Historial completo de precios - App ID {self.appid}**\n"
                f"✅ Archivo JSON generado con éxito.",
                file=json_file,
                ephemeral=True  # Solo visible para quien presionó el botón
            )

            logger.info(f"[BOT] JSON descargado por {interaction.user} para App ID {self.appid}")

        except Exception as e:
            logger.error(f"[BOT] Error al generar JSON: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ Error al generar el archivo JSON. Por favor intenta nuevamente.",
                ephemeral=True
            )

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

async def analyze_game_purchase_with_gemini(history_json: dict, game_name: str, model_name: str = None) -> dict:
    """
    Analiza el historial de precios y ofertas con Gemini para recomendar si conviene comprar.

    Args:
        history_json: JSON completo con historial de precios y sales
        game_name: Nombre del juego
        model_name: Modelo de Gemini a usar (opcional, por defecto GEMINI_MODEL)

    Returns:
        dict con success, game_name, considerations, conclusion
    """
    if not GEMINI_API_KEY:
        logger.warning("[BOT] Gemini API Key no configurada, no se puede realizar análisis")
        return {"success": False, "error": "API Key no configurada"}

    selected_model = model_name if model_name else GEMINI_MODEL

    try:
        from datetime import datetime

        # Obtener fecha actual
        current_date = datetime.now().strftime("%Y-%m-%d")

        # Crear prompt según especificaciones
        prompt = f"""En base al siguiente JSON necesito que analices las próximas fechas en las que el juego va a estar en oferta, considerando que la fecha actual es {current_date} y que me digas si me conviene o no me conviene comprar el juego ahora.

Para recomendar si conviene o no, necesitarás basarte en:
1. Si actualmente tiene una oferta (en cuyo caso SÍ conviene comprarlo ahora)
2. Si NO tiene una oferta, revisar cuál es la próxima sale más cercana:
   - Si es un plazo mayor a 1 mes: conviene comprarlo ahora dado el motivo de que falta mucho para la próxima oferta
   - Si el plazo es menor a 1 mes: conviene esperar dado que dentro de no mucho va a haber una oferta

IMPORTANTE:
- Analiza tanto el historial de ofertas (offers) como las Steam Sales próximas (steam_sales)
- Considera el precio actual vs el precio mínimo histórico
- Considera el descuento actual si existe
- Debes proporcionar entre 3 y 5 consideraciones relevantes

Debes retornar SOLO un JSON con el siguiente formato, sin texto adicional ni markdown:

{{
  "game_name": "{game_name}",
  "considerations": [
    "Primera consideración relevante",
    "Segunda consideración relevante",
    "Tercera consideración relevante"
  ],
  "conclusion": "conviene"
}}

Nota: El campo "conclusion" debe ser exactamente "conviene" o "no conviene" (en minúsculas).

El JSON con los datos del juego es el siguiente:
{json.dumps(history_json, indent=2, ensure_ascii=False)}"""

        logger.info(f"[BOT] Iniciando análisis Gemini para {game_name} con modelo {selected_model}")
        logger.debug(f"[BOT] Tamaño del prompt: {len(prompt)} caracteres")

        # Llamar a Gemini
        model = genai.GenerativeModel(selected_model)
        response = model.generate_content(prompt)

        logger.debug(f"[BOT] Respuesta de Gemini recibida")

        # Extraer y limpiar respuesta
        response_text = response.text.strip()

        # Limpiar markdown si viene con ```json
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]

        response_text = response_text.strip()

        logger.debug(f"[BOT] Respuesta limpiada: {response_text[:200]}...")

        # Parsear JSON
        analysis = json.loads(response_text)

        # Validar estructura
        required_fields = ['game_name', 'considerations', 'conclusion']
        if not all(field in analysis for field in required_fields):
            logger.error(f"[BOT] Respuesta de Gemini incompleta, faltan campos requeridos")
            return {"success": False, "error": "Respuesta incompleta"}

        # Validar tipos
        if not isinstance(analysis['considerations'], list) or len(analysis['considerations']) == 0:
            logger.error(f"[BOT] Consideraciones inválidas en respuesta de Gemini")
            return {"success": False, "error": "Consideraciones inválidas"}

        # Normalizar conclusión
        conclusion_lower = analysis['conclusion'].lower().strip()
        if conclusion_lower not in ['conviene', 'no conviene']:
            logger.error(f"[BOT] Conclusión inválida: {analysis['conclusion']}")
            return {"success": False, "error": "Conclusión inválida"}

        analysis['conclusion'] = conclusion_lower

        logger.info(f"[BOT] Análisis Gemini completado: {analysis['conclusion']}")

        return {
            "success": True,
            "game_name": analysis['game_name'],
            "considerations": analysis['considerations'],
            "conclusion": analysis['conclusion']
        }

    except json.JSONDecodeError as e:
        logger.error(f"[BOT] Error al parsear JSON de Gemini: {e}")
        logger.error(f"[BOT] Respuesta recibida: {response_text[:500]}")
        return {"success": False, "error": "Error al parsear respuesta"}

    except Exception as e:
        logger.error(f"[BOT] Error en análisis Gemini: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

@app_commands.allowed_installs(guilds=True, users=False)
@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
@bot.tree.command(
    name="should-buy",
    description="Obtiene el historial de ofertas de un juego de Steam desde SteamDB"
)
@app_commands.describe(
    url="URL del juego en Steam (e.g., https://store.steampowered.com/app/1627720/)",
    country="Código de país para precios (opcional, por defecto: ar para Argentina)",
    model="Modelo de Gemini para análisis (opcional, por defecto usa el del .env)"
)
@app_commands.choices(
    country=[
        app_commands.Choice(name="Argentina (ARS)", value="ar"),
        app_commands.Choice(name="Estados Unidos (USD)", value="us"),
        app_commands.Choice(name="Brasil (BRL)", value="br"),
        app_commands.Choice(name="Europa (EUR)", value="eu"),
        app_commands.Choice(name="Reino Unido (GBP)", value="gb"),
    ],
    model=[
        app_commands.Choice(name="Gemini 2.5 Pro (Más potente)", value="gemini-2.5-pro"),
        app_commands.Choice(name="Gemini 2.5 Flash (Equilibrado)", value="gemini-2.5-flash"),
        app_commands.Choice(name="Gemini 2.5 Flash Lite (Rápido y económico)", value="gemini-2.5-flash-lite"),
        app_commands.Choice(name="Gemini 2.0 Flash (Estable)", value="gemini-2.0-flash"),
        app_commands.Choice(name="Gemini 2.0 Flash Experimental", value="gemini-2.0-flash-exp"),
        app_commands.Choice(name="Gemini 2.0 Flash Lite", value="gemini-2.0-flash-lite"),
        app_commands.Choice(name="LearnLM 2.0 Flash Experimental", value="learnlm-2.0-flash-experimental")
    ]
)
async def should_buy(interaction: discord.Interaction, url: str, country: app_commands.Choice[str] = None, model: app_commands.Choice[str] = None):
    # Determinar código de país y modelo
    cc = country.value if country else "ar"
    selected_model = model.value if model else GEMINI_MODEL
    logger.info(f"[BOT] Comando /should-buy ejecutado por {interaction.user} con URL: {url}, país: {cc} y modelo: {selected_model}")

    # Defer la respuesta
    await interaction.response.defer(thinking=True)

    try:
        # Extraer Steam App ID de la URL
        appid = extract_steam_app_id_from_url(url)

        if not appid:
            logger.warning(f"[BOT] No se pudo extraer App ID de la URL: {url}")
            await interaction.followup.send(
                "❌ URL inválida. Debe ser una URL de Steam Store:\n"
                "- Formato: `https://store.steampowered.com/app/APPID/nombre_del_juego/`\n"
                "- Ejemplo: `https://store.steampowered.com/app/1627720/Lies_of_P/`"
            )
            return

        logger.info(f"[BOT] App ID extraído: {appid}")

        # Obtener historial de precios de SteamDB
        price_data = await get_steamdb_price_history(appid, cc)

        if not price_data or not price_data.get('success'):
            logger.error(f"[BOT] No se pudieron obtener datos de SteamDB para App ID: {appid}")
            embed = discord.Embed(
                title="❌ Error al obtener historial de precios",
                description=f"No se pudo obtener el historial de precios desde SteamDB para el juego.\n\n"
                           f"**App ID:** {appid}\n"
                           f"**País:** {cc.upper()}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)
            return

        # Analizar los datos
        analysis = analyze_price_data(price_data, cc)

        if not analysis:
            logger.error(f"[BOT] Error al analizar datos de precios")
            await interaction.followup.send("❌ Error al analizar el historial de precios.")
            return

        logger.info(f"[BOT] Análisis completado: {analysis['total_records']} registros")

        # Obtener información de sales activas y próximas
        logger.info(f"[BOT] Obteniendo información de Steam Sales...")
        sales_calendar = await get_steam_sales_calendar()

        # Generar JSON completo para análisis Gemini
        full_history_json = {
            "appid": appid,
            "country": cc.upper(),
            "statistics": {
                "total_records": analysis.get('total_records', 0),
                "min_price": analysis.get('min_price', 0),
                "max_price": analysis.get('max_price', 0),
                "current_price": analysis.get('current_price', 0),
                "current_discount": analysis.get('current_discount', 0),
                "currency": analysis.get('currency', 'N/A')
            },
            "steam_sales": sales_calendar if sales_calendar else {
                "success": False,
                "message": "Sales information not available"
            },
            "offers": analysis.get('offers', []),
            "raw_data": price_data if price_data else {}
        }

        # Realizar análisis con Gemini si está disponible
        gemini_analysis = None
        analysis_time = None
        if GEMINI_API_KEY:
            try:
                import time
                game_name = price_data.get('game_name', f'App ID {appid}')
                logger.info(f"[BOT] Iniciando análisis Gemini para: {game_name}")

                # Medir tiempo de análisis
                start_time = time.time()
                gemini_analysis = await analyze_game_purchase_with_gemini(
                    full_history_json,
                    game_name,
                    selected_model
                )
                end_time = time.time()
                analysis_time = end_time - start_time

                if gemini_analysis and gemini_analysis.get('success'):
                    logger.info(f"[BOT] Análisis Gemini completado exitosamente en {analysis_time:.2f}s")
                else:
                    logger.warning(f"[BOT] Análisis Gemini falló: {gemini_analysis.get('error', 'Unknown error')}")
            except Exception as e:
                logger.error(f"[BOT] Error al ejecutar análisis Gemini: {e}", exc_info=True)
                gemini_analysis = None
                analysis_time = None

        # Crear embed principal
        embed = discord.Embed(
            title=f"💰 Historial de Ofertas - App ID {appid}",
            description=f"Análisis de precios desde SteamDB",
            color=discord.Color.green(),
            url=f"https://steamdb.info/app/{appid}/"
        )

        # Estadísticas generales
        stats_text = f"**Precio actual:** {analysis['current_price_formatted']}"
        if analysis['current_discount'] > 0:
            stats_text += f" **(-{analysis['current_discount']}%)**"
        stats_text += f"\n**Precio mínimo histórico:** {analysis['currency']} {analysis['min_price']:.2f}"
        stats_text += f"\n**Precio máximo histórico:** {analysis['currency']} {analysis['max_price']:.2f}"
        stats_text += f"\n**Total de cambios de precio:** {analysis['total_records']}"

        embed.add_field(
            name="📊 Estadísticas",
            value=stats_text,
            inline=False
        )

        # Filtrar solo las ofertas (descuentos)
        discounts = [offer for offer in analysis['offers'] if offer['is_discount']]

        if discounts:
            # Mostrar TODAS las ofertas con rangos de fechas
            offers_text = ""
            field_count = 0

            for i, offer in enumerate(discounts, 1):
                date_from = offer['date']
                date_to = offer['date_end']
                price = offer['price_formatted']
                discount = offer['discount']
                event = offer['event']

                # Formato: fecha_inicio → fecha_fin: precio (descuento)
                line = f"**{i}.** `{date_from}` → `{date_to}`\n"
                line += f"   💰 {price} **(-{discount}%)**"
                if event:
                    line += f"\n   🎉 *{event}*"
                line += "\n\n"

                # Discord tiene límite de 1024 caracteres por field
                # Si agregar esta línea excede el límite, crear un nuevo field
                if len(offers_text) + len(line) > 950:
                    field_count += 1
                    embed.add_field(
                        name=f"🏷️ Historial de Ofertas (Parte {field_count})",
                        value=offers_text,
                        inline=False
                    )
                    offers_text = line
                else:
                    offers_text += line

            # Agregar cualquier texto restante
            if offers_text:
                if field_count > 0:
                    # Si ya hay partes, esta es la última parte
                    embed.add_field(
                        name=f"🏷️ Historial de Ofertas (Parte {field_count + 1})",
                        value=offers_text,
                        inline=False
                    )
                else:
                    # Si no hay partes, es el único field
                    embed.add_field(
                        name=f"🏷️ Historial de Ofertas ({len(discounts)} ofertas encontradas)",
                        value=offers_text,
                        inline=False
                    )
        else:
            embed.add_field(
                name="🏷️ Ofertas",
                value="No se encontraron ofertas para este juego.",
                inline=False
            )

        # Información de Steam Sales
        if sales_calendar and sales_calendar.get('success'):
            sales_text = ""

            # Countdown de próxima sale
            if sales_calendar.get('has_countdown'):
                countdown = sales_calendar['next_sale_countdown']
                if countdown and countdown.get('text'):
                    sales_text += f"⏱️ **Próxima Sale:** {countdown['text']}\n\n"

            # Sales activas
            if sales_calendar.get('has_current_sales'):
                sales_text += "🟢 **Sales Activas:**\n"
                for sale in sales_calendar['current_sales'][:3]:  # Mostrar máximo 3
                    sales_text += f"• {sale['name']}\n"
                    if sale.get('end'):
                        sales_text += f"  ⏰ Termina: {sale['end']}\n"

            # Sales próximas
            if sales_calendar.get('has_upcoming_sales'):
                if sales_text:
                    sales_text += "\n"
                sales_text += "🔵 **Próximas Sales:**\n"
                for sale in sales_calendar['upcoming_sales'][:3]:  # Mostrar máximo 3
                    sales_text += f"• {sale['name']}\n"
                    if sale.get('date'):
                        sales_text += f"  📅 {sale['date']}\n"

            if not sales_text:
                sales_text = "ℹ️ No hay información de sales disponible."

            embed.add_field(
                name="🎉 Steam Sales",
                value=sales_text,
                inline=False
            )

        # Recomendación (con análisis Gemini si disponible)
        if gemini_analysis and gemini_analysis.get('success'):
            # Usar análisis de Gemini - formato simplificado
            considerations = "\n".join([f"• {c}" for c in gemini_analysis['considerations']])
            conclusion_emoji = "✅" if gemini_analysis['conclusion'] == 'conviene' else "⏳"

            # Construir mensaje limpio
            recommendation = f"{considerations}\n\n"
            recommendation += f"{conclusion_emoji} **Conclusión:** "
            if gemini_analysis['conclusion'] == 'conviene':
                recommendation += f"**Conviene** comprar {gemini_analysis['game_name']} ahora."
            else:
                recommendation += f"**No conviene** comprar {gemini_analysis['game_name']} ahora."

            # Agregar información del modelo y tiempo
            recommendation += f"\n\n_Modelo: {selected_model} • Tiempo de análisis: {analysis_time:.2f}s_"
        else:
            # Fallback a recomendación básica
            if analysis['current_discount'] > 0:
                recommendation = f"✅ **¡Hay una oferta activa de {analysis['current_discount']}%!**\n"
                if analysis['current_price'] <= analysis['min_price']:
                    recommendation += "💎 **Este es el precio más bajo histórico. ¡Es un buen momento para comprar!**"
                else:
                    diff = analysis['current_price'] - analysis['min_price']
                    recommendation += f"⚠️ El precio más bajo fue {analysis['currency']} {analysis['min_price']:.2f} ({analysis['currency']} {diff:.2f} menos que ahora)."
            else:
                recommendation = f"⏳ **No hay ofertas activas actualmente.**\n"
                recommendation += f"El último precio más bajo fue {analysis['currency']} {analysis['min_price']:.2f}."

        embed.add_field(
            name="💡 Recomendación",
            value=recommendation,
            inline=False
        )

        # Footer
        embed.set_footer(text=f"Datos de SteamDB • País: {cc.upper()}")

        # Crear vista con botón de descarga
        view = DownloadHistoryView(price_data, analysis, appid, cc, sales_calendar)

        await interaction.followup.send(embed=embed, view=view)
        logger.info(f"[BOT] Comando /should-buy completado exitosamente para App ID {appid}")

    except Exception as e:
        logger.error(f"[BOT] Error en comando /should-buy: {e}", exc_info=True)
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
