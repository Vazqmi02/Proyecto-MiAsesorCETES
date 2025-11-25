import json
from openai import OpenAI

def handle_tool_calls(tool_calls):
    """
    Maneja las llamadas a herramientas (tools) del modelo.
    Por ahora retorna respuestas vacías, pero puedes expandir esta función
    para integrar APIs externas, bases de datos, etc.
    """
    results = []
    for tool_call in tool_calls:
        function_name = tool_call.function.name
        try:
            # Verificar que los argumentos no estén vacíos
            if not tool_call.function.arguments or tool_call.function.arguments.strip() == '':
                arguments = {}
            else:
                arguments = json.loads(tool_call.function.arguments)
        except (ValueError, json.JSONDecodeError) as e:
            print(f"Error al parsear argumentos de tool_call {function_name}: {e}")
            arguments = {}
        
        # Aquí puedes agregar lógica para diferentes herramientas
        # Por ejemplo: consultar APIs, bases de datos, hacer cálculos, etc.
        
        result = {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": json.dumps({"result": "Función ejecutada correctamente"})
        }
        results.append(result)
    
    return results

# Definición de herramientas disponibles para el modelo
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

