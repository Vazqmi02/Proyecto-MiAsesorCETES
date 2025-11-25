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
        
        result = {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": json.dumps({"result": "Función ejecutada correctamente"})
        }
        results.append(result)
    
    return results

tools = [
    {
        "type": "function",
        "function": {
            "name": "calcular_rendimiento",
            "description": "Calcula el rendimiento de una inversión en CETES",
            "parameters": {
                "type": "object",
                "properties": {
                    "monto": {
                        "type": "number",
                        "description": "Monto a invertir"
                    },
                    "tasa": {
                        "type": "number",
                        "description": "Tasa de interés anual"
                    },
                    "plazo": {
                        "type": "integer",
                        "description": "Plazo en días"
                    }
                },
                "required": ["monto", "tasa", "plazo"]
            }
        }
    }
]
