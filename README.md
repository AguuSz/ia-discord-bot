# 🎮 Steam Game Recommendations Bot

Bot de Discord con inteligencia artificial que analiza tu biblioteca de Steam y te recomienda juegos personalizados con información de precios en tiempo real.

## ✨ Características

- 🤖 **Recomendaciones con IA**: Utiliza Google Gemini AI para analizar tu biblioteca y sugerir juegos similares
- 💰 **Información de precios**: Obtiene precios actuales e históricos de IsThereAnyDeal.com
- 📊 **Estadísticas de biblioteca**: Visualiza tus juegos más jugados y estadísticas generales
- 🎯 **Modelos personalizables**: Elige entre 7 modelos diferentes de Gemini en tiempo de ejecución
- 🚀 **Respuesta unificada**: Todo en un solo mensaje con múltiples embeds visuales

## 🛠️ Tecnologías

- **Python 3.11+**
- **Discord.py** - Interacción con Discord API
- **Google Generative AI** - IA de recomendaciones
- **IsThereAnyDeal API** - Información de precios
- **Docker** - Contenerización

## 📋 Requisitos

- Docker y Docker Compose instalados
- Token de Discord Bot
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

### Obtener API Key de Gemini

1. Ve a [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Crea una nueva API Key
3. Copia la key a tu archivo `.env`

## 📖 Uso

### Comando Principal

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
/get-recommendations url:https://steamcommunity.com/id/Agus model:Gemini 2.5 Pro (Más potente)
```

**Respuesta del bot:**
1. 📊 Embed con tu biblioteca de Steam (total de juegos, horas jugadas, top 10)
2. 🎮 5 embeds con recomendaciones personalizadas que incluyen:
   - Nombre del juego
   - Razón de la recomendación (basada en tus gustos)
   - Mejor precio actual (tienda, descuento, expiración)
   - Precio más bajo histórico
   - Link directo a Steam Store

## 📁 Estructura del Proyecto

```
ia-bot-discord/
├── bot.py                      # Bot principal
├── requirements.txt            # Dependencias Python
├── Dockerfile                  # Configuración Docker
├── docker-compose.yml          # Orquestación Docker
├── .env                        # Variables de entorno (no versionado)
├── README.md                   # Este archivo
├── urls.md                     # Documentación de URLs válidas
├── mock_data/
│   └── steam_libraries.json    # Datos mock de usuarios
└── utils/
    ├── __init__.py
    └── itad_client.py          # Cliente para IsThereAnyDeal API
```

## 🎯 Usuarios Mock Disponibles

El bot utiliza datos mock para demostración. Usuarios disponibles:

- `Agus` (100 juegos)
- `usuario1` - `usuario9` (50-76 juegos cada uno)

Para más detalles, consulta [urls.md](urls.md)

## 🔧 Desarrollo

### Agregar nuevos usuarios mock

Edita el archivo `mock_data/steam_libraries.json`:

```json
{
  "nuevo_usuario": {
    "games": [
      {
        "appid": 730,
        "name": "Counter-Strike 2",
        "playtime_hours": 250
      }
    ]
  }
}
```

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

### Recomendaciones incorrectas

1. El bot usa datos mock, no la biblioteca real de Steam
2. Los juegos recomendados son generados por IA y pueden variar
3. Prueba con diferentes modelos de Gemini para comparar resultados

## 📝 Notas

- Los datos de usuarios son **simulados** (mock), no se consulta la API real de Steam
- Las recomendaciones son generadas por **IA** y pueden variar entre ejecuciones
- Los **precios** son reales y se obtienen en tiempo real de IsThereAnyDeal.com
- El bot muestra "IA Bot is thinking..." mientras procesa (puede tomar 10-30 segundos)

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
