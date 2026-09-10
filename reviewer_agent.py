"""
Agente Verificador para SplitPay (backend). Revisa el PR de un agente de
carril cruzando señales objetivas (pytest, alembic) con una revisión
semántica hecha por un modelo de Gemini DISTINTO al que escribe el código
(gemini-2.0-flash en vez de gemini-3.6-flash), usando la cuota gratuita
independiente que Google asigna por modelo.
"""

import json
import os
import subprocess
import sys

from google import genai

REVIEWER_API_KEY = os.environ["REVIEWER_API_KEY"]
REVIEWER_MODEL = os.environ.get("REVIEWER_MODEL", "gemini-2.0-flash")

TESTS_PASSED = os.environ.get("TESTS_PASSED", "false").lower() == "true"
MIGRATIONS_PASSED = os.environ.get("MIGRATIONS_PASSED", "false").lower() == "true"
PR_NUMBER = os.environ["PR_NUMBER"]

MAX_AUTO_FIX_ATTEMPTS = 2

client = genai.Client(api_key=REVIEWER_API_KEY)

REVIEW_CHECKLIST = """
Actúa como Principal Engineer haciendo code review de un Pull Request para SplitPay,
una fintech colombiana de división de gastos entre roomies que opera bajo una regla
legal inamovible de "Cero Custodia": SplitPay NUNCA debe almacenar saldos reales,
procesar pagos internamente, ni tener custodia de dinero de los usuarios. Solo
calcula deudas (registros contables) y genera enlaces de pago hacia billeteras
externas (Nequi, Daviplata). Backend: Python, FastAPI, PostgreSQL, SQLAlchemy 2.0.

Revisa el diff adjunto exclusivamente por:
1. Violaciones al principio de Cero Custodia (cualquier código que sugiera retener,
   procesar o mover fondos reales, en vez de solo calcular y enlazar).
2. Bugs de lógica financiera: división por cero, mal manejo de ingresos None/negativos,
   redondeo de centavos, uso de `float` en vez de `Decimal`/`Numeric` para dinero.
3. Validaciones de entrada faltantes (pertenencia a un hogar, sumas de splits que no
   cuadran con el total, estados inválidos).
4. Migraciones de Alembic que editen retroactivamente un archivo de migración ya
   existente en vez de crear una migración nueva encadenada correctamente.
5. Secretos hardcodeados, valores por defecto inseguros, o falta de manejo de errores
   en llamadas a APIs externas.
6. Inconsistencias entre lo que un endpoint retorna y lo que sus schemas de Pydantic
   declaran.

Ignora estilo de código, nombres de variables o preferencias subjetivas: solo
correctitud e integridad de datos financieros y adherencia a Cero Custodia.

Responde ÚNICAMENTE con un objeto JSON con esta forma exacta, sin texto adicional,
sin backticks de Markdown:
{
  "veredicto": "aprobado" | "cambios_requeridos",
  "comentarios": ["hallazgo 1", "hallazgo 2"],
  "correcciones": {"ruta/al/archivo.py": "contenido COMPLETO corregido del archivo"}
}
El campo "correcciones" debe incluir ÚNICAMENTE archivos donde tengas alta confianza
en el arreglo exacto y completo. Si no aplica ninguna corrección directa, debe ser
un objeto vacío {}. Nunca dejes "correcciones" con un archivo a medio escribir.
"""


def run_git(*args: str) -> str:
    result = subprocess.run(["git", *args], capture_output=True, text=True, check=True)
    return result.stdout


def gh(*args: str) -> None:
    result = subprocess.run(["gh", *args], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"⚠️ Comando gh falló: {' '.join(args)}\n{result.stderr}")


def read_tail(path: str, max_chars: int) -> str:
    if not os.path.exists(path):
        return "(sin salida)"
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()[-max_chars:]


def count_previous_fix_attempts() -> int:
    log = subprocess.run(
        ["git", "log", "--oneline", "--grep=Corrección aplicada por el agente verificador"],
        capture_output=True, text=True,
    ).stdout
    return len([line for line in log.splitlines() if line.strip()])


def main() -> None:
    diff = read_tail("pr_diff.txt", 60_000)
    pytest_output = read_tail("pytest_output.txt", 4_000)
    alembic_output = read_tail("alembic_output.txt", 2_000)

    if not TESTS_PASSED or not MIGRATIONS_PASSED:
        comment = (
            "❌ **El agente verificador bloqueó este PR por señales objetivas.**\n\n"
            f"- `pytest`: {'✅ pasó' if TESTS_PASSED else '❌ falló'}\n"
            f"- `alembic upgrade head`: {'✅ pasó' if MIGRATIONS_PASSED else '❌ falló'}\n\n"
            f"<details><summary>Salida de pytest</summary>\n\n```\n{pytest_output}\n```\n</details>\n\n"
            f"<details><summary>Salida de alembic</summary>\n\n```\n{alembic_output}\n```\n</details>\n\n"
            "No se ejecutó la revisión semántica: una falla objetiva ya es motivo suficiente "
            "para no mergear. Corrige y sube cambios a esta misma rama; se volverá a revisar automáticamente."
        )
        gh("pr", "comment", PR_NUMBER, "--body", comment)
        print("Bloqueado por fallos objetivos. No se mergea.")
        sys.exit(0)

    fix_attempts = count_previous_fix_attempts()

    response = client.models.generate_content(
        model=REVIEWER_MODEL,
        contents=f"{REVIEW_CHECKLIST}\n\n--- DIFF DEL PULL REQUEST ---\n{diff}",
    )

    raw = response.text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]

    try:
        review = json.loads(raw.strip())
    except json.JSONDecodeError:
        gh("pr", "comment", PR_NUMBER, "--body",
           "⚠️ El agente verificador no pudo interpretar la respuesta del modelo revisor. "
           "Requiere revisión humana antes de mergear.")
        sys.exit(0)

    veredicto = review.get("veredicto")
    comentarios = review.get("comentarios", [])
    correcciones = review.get("correcciones", {})
    comentarios_md = "\n".join(f"- {c}" for c in comentarios) or "- Sin observaciones."

    if correcciones and fix_attempts >= MAX_AUTO_FIX_ATTEMPTS:
        gh("pr", "comment", PR_NUMBER, "--body",
           f"⚠️ El agente verificador ya intentó corregir este PR {fix_attempts} veces sin lograr "
           f"la aprobación. Se detienen las correcciones automáticas; requiere revisión humana.\n\n"
           f"Último diagnóstico del modelo:\n{comentarios_md}")
        sys.exit(0)

    if correcciones:
        for filepath, filecontent in correcciones.items():
            os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(filecontent)
        run_git("add", "-A")
        run_git("commit", "-m", "🤖 Corrección aplicada por el agente verificador")
        run_git("push")
        gh("pr", "comment", PR_NUMBER, "--body",
           f"🔧 **El agente verificador aplicó una corrección directa sobre esta rama.**\n\n{comentarios_md}\n\n"
           "Esto disparará un nuevo ciclo de pruebas y revisión automáticamente.")
        print("Corrección aplicada, se re-disparará la revisión al sincronizarse el PR.")
        sys.exit(0)

    if veredicto == "aprobado":
        gh("pr", "comment", PR_NUMBER, "--body", f"✅ **Aprobado por el agente verificador.**\n\n{comentarios_md}")
        gh("pr", "merge", PR_NUMBER, "--squash", "--delete-branch")
        print("PR aprobado y mergeado.")
    else:
        gh("pr", "comment", PR_NUMBER, "--body",
           f"🔧 **Cambios requeridos según el agente verificador.**\n\n{comentarios_md}\n\n"
           "No se mergeó automáticamente. El agente del carril correspondiente seguirá trabajando "
           "sobre esta misma rama en su próximo ciclo.")
        print("PR no mergeado, requiere atención.")


if __name__ == "__main__":
    main()
