import os
import re
import json
import google.generativeai as genai

# 1. Configuración de Gemini
API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("Falta la variable de entorno GEMINI_API_KEY")

genai.configure(api_key=API_KEY)
# Utilizamos la versión 1.5 Pro o 2.5 Flash según la disponibilidad en tu API Key
model = genai.GenerativeModel('gemini-1.5-pro-latest') 
TASKS_FILE = "tasks.md"

def get_codebase_context():
    """Lee los archivos Python actuales para darle contexto a la IA."""
    context = ""
    for root, _, files in os.walk("."):
        if ".git" in root or "__pycache__" in root or "venv" in root: 
            continue
        for file in files:
            if file.endswith(".py") and file != "agent.py":
                path = os.path.join(root, file)
                with open(path, "r", encoding="utf-8") as f:
                    context += f"\n--- {path} ---\n{f.read()}\n"
    return context

def run_agent():
    # 2. Leer el backlog
    with open(TASKS_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    # Buscar la primera tarea pendiente (líneas que empiezan con "- [ ]")
    match = re.search(r'- \[ \] (.*)', content)
    if not match:
        print("No hay tareas pendientes en tasks.md. Apagando agente.")
        return

    current_task = match.group(1)
    full_line = match.group(0)
    print(f"🚀 Iniciando tarea: {current_task}")

    # 3. Construir el Prompt
    context = get_codebase_context()
    prompt = f"""
    Eres un Tech Lead autónomo desarrollando el backend de 'SplitPay' en FastAPI.
    Tu tarea actual a ejecutar es: "{current_task}"
    
    Este es el estado actual del código (contexto):
    {context}
    
    Genera el código necesario para cumplir esta tarea. 
    REGLA CRÍTICA: Tu respuesta debe ser ÚNICAMENTE un objeto JSON válido. 
    - Las claves (keys) deben ser la ruta relativa del archivo (ej. 'main.py' o 'models/user.py').
    - Los valores (values) deben ser el código fuente COMPLETO de ese archivo.
    - NO incluyas formato Markdown (como ```json), no saludes, no expliques nada. Solo el JSON.
    """

    # 4. Llamar a la IA
    response = model.generate_content(prompt)
    
    try:
        # Limpiar posibles formateos residuales que la IA intente agregar
        raw_json = response.text.strip()
        if raw_json.startswith("```json"):
            raw_json = raw_json[7:]
        if raw_json.startswith("```"):
            raw_json = raw_json[3:]
        if raw_json.endswith("```"):
            raw_json = raw_json[:-3]
            
        files_to_update = json.loads(raw_json.strip())
        
        # 5. Escribir los archivos generados
        for filepath, filecontent in files_to_update.items():
            # Crear las carpetas si no existen (ej. schemas/)
            os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(filecontent)
            print(f"✅ Archivo actualizado/creado: {filepath}")
                
        # 6. Tachar la tarea en tasks.md
        new_content = content.replace(full_line, full_line.replace('[ ]', '[x]', 1), 1)
        with open(TASKS_FILE, "w", encoding="utf-8") as f:
            f.write(new_content)
            
        print("🏁 Tarea completada con éxito.")
        
    except json.JSONDecodeError:
        print("❌ Error: La respuesta de Gemini no fue un JSON válido.")
        print("Respuesta cruda recibida:\n", response.text)
    except Exception as e:
        print(f"❌ Error inesperado: {e}")

if __name__ == "__main__":
    run_agent()
