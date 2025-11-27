import json
from openai import OpenAI

def handle_tool_calls(tool_calls):
    results = []
    for tool_call in tool_calls:
        try:
            if not tool_call.function.arguments or tool_call.function.arguments.strip() == '':
                arguments = {}
            else:
                arguments = json.loads(tool_call.function.arguments)
        except (ValueError, json.JSONDecodeError):
            arguments = {}
        
        
        function_name = tool_call.function.name if hasattr(tool_call.function, 'name') else None
        
        if function_name == "calcular_rendimiento":
            # Obtener los parámetros
            monto = arguments.get("monto", 0)
            tasa = arguments.get("tasa", 0)  # Tasa anual en porcentaje
            plazo = arguments.get("plazo", 0)  # Plazo en días
            
            # Validar que todos los parámetros estén presentes
            if monto <= 0 or tasa <= 0 or plazo <= 0:
                resultado = {
                    "error": "Parámetros inválidos. El monto, tasa y plazo deben ser mayores a cero.",
                    "monto": monto,
                    "tasa": tasa,
                    "plazo": plazo
                }
            else:
                # Calcular el rendimiento: Interés simple
                # Fórmula: Rendimiento = Monto × (Tasa / 100) × (Plazo / 365)
                rendimiento = monto * (tasa / 100) * (plazo / 365)
                
                # Calcular el monto total al vencimiento
                monto_total = monto + rendimiento
                
                # Calcular la tasa efectiva anual (si se mantuviera la misma tasa)
                tasa_efectiva = tasa * (365 / plazo) if plazo < 365 else tasa
                
                resultado = {
                    "monto_invertido": f"${monto:,.2f} MXN",
                    "tasa_anual": f"{tasa:.2f}%",
                    "plazo": f"{plazo} días",
                    "rendimiento": f"${rendimiento:,.2f} MXN",
                    "monto_total_al_vencimiento": f"${monto_total:,.2f} MXN",
                    "tasa_efectiva_equivalente": f"{tasa_efectiva:.2f}%",
                    "explicacion": f"Por invertir ${monto:,.2f} MXN a una tasa del {tasa:.2f}% anual durante {plazo} días, obtendrás un rendimiento de ${rendimiento:,.2f} MXN. Al vencimiento recibirás ${monto_total:,.2f} MXN."
                }
            
            result = {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(resultado, ensure_ascii=False)
            }
        else:
            # Para funciones no implementadas
            result = {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps({
                    "error": f"Función '{function_name}' no está implementada aún"
                })
            }
        
        results.append(result)
    
    return results

tools = [
    {
        "type": "function",
        "function": {
            "name": "calcular_rendimiento",
            "description": "Calcula el rendimiento de una inversión en CETES usando interés simple. Retorna el rendimiento en pesos mexicanos, el monto total al vencimiento y la tasa efectiva equivalente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "monto": {
                        "type": "number",
                        "description": "Monto a invertir en pesos mexicanos (MXN)"
                    },
                    "tasa": {
                        "type": "number",
                        "description": "Tasa de interés anual en porcentaje (ej: 11.5 para 11.5%)"
                    },
                    "plazo": {
                        "type": "integer",
                        "description": "Plazo de la inversión en días (ej: 28, 91, 182, 364)"
                    }
                },
                "required": ["monto", "tasa", "plazo"]
            }
        }
    }
]