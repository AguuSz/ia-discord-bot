# 🎮 Steam Game Recommendations Bot

Bot de Discord con inteligencia artificial que analiza tu biblioteca de Steam y te recomienda juegos personalizados con información de precios en tiempo real.

## ✨ Características

- 🎮 **Integración con Steam API**: Obtiene tu biblioteca real de Steam en tiempo real
- 🤖 **Recomendaciones con IA**: Utiliza Google Gemini AI para analizar tu biblioteca y sugerir juegos similares
- 💰 **Información de precios**: Obtiene precios actuales e históricos de IsThereAnyDeal.com
- 📊 **Estadísticas de biblioteca**: Visualiza tus juegos más jugados y estadísticas generales
- 🎯 **Modelos personalizables**: Elige entre 7 modelos diferentes de Gemini en tiempo de ejecución
- 🚀 **Respuesta unificada**: Todo en un solo mensaje con múltiples embeds visuales
- 🏷️ **Historial de ofertas**: Consulta el historial completo de precios y ofertas desde SteamDB

## 🛠️ Tecnologías

- **Python 3.11+**
- **Discord.py** - Interacción con Discord API
- **Steam Web API** - Obtención de bibliotecas de juegos
- **Google Generative AI** - IA de recomendaciones
- **IsThereAnyDeal API** - Información de precios
- **Docker** - Contenerización

## 📋 Requisitos

- Docker y Docker Compose instalados
- Token de Discord Bot
- Steam API Key
- API Key de Google Gemini
- Python 3.11+ (si se ejecuta sin Docker)

## 🚀 Instalación

### Con Docker (Recomendado)

1. **Clona el repositorio**
```bash
git clone <url-del-repositorio>
cd ia-bot-discord
```

2. **Configura las variables de entorno**
```bash
cp .env.example .env
```

Edita el archivo `.env` con tus credenciales:
```env
DISCORD_TOKEN=tu_token_de_discord
STEAM_API_KEY=tu_steam_api_key
GEMINI_API_KEY=tu_api_key_de_gemini
GEMINI_MODEL=gemini-2.5-flash-lite
```

3. **Construye y ejecuta el contenedor**
```bash
docker-compose up -d
```

4. **Verifica los logs**
```bash
docker-compose logs -f
```

### Sin Docker

1. **Instala las dependencias**
```bash
pip install -r requirements.txt
```

2. **Configura el archivo `.env`** (igual que arriba)

3. **Ejecuta el bot**
```bash
python bot.py
```

## ⚙️ Configuración

### Obtener Token de Discord

1. Ve a [Discord Developer Portal](https://discord.com/developers/applications)
2. Crea una nueva aplicación
3. En la sección "Bot", crea un bot y copia el token
4. Habilita los siguientes intents:
   - Message Content Intent
   - Server Members Intent (opcional)
5. Invita el bot a tu servidor con los permisos:
   - Send Messages
   - Embed Links
   - Attach Files
   - Use Slash Commands

### Obtener Steam API Key

1. Ve a [Steam Web API Key](https://steamcommunity.com/dev/apikey)
2. Inicia sesión con tu cuenta de Steam
3. Registra tu dominio (puedes usar `localhost` para desarrollo)
4. Copia la API Key a tu archivo `.env`

**Nota:** El perfil de Steam del usuario debe ser **público** para que el bot pueda acceder a su biblioteca de juegos.

### Obtener API Key de Gemini

1. Ve a [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Crea una nueva API Key
3. Copia la key a tu archivo `.env`

## 📖 Uso

### Comandos Disponibles

#### 1. `/get-recommendations` - Recomendaciones personalizadas

```
/get-recommendations url:https://steamcommunity.com/id/USERNAME [model:opcional]
```

**Parámetros:**
- `url` (obligatorio): URL del perfil de Steam (formato: `https://steamcommunity.com/id/USERNAME`)
- `model` (opcional): Modelo de Gemini a utilizar

**Modelos disponibles:**
- Gemini 2.5 Pro (Más potente)
- Gemini 2.5 Flash (Equilibrado)
- Gemini 2.5 Flash Lite (Rápido y económico) - **Por defecto**
- Gemini 2.0 Flash (Estable)
- Gemini 2.0 Flash Experimental
- Gemini 2.0 Flash Lite
- LearnLM 2.0 Flash Experimental

### Ejemplo

```
/get-recommendations url:https://steamcommunity.com/id/tu_usuario model:Gemini 2.5 Pro (Más potente)
```

O con Steam ID numérico:
```
/get-recommendations url:https://steamcommunity.com/profiles/76561198183693995
```

**Respuesta del bot:**
1. 📊 Embed con tu biblioteca de Steam (total de juegos, horas jugadas, top 10)
2. 🎮 5 embeds con recomendaciones personalizadas que incluyen:
   - Nombre del juego
   - Razón de la recomendación (basada en tus gustos)
   - Mejor precio actual (tienda, descuento, expiración)
   - Precio más bajo histórico
   - Link directo a Steam Store

**Importante:** El perfil de Steam debe ser público para que el bot pueda acceder a la biblioteca.

---

#### 2. `/should-buy` - Historial de ofertas

```
/should-buy url:https://store.steampowered.com/app/1627720/ [country:opcional]
```

**Parámetros:**
- `url` (obligatorio): URL del juego en Steam Store
- `country` (opcional): País para precios (Argentina, Estados Unidos, Brasil, Europa, Reino Unido)

**Países disponibles:**
- Argentina (ARS) - **Por defecto**
- Estados Unidos (USD)
- Brasil (BRL)
- Europa (EUR)
- Reino Unido (GBP)

**Ejemplo:**

```
/should-buy url:https://store.steampowered.com/app/1627720/Lies_of_P/ country:Argentina (ARS)
```

**Respuesta del bot:**
- 📊 Estadísticas de precios (actual, mínimo, máximo)
- 🏷️ **Historial completo de ofertas** con rangos de fechas (desde → hasta)
  - Muestra todas las ofertas históricas, no solo las últimas
  - Cada oferta incluye: fecha inicio, fecha fin, precio y descuento
  - Si hay eventos de Steam (como "Summer Sale"), se muestran también
- 🎉 **Steam Sales** (información en tiempo real)
  - Sales activas actualmente en Steam
  - Próximas sales programadas con fechas
- 💡 Recomendación de compra basada en historial
- 🔗 Link directo a SteamDB
- 📥 **Botón de descarga** para obtener el historial completo en formato JSON

**Formato de visualización:**
```
1. 01/12/2024 → 15/12/2024
   💰 ARS$ 13,499.00 (-50%)
   🎉 Autumn Sale 2024

2. 20/11/2024 → 30/11/2024
   💰 ARS$ 15,999.00 (-40%)
```

**Descarga de JSON:**

Al presionar el botón "📥 Descargar JSON Completo", recibirás un archivo JSON con:
- App ID del juego
- País y moneda utilizados
- Estadísticas completas (precios mínimo, máximo, actual)
- Array completo de todas las ofertas con fechas exactas
- Datos raw de SteamDB para análisis avanzado

**Estructura del JSON:**
```json
{
  "appid": "1627720",
  "country": "AR",
  "statistics": {
    "total_records": 25,
    "min_price": 13499.00,
    "max_price": 26599.00,
    "current_price": 18599.00,
    "current_discount": 30,
    "currency": "ARS$"
  },
  "steam_sales": {
    "success": true,
    "current_sales": [
      {
        "name": "Winter Sale 2024",
        "start": "19 Dec 2024",
        "end": "2 Jan 2025"
      }
    ],
    "upcoming_sales": [
      {
        "name": "Spring Sale 2025",
        "date": "20 Mar 2025"
      }
    ],
    "has_current_sales": true,
    "has_upcoming_sales": true
  },
  "offers": [
    {
      "date": "01/12/2024",
      "date_end": "15/12/2024",
      "price": 13499.00,
      "price_formatted": "ARS$ 13,499.00",
      "discount": 50,
      "event": "Autumn Sale 2024",
      "is_discount": true
    }
  ],
  "raw_data": { ... }
}
```

**Notas:**
- Este comando utiliza web scraping de SteamDB y puede tardar 15-30 segundos (scrapea dos páginas: historial de precios y calendario de sales)
- Si hay muchas ofertas, se dividirán en múltiples secciones para cumplir con los límites de Discord
- El botón de descarga está disponible por 5 minutos después de ejecutar el comando
- El archivo JSON descargado es privado (solo visible para quien presionó el botón)
- La información de Steam Sales es actualizada en tiempo real desde SteamDB

## 📁 Estructura del Proyecto

```
ia-bot-discord/
├── bot.py                      # Bot principal
├── requirements.txt            # Dependencias Python
├── Dockerfile                  # Configuración Docker
├── docker-compose.yml          # Orquestación Docker
├── .env                        # Variables de entorno (no versionado)
├── .env.example                # Plantilla de variables de entorno
├── .gitignore                  # Archivos a ignorar en git
├── README.md                   # Este archivo
└── utils/
    ├── __init__.py
    ├── steam_client.py         # Cliente para Steam Web API
    ├── itad_client.py          # Cliente para IsThereAnyDeal API
    └── steamdb_client.py       # Cliente para SteamDB (web scraping)
```

## 🔧 Desarrollo

### Logs

Para ver los logs del bot en Docker:

```bash
docker-compose logs -f
```

### Reiniciar el bot

```bash
docker-compose restart
```

### Detener el bot

```bash
docker-compose down
```

## 🐛 Troubleshooting

### El bot no responde

1. Verifica que el token de Discord sea correcto en `.env`
2. Asegúrate de que el bot tenga permisos de slash commands en el servidor
3. Revisa los logs: `docker-compose logs -f`

### Error de API de Gemini

1. Verifica que tu API Key sea válida
2. Comprueba que tengas cuota disponible en Google AI Studio
3. Prueba con un modelo diferente (algunos requieren acceso especial)

### No se pueden obtener los juegos

1. Verifica que el perfil de Steam sea **público**
2. Comprueba que la Steam API Key sea válida
3. Asegúrate de que la URL del perfil sea correcta
4. Algunos perfiles pueden tener la biblioteca privada en la configuración de privacidad

### Recomendaciones incorrectas

1. Los juegos recomendados son generados por IA y pueden variar
2. Prueba con diferentes modelos de Gemini para comparar resultados
3. La IA se basa en tus horas jugadas para identificar tus preferencias

## 📝 Notas

- Los datos de usuarios son **reales** obtenidos de Steam Web API
- Las recomendaciones son generadas por **IA** y pueden variar entre ejecuciones
- Los **precios** son reales y se obtienen en tiempo real de IsThereAnyDeal.com
- El bot muestra "IA Bot is thinking..." mientras procesa (puede tomar 10-40 segundos)
- **Importante:** El perfil de Steam debe ser público para acceder a la biblioteca
- El comando `/should-buy` usa **Playwright** para web scraping de SteamDB
  - Requiere instalación adicional: `playwright install chromium` (se hace automáticamente en Docker)
  - Bypasea protección de Cloudflare usando navegador real en modo headless

## 🤝 Contribuciones

Las contribuciones son bienvenidas. Por favor:

1. Haz fork del proyecto
2. Crea una rama para tu feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit tus cambios (`git commit -m 'Agrega nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Abre un Pull Request

## 📄 Licencia

Este proyecto es de código abierto y está disponible bajo la licencia MIT.

## 👤 Autor

Desarrollado con ❤️ usando Claude Code

---

**¿Necesitas ayuda?** Abre un issue en el repositorio o consulta la documentación de:
- [Discord.py](https://discordpy.readthedocs.io/)
- [Google Gemini API](https://ai.google.dev/docs)
- [IsThereAnyDeal API](https://docs.isthereanydeal.com/)
