"""
gemini_client.py — cliente de Gemini pensado para la cuota GRATUITA.

Qué resuelve (todo basado en errores reales vistos en los logs de GitHub Actions):
  * 503 "high demand"  -> el modelo está saturado: se reintenta una vez y luego se
                          pasa al siguiente modelo (insistir sobre el mismo no sirve).
  * 429                -> se lee el detalle que manda Google: si es cuota DIARIA se
                          descarta ese modelo por el resto de la corrida (esperar 65 s
                          no sirve); si es por MINUTO se espera el tiempo que Google indica.
  * 404 "no longer available to new users" -> el modelo ya no existe para esta llave:
                          se descarta de inmediato, sin reintentos ni esperas.
  * Los nombres de modelo NO están escritos a mano: se le pregunta a la API qué modelos
    Flash ve esta llave y se ordenan del más capaz al más liviano (Flash-Lite al final,
    que tiene una cuota gratuita mucho mayor).
  * Admite hasta dos llaves (GEMINI_API_KEY y GEMINI_API_KEY_2). Si pertenecen a
    proyectos distintos de Google, la cuota es independiente y se duplica la capacidad.
  * Todo queda en el log con flush inmediato, incluyendo el detalle real de los 429.
"""

import json
import os
import random
import re
import time

from google import genai
from google.genai import errors, types

# Solo se usa si la API no deja listar modelos.
STATIC_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
]
# Solo alias estables: sin -preview, -exp, -image, -tts, -live, etc.
MODEL_RE = re.compile(r"^gemini-(\d+(?:\.\d+)*)-flash(-lite)?$")

REQUEST_TIMEOUT_MS = 240_000


def log(*args):
    print(*args, flush=True)


class AllModelsFailed(Exception):
    """Ninguna combinación (llave, modelo) pudo responder."""

    def __init__(self, summary, all_daily=False, fatal=False):
        super().__init__(summary)
        self.summary = summary
        self.all_daily = all_daily  # cuota diaria agotada en todo: reintentar mañana
        self.fatal = fatal  # llave inválida / ningún modelo disponible


def order_models(names):
    """Flash completos primero (versión más nueva primero), Flash-Lite después."""
    found = []
    for name in names:
        short = name.split("/")[-1]
        m = MODEL_RE.match(short)
        if m:
            version = tuple(int(x) for x in m.group(1).split("."))
            found.append((bool(m.group(2)), tuple(-v for v in version), short))
    found.sort()
    ordered = []
    for _, _, short in found:
        if short not in ordered:
            ordered.append(short)
    return ordered


def parse_quota_error(exc):
    """
    Devuelve (tipo, segundos_de_espera_sugeridos, texto_diagnostico).
    tipo: 'daily' | 'minute' | 'unknown'.
    """
    details = getattr(exc, "details", None)
    kind, delay = "unknown", None
    ids = []
    try:
        err = details.get("error", details) if isinstance(details, dict) else {}
        for item in err.get("details", []) or []:
            t = str(item.get("@type", ""))
            if t.endswith("QuotaFailure"):
                for v in item.get("violations", []) or []:
                    ids.append(f"{v.get('quotaId', '')} {v.get('quotaMetric', '')}")
            if t.endswith("RetryInfo"):
                m = re.match(r"^\s*([\d.]+)s", str(item.get("retryDelay", "")))
                if m:
                    delay = float(m.group(1))
    except Exception:
        pass

    blob = " ".join(ids).lower().replace("_", "")
    message = str(getattr(exc, "message", "") or exc).lower()
    if "perday" in blob or "daily" in blob or "per day" in message:
        kind = "daily"
    elif "perminute" in blob or "per minute" in message:
        kind = "minute"

    if delay is None:
        m = re.search(r"retry in ([\d.]+)s", message)
        if m:
            delay = float(m.group(1))

    diag = ("; ".join(i.strip() for i in ids if i.strip()) or str(getattr(exc, "message", ""))[:200])
    return kind, delay, diag


def classify(exc):
    """'quota' | 'transient' | 'dead' | 'badkey'."""
    code = getattr(exc, "code", None)
    text = str(exc).lower()
    if code == 429:
        return "quota"
    if code in (500, 502, 503, 504, 408):
        return "transient"
    if code == 400 and ("api key not valid" in text or "api_key_invalid" in text):
        return "badkey"
    if code in (400, 401, 403, 404):
        return "dead"
    return "transient"


def make_client(api_key):
    try:
        opts = types.HttpOptions(
            timeout=REQUEST_TIMEOUT_MS,
            retry_options=types.HttpRetryOptions(attempts=1),  # los reintentos los hacemos nosotros
        )
        return genai.Client(api_key=api_key, http_options=opts)
    except Exception:
        return genai.Client(api_key=api_key)


class GeminiPool:
    def __init__(self, api_keys, models=None, sleep=time.sleep, client_factory=make_client):
        keys = []
        for k in api_keys:
            k = (k or "").strip()
            if k and k not in keys:
                keys.append(k)
        if not keys:
            raise ValueError("No hay ninguna llave: define GEMINI_API_KEY.")
        self.clients = [client_factory(k) for k in keys]
        self.sleep = sleep
        self.models = list(models) if models else None
        self.state = {}  # (idx_llave, modelo) -> 'dead' | 'daily'
        self.stats = {}  # modelo -> {'ok': n, 'fail': n}
        self.last_error = {}

    # ---------- descubrimiento ----------
    def discover(self):
        override = os.environ.get("GEMINI_MODELS", "").strip()
        if override:
            self.models = [m.strip() for m in override.split(",") if m.strip()]
            log(f"ℹ️ Modelos fijados por GEMINI_MODELS: {self.models}")
            return self.models
        if self.models:
            return self.models
        for idx, client in enumerate(self.clients):
            try:
                names = []
                for m in client.models.list():
                    actions = getattr(m, "supported_actions", None)
                    if actions is not None and "generateContent" not in actions:
                        continue
                    names.append(m.name)
                gemini = sorted({n.split("/")[-1] for n in names if "gemini" in n})
                log(f"ℹ️ Modelos Gemini visibles para la llave #{idx + 1}: {gemini[:40]}")
                ordered = order_models(names)
                if ordered:
                    self.models = ordered
                    log(f"ℹ️ Orden de uso: {self.models}")
                    return self.models
            except Exception as e:
                log(f"⚠️ No se pudo listar modelos con la llave #{idx + 1}: {type(e).__name__}: {str(e)[:160]}")
        self.models = list(STATIC_MODELS)
        log(f"ℹ️ Usando la lista fija de modelos: {self.models}")
        return self.models

    # ---------- llamada ----------
    def _bump(self, model, field):
        self.stats.setdefault(model, {"ok": 0, "fail": 0})[field] += 1

    def _try(self, idx, model, prompt):
        """Intenta una combinación. Devuelve texto, o None (y deja estado/descripción)."""
        tag = f"{model}|llave#{idx + 1}"
        for attempt in (1, 2):
            try:
                resp = self.clients[idx].models.generate_content(model=model, contents=prompt)
                text = getattr(resp, "text", None)
                if not text or not text.strip():
                    self.last_error[(idx, model)] = "respuesta vacía (posible filtro de seguridad)"
                    log(f"⚠️ [{tag}] respuesta vacía; se prueba otro modelo.")
                    self._bump(model, "fail")
                    return None
                self._bump(model, "ok")
                return text
            except Exception as e:  # APIError y errores de red
                kind = classify(e) if isinstance(e, errors.APIError) else "transient"
                code = getattr(e, "code", type(e).__name__)
                self.last_error[(idx, model)] = f"{code}: {str(e)[:160]}"
                self._bump(model, "fail")

                if kind == "badkey":
                    log(f"❌ [{tag}] la llave no es válida: {str(e)[:160]}")
                    for m in self.models:
                        self.state[(idx, m)] = "dead"
                    return None
                if kind == "dead":
                    log(f"🚫 [{tag}] no disponible ({code}): {str(e)[:200]} -> se descarta.")
                    self.state[(idx, model)] = "dead"
                    return None
                if kind == "quota":
                    qkind, delay, diag = parse_quota_error(e)
                    log(f"⚠️ [{tag}] 429 tipo={qkind} espera_sugerida={delay} detalle={diag}")
                    if qkind == "daily":
                        self.state[(idx, model)] = "daily"
                        return None
                    if qkind == "minute" and delay is not None and delay <= 45 and attempt == 1:
                        log(f"   Esperando {delay + 1:.0f}s y reintentando el mismo modelo.")
                        self.sleep(delay + 1)
                        continue
                    return None  # se vuelve a intentar en la siguiente pasada
                # transitorio (503 y similares)
                log(f"⚠️ [{tag}] error transitorio ({code}): {str(e)[:160]}")
                if attempt == 1:
                    wait = 10 + random.random() * 5
                    log(f"   Reintentando una vez en {wait:.0f}s...")
                    self.sleep(wait)
                    continue
                return None
        return None

    def generate(self, prompt, max_passes=3, max_seconds=None):
        if self.models is None:
            self.discover()
        if max_seconds is None:
            max_seconds = int(os.environ.get("GEMINI_MAX_SECONDS", "720"))
        deadline = time.monotonic() + max_seconds
        combos = [(i, m) for m in self.models for i in range(len(self.clients))]
        for pass_no in range(1, max_passes + 1):
            remaining = [c for c in combos if self.state.get(c) not in ("dead", "daily")]
            if not remaining:
                break
            for idx, model in remaining:
                if self.state.get((idx, model)) in ("dead", "daily"):
                    continue
                if time.monotonic() > deadline:
                    log(f"⏱️ Se alcanzó el tope de {max_seconds}s para esta solicitud; se detienen los intentos.")
                    break
                text = self._try(idx, model, prompt)
                if text is not None:
                    if (idx, model) != combos[0]:
                        log(f"ℹ️ Respondió {model} (llave #{idx + 1}).")
                    return text
            if time.monotonic() > deadline:
                break
            still = [c for c in combos if self.state.get(c) not in ("dead", "daily")]
            if still and pass_no < max_passes:
                wait = 60 * pass_no
                log(f"🔁 Pasada {pass_no}/{max_passes} sin éxito; esperando {wait}s antes de repetir.")
                self.sleep(wait)

        states = [self.state.get(c) for c in combos]
        dead = sum(1 for s in states if s == "dead")
        daily = sum(1 for s in states if s == "daily")
        all_daily = daily > 0 and dead + daily == len(combos)
        fatal = dead == len(combos)
        lines = [f"{m} (llave #{i + 1}): {self.state.get((i, m)) or 'sin respuesta'} - {self.last_error.get((i, m), '')}"
                 for i, m in combos]
        raise AllModelsFailed("\n".join(lines), all_daily=all_daily, fatal=fatal)

    def usage_summary(self):
        return {m: dict(v) for m, v in self.stats.items()}
