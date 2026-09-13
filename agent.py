import os
import re
import sys
import json
import time
import traceback
from google import genai
from google.genai import errors

API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("Falta la variable de entorno GEMINI_API_KEY")

client = genai.Client(api_key=API_KEY)
TASKS_FILE = "tasks.md"

# Presupuesto de caracteres para el contexto del codebase que se manda en el
# prompt. Sin este límite, get_codebase_context() concatena TODO el repo en
# cada iteración del while True, y ese contexto crece con cada tarea que se
# completa. Con el tiempo eso arma prompts cada vez más grandes que consumen
# la cuota por minuto/día mucho más rápido de lo esperado y aumentan el riesgo
# de respuestas truncadas. 350k caracteres (~90-100k tokens) deja margen
# amplio dentro de la ventana de 1M de gemini-3.6-flash.
MAX_CONTEXT_CHARS = 350_000

LANE = None
if len(sys.argv) > 1 and sys.argv[1].strip():
    LANE = sys.argv[1].strip().upper()
elif os.environ.get("AGENT_LANE"):
    LANE = os.environ["AGENT_LANE"].strip().upper()

if LANE:
    TASK_PATTERN = re.compile(r'- \[ \] \[' + re.escape(LANE) + r'\] (.*)')
else:
    TASK_PATTERN = re.compile(r'- \[ \] (.*)')


def get_codebase_context():
    context = ""
    for root, _, files in os.walk("."):
        if ".git" in root or "__pycache__" in root or "venv" in root:
            continue
        for file in files:
            if file.endswith(".py") and file != "agent.py":
                path = os.path.join(root, file)
                with open(path, "r", encoding="utf-8") as f:
                    context += f"\n--- {path} ---\n{f.read()}\n"

    if len(context) > MAX_CONTEXT_CHARS:
        print(
            f"⚠️ Contexto del codebase ({len(context)} caracteres) excede el "
            f"presupuesto de {MAX_CONTEXT_CHARS}; se trunca. Si esto empieza a "
            f"pasar seguido, es momento de particionar el contexto en vez de "
            f"mandar el repo completo en cada tarea."
        )
        context = context[:MAX_CONTEXT_CHARS] + "\n\n[...CONTEXTO TRUNCADO POR LÍMITE DE TAMAÑO...]"

    return context


def validate_file_content(filepath: str, content: str) -> str | None:
    """
    Validación previa a escribir un archivo generado por la IA. No reemplaza
    al agente verificador (eso ocurre después, sobre el Pull Request), pero
    atrapa gratis e inmediatamente sintaxis Python inválida o artefactos de
    generación truncada (comillas/llaves sueltas al final del archivo) —
    exactamente la clase de bug que rompió el build de Vercel.
    """
    if filepath.endswith(".py"):
        try:
            compile(content, filepath, "exec")
        except SyntaxError as e:
            return f"SyntaxError en {filepath}: {e}"

    stripped = content.rstrip()
    if stripped.endswith(('"', "'")) and not stripped.endswith(('"""', "'''")):
        return f"{filepath} termina sospechosamente en una comilla suelta: {stripped[-20:]!r}"

    return None


def call_gemini_with_retries(prompt: str, max_attempts: int = 3):
    """
    ANTES: una sola llamada; cualquier error (429, red, respuesta vacía, lo
    que sea) tumbaba el bucle con un `break` silencioso y el script terminaba
    con exit code 0. Por eso GitHub Actions mostraba ✅ verde en corridas
    donde el agente en realidad no había hecho absolutamente nada.

    AHORA: reintentamos con backoff SOLO errores que probablemente sean
    transitorios (5xx, problemas de red puntuales). Un 429 de cuota agotada
    NO se reintenta en el mismo run — si la cuota es diaria, esperar unos
    segundos no la libera — se relanza tal cual para que run_agent() decida
    terminar con un exit code distinto de 0.
    """
    last_exc = None
    for attempt in range(1, max_attempts + 1):
        try:
            return client.models.generate_content(
                model='gemini-3.6-flash',
                contents=prompt,
            )
        except errors.ClientError as e:
            if "429" in str(e):
                raise
            last_exc = e
            wait = 5 * attempt
            print(f"⚠️ Error de API (intento {attempt}/{max_attempts}): {e}")
            print(f"   Reintentando en {wait}s...")
            time.sleep(wait)
    raise last_exc


def run_agent():
    lane_label = LANE or "SIN_CARRIL"
    print(f"🤖 Iniciando Agente en Modo Bucle (carril: {lane_label})...")

    while True:
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            content = f.read()

        match = TASK_PATTERN.search(content)
        if not match:
            print(f"🎉 No hay más tareas pendientes en el carril '{lane_label}'. Apagando agente.")
            sys.exit(0)  # éxito legítimo: no queda trabajo pendiente

        current_task = match.group(1)
        full_line = match.group(0)
        print(f"\n🚀 Procesando [{lane_label}]: {current_task}")

        codebase_context = get_codebase_context()
        prompt = f"""
        Eres un Tech Lead autónomo desarrollando el backend de 'SplitPay' en FastAPI.
        SplitPay opera bajo una regla legal inamovible de "Cero Custodia": nunca
        almacenes saldos reales, proceses pagos internamente, ni implementes nada
        que sugiera que SplitPay retiene o mueve fondos. Solo calcula deudas y
        genera enlaces de pago hacia billeteras externas.

        Tu carril de trabajo asignado es: "{lane_label}". Evita tocar archivos que
        no correspondan a tu carril salvo que sea estrictamente necesario para
        completar la tarea.

        Tu tarea actual a ejecutar es: "{current_task}"

        Este es el estado actual del código (contexto):
        {codebase_context}

        Genera el código necesario para cumplir esta tarea.
        REGLA CRÍTICA: Tu respuesta debe ser ÚNICAMENTE un objeto JSON válido.
        - Las claves (keys) deben ser la ruta relativa del archivo (ej. 'main.py' o 'models/user.py').
        - Los valores (values) deben ser el código fuente COMPLETO de ese archivo, sin caracteres sueltos antes o después.
        - NO incluyas formato Markdown, no saludes, no expliques nada. Solo el JSON.
        """

        raw_json = None
        try:
            response = call_gemini_with_retries(prompt)

            if not response.text:
                feedback = getattr(response, "prompt_feedback", None)
                raise RuntimeError(
                    f"Gemini devolvió una respuesta vacía (posible bloqueo de "
                    f"seguridad / safety filter). prompt_feedback={feedback}"
                )

            raw_json = response.text.strip()
            if raw_json.startswith("```json"):
                raw_json = raw_json[7:]
            if raw_json.startswith("```"):
                raw_json = raw_json[3:]
            if raw_json.endswith("```"):
                raw_json = raw_json[:-3]

            files_to_update = json.loads(raw_json.strip())

            validation_errors = []
            for filepath, filecontent in files_to_update.items():
                error = validate_file_content(filepath, filecontent)
                if error:
                    validation_errors.append(error)

            if validation_errors:
                print("🛑 Validación de contenido falló, no se escribe nada de este lote:")
                for err in validation_errors:
                    print(f"   - {err}")
                print("La tarea no se marca como completa; se reintentará en el próximo ciclo.")
                sys.exit(1)  # ANTES: break (exit 0). Esto es una falla real y debe verse en CI.

            for filepath, filecontent in files_to_update.items():
                if filecontent is None:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                        print(f"🗑️ Archivo eliminado: {filepath}")
                    continue
                os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(filecontent)
                print(f"✅ Archivo actualizado/creado: {filepath}")

            new_content = content.replace(full_line, full_line.replace('[ ]', '[x]', 1), 1)
            with open(TASKS_FILE, "w", encoding="utf-8") as f:
                f.write(new_content)

            print("🏁 Tarea completada. Buscando la siguiente...")

        except json.JSONDecodeError:
            largo = len(raw_json) if raw_json is not None else 0
            print("⚠️ Error: la IA devolvió un JSON incompleto o inválido (posible corte por límite de tokens).")
            print(f"   Longitud de la respuesta cruda recibida: {largo} caracteres.")
            print("Deteniendo el bucle. La tarea no se marcó con [x] para que se reintente en el próximo ciclo.")
            sys.exit(1)  # ANTES: break (exit 0)

        except errors.ClientError as e:
            if "429" in str(e):
                print(
                    "🛑 Cuota gratuita agotada (Error 429). El agente se detiene ahora; "
                    "probablemente se recupere en la próxima corrida programada (cada 6h)."
                )
            else:
                print(f"❌ Error de la API de Gemini: {e}")
            sys.exit(1)  # ANTES: break (exit 0) — esto era lo que ocultaba el problema en CI

        except Exception as e:
            print(f"❌ Error inesperado: {e}")
            traceback.print_exc()
            sys.exit(1)  # ANTES: break (exit 0)


if __name__ == "__main__":
    run_agent()
