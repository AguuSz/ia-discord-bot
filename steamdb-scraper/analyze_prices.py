import json
from datetime import datetime


def convert_to_sales_format(json_file, game_id=None, released_date=None):
    """
    Convierte el historial de precios al formato solicitado.

    Args:
        json_file: Ruta al archivo JSON con los datos de SteamDB
        game_id: ID del juego (opcional, se extrae del nombre del archivo)
        released_date: Fecha de lanzamiento en formato DD/MM/YYYY (opcional)

    Returns:
        dict: Datos en el formato solicitado
    """
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if not data.get('success'):
        print("[!] La respuesta no fue exitosa")
        return None

    history = data['data']['history']

    # Extraer game_id del nombre del archivo si no se proporciona
    if game_id is None:
        import re
        match = re.search(r'price_history_(\d+)_', json_file)
        if match:
            game_id = int(match.group(1))
        else:
            game_id = None

    # Agrupar períodos de precio
    sales = []
    sale_id = 1

    for i in range(len(history)):
        current = history[i]
        current_date = datetime.fromtimestamp(current['x'] / 1000)
        current_price = current['y']

        # Determinar la fecha "to" (hasta cuando dura este precio)
        if i < len(history) - 1:
            next_item = history[i + 1]
            to_date = datetime.fromtimestamp(next_item['x'] / 1000)
        else:
            # Si es el último, usar la fecha actual
            to_date = datetime.now()

        sales.append({
            "id": sale_id,
            "since": current_date.strftime("%d/%m/%Y"),
            "to": to_date.strftime("%d/%m/%Y"),
            "price": current_price
        })
        sale_id += 1

    # Construir el objeto final
    result = {
        "gameID": game_id,
        "released": released_date,
        "sales": sales
    }

    return result


def analyze_price_history(json_file):
    """Analiza y muestra el historial de precios de forma legible"""

    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if not data.get('success'):
        print("[!] La respuesta no fue exitosa")
        return

    history = data['data']['history']
    sales_events = data['data'].get('sales', {})

    print("=" * 80)
    print("ANÁLISIS DE HISTORIAL DE PRECIOS - Marvel's Spider-Man 2 (Argentina)")
    print("=" * 80)

    # Estadísticas básicas
    prices = [item['y'] for item in history]
    print(f"\nESTADISTICAS:")
    print(f"  - Total de registros: {len(history)}")
    print(f"  - Precio minimo: ${min(prices):.2f}")
    print(f"  - Precio maximo: ${max(prices):.2f}")
    print(f"  - Precio actual: {history[-1]['f']}")
    print(f"  - Descuento actual: {history[-1]['d']}%")

    # Eventos de venta
    print(f"\nEVENTOS DE VENTA:")
    if sales_events:
        for timestamp, event_name in sales_events.items():
            date = datetime.fromtimestamp(int(timestamp) / 1000)
            print(f"  - {event_name}: {date.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print("  - No hay eventos de venta registrados")

    # Historial detallado
    print(f"\nHISTORIAL DETALLADO:")
    print(f"{'Fecha':<20} {'Precio':<12} {'Descuento':<12} {'Evento'}")
    print("-" * 80)

    for item in history:
        timestamp = item['x']
        date = datetime.fromtimestamp(timestamp / 1000)
        date_str = date.strftime('%Y-%m-%d %H:%M:%S')
        price = item['f']
        discount = f"{item['d']}%" if item['d'] > 0 else "-"

        # Buscar si hay un evento en esta fecha
        event = sales_events.get(str(timestamp), "")

        print(f"{date_str:<20} {price:<12} {discount:<12} {event}")

    # Análisis de tendencias
    print(f"\nTENDENCIA:")
    if len(history) >= 2:
        first_price = history[0]['y']
        last_price = history[-1]['y']
        change = last_price - first_price
        change_pct = (change / first_price) * 100

        if change > 0:
            print(f"  - El precio ha AUMENTADO ${abs(change):.2f} ({abs(change_pct):.1f}%) desde el primer registro")
        elif change < 0:
            print(f"  - El precio ha DISMINUIDO ${abs(change):.2f} ({abs(change_pct):.1f}%) desde el primer registro")
        else:
            print(f"  - El precio se ha mantenido ESTABLE")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    input_file = "price_history_2651280_ar.json"
    output_file = "formatted_sales.json"

    # Mostrar análisis en consola
    print("Generando analisis...")
    analyze_price_history(input_file)

    # Generar JSON en formato solicitado
    print("\n" + "=" * 80)
    print("GENERANDO JSON EN FORMATO SOLICITADO...")
    print("=" * 80)

    # Puedes especificar la fecha de lanzamiento manualmente o dejarla en None
    formatted_data = convert_to_sales_format(
        input_file,
        game_id=2651280,  # Se auto-detecta del nombre del archivo
        released_date=None  # Puedes poner "19/01/2024" por ejemplo
    )

    if formatted_data:
        # Guardar el JSON formateado
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(formatted_data, f, indent=2, ensure_ascii=False)

        print(f"\n[+] JSON generado y guardado en: {output_file}")
        print("\nPreview del JSON generado:")
        print(json.dumps(formatted_data, indent=2, ensure_ascii=False))
