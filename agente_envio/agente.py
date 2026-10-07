"""Agente que llena la solicitud en el portal simulado.

Dos modos con el mismo resultado:
- computer_use: Claude ve capturas del navegador y decide clics y texto (herramienta computer_toolset_20260801).
  Las contraseñas las escribe el robot sin mostrarlas al modelo, y el último clic requiere confirmación humana.
- guion: respaldo con pasos fijos de Playwright (sin IA).

En ambos, antes de "Firmar y enviar" se llama a `confirmar(captura_png, resumen)`, que bloquea hasta que una
persona confirma o cancela en la app.
"""
import base64
import json
import time

import anthropic

MODELO = "claude-opus-5-5"
ANCHO, ALTO = 1280, 800
MAX_PASOS = 60
PRECIO = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0)}   # USD por millón de tokens (entrada, salida)

TECLAS = {"return": "Enter", "enter": "Enter", "tab": "Tab", "escape": "Escape", "esc": "Escape", "backspace": "Backspace",
          "delete": "Delete", "space": " ", "up": "ArrowUp", "down": "ArrowDown", "left": "ArrowLeft", "right": "ArrowRight",
          "page_down": "PageDown", "page_up": "PageUp", "home": "Home", "end": "End", "ctrl": "Control", "control": "Control",
          "shift": "Shift", "alt": "Alt", "cmd": "Meta", "super": "Meta"}


def _tecla(combo):
    return "+".join(TECLAS.get(p.lower(), p if len(p) > 1 else p) for p in combo.split("+"))


class Resultado(dict):
    pass


# ----------------------------------------------------------------------------------------------- modo guion
def enviar_con_guion(page, env, solicitud, zips, confirmar):
    t0 = time.time()
    page.goto(env["PORTAL_URL"])
    page.fill("#usuario", env["PORTAL_USUARIO"]); page.fill("#contrasena", env["PORTAL_PASSWORD"])
    page.click("#btn-entrar")
    page.click("#btn-nueva")
    page.select_option("#homoclave", solicitud["homoclave"])
    page.fill("#denominacion", solicitud["denominacion"])
    page.select_option("#tipo_producto", solicitud["tipo_producto"])
    page.fill("#referencia", solicitud["tramite_id"])
    page.click("#btn-continuar")
    for m, z in zips.items():
        page.set_input_files(f"#archivo-{m}", str(z))
        page.click(f"#btn-cargar-{m}")
    page.click("#btn-revisar")
    decision = confirmar(page.screenshot(), "Solicitud llenada con pasos fijos (respaldo sin IA): 5 módulos cargados.")
    if decision != "CONFIRMADO":
        return Resultado(exito=False, nota="Cancelado por el usuario", pasos=0, segundos=round(time.time() - t0, 1))
    page.fill("#contrasena_efirma", env["PORTAL_EFIRMA_PASSWORD"])
    page.check("#acepto")
    page.click("#btn-firmar-enviar")
    folio = page.inner_text("#folio").strip()
    return Resultado(exito=True, folio=folio, cadena=page.inner_text("#cadena").strip(), acuse=page.screenshot(),
                     pasos=0, segundos=round(time.time() - t0, 1), costo_usd=0.0, nota="Modo guion")


# ----------------------------------------------------------------------------------------------- modo computer use
HERRAMIENTAS = [
    {"type": "computer_toolset_20260801"},
    {"name": "escribir_credencial", "strict": True,
     "description": "Escribe una credencial en el campo que tiene el foco. Úsala SIEMPRE para contraseñas o usuario: "
                    "primero haz clic en el campo y luego llama esta herramienta. Nunca escribas credenciales con 'type'.",
     "input_schema": {"type": "object", "additionalProperties": False, "required": ["credencial"],
                      "properties": {"credencial": {"type": "string",
                                                    "enum": ["usuario_portal", "contrasena_portal", "contrasena_efirma"]}}}},
    {"name": "adjuntar_modulo", "strict": True,
     "description": "Adjunta el archivo ZIP del módulo CTD indicado al selector de archivo de ese módulo en la página de "
                    "documentos (equivale a elegir el archivo en el diálogo). Después debes pulsar el botón 'Cargar' de ese módulo.",
     "input_schema": {"type": "object", "additionalProperties": False, "required": ["modulo"],
                      "properties": {"modulo": {"type": "string", "enum": ["m1", "m2", "m3", "m4", "m5"]}}}},
    {"name": "solicitar_confirmacion", "strict": True,
     "description": "Pide a una persona que confirme el envío. Llámala cuando estés en la página de firma, con los 5 "
                    "módulos cargados, ANTES de escribir la contraseña de la e.firma o pulsar 'Firmar y enviar'. "
                    "Devuelve CONFIRMADO o CANCELADO.",
     "input_schema": {"type": "object", "additionalProperties": False, "required": ["resumen"],
                      "properties": {"resumen": {"type": "string",
                                                 "description": "Qué se va a enviar: trámite, producto y módulos cargados."}}}},
    {"name": "reportar_resultado", "strict": True,
     "description": "Termina la tarea. Llámala al ver el acuse (con el folio) o si no fue posible completar el envío.",
     "input_schema": {"type": "object", "additionalProperties": False, "required": ["exito", "folio", "nota"],
                      "properties": {"exito": {"type": "boolean"}, "folio": {"type": "string"}, "nota": {"type": "string"}}}},
]

SISTEMA = """Eres el agente de envíos regulatorios de Laboratorios Altamira (empresa ficticia). Operas un navegador ya abierto en un portal de trámites SIMULADO para una demostración. Tu tarea es presentar una solicitud de trámite.

Pasos:
1. Inicia sesión: clic en el campo Usuario y usa escribir_credencial(usuario_portal); clic en Contraseña y usa escribir_credencial(contrasena_portal); pulsa Entrar.
2. Crea una nueva solicitud con los datos indicados y continúa.
3. En la página de documentos, para cada módulo m1 a m5: llama adjuntar_modulo(mX) y pulsa el botón 'Cargar' de ese módulo. Verifica en la pantalla que aparezca el nombre del archivo.
4. Continúa a firma y envío. Revisa que estén los 5 módulos.
5. Llama solicitar_confirmacion con un resumen. Si responde CANCELADO, llama reportar_resultado(exito=false) y termina.
6. Solo si responde CONFIRMADO: clic en el campo de la contraseña de e.firma, escribir_credencial(contrasena_efirma), marca la casilla de la declaración y pulsa 'Firmar y enviar solicitud'.
7. En el acuse, lee el folio y llama reportar_resultado(exito=true, folio=...).

Reglas: nunca pulses 'Firmar y enviar' sin CONFIRMADO; no escribas contraseñas con la acción 'type'; no salgas del portal; si algo falla, reintenta una vez y si no, reporta el problema. Trabaja con pocas capturas: toma una después de cada cambio de página."""


def enviar_con_computer_use(page, env, solicitud, zips, confirmar, registrar=print):
    cliente = anthropic.Anthropic(api_key=env["ANTHROPIC_API_KEY"])
    page.goto(env["PORTAL_URL"])
    t0 = time.time()
    tarea = (f"Presenta esta solicitud. Trámite (homoclave): {solicitud['homoclave']}. Denominación: {solicitud['denominacion']}. "
             f"Tipo de medicamento: {solicitud['tipo_producto']}. Referencia interna: {solicitud['tramite_id']}. "
             f"El navegador muestra {env['PORTAL_URL']} con una ventana de {ANCHO}x{ALTO} píxeles.")
    mensajes = [{"role": "user", "content": tarea}]
    tokens_in = tokens_out = pasos = 0
    resultado = None
    while pasos < MAX_PASOS and resultado is None:
        resp = cliente.beta.messages.create(
            model=MODELO, max_tokens=16000, system=SISTEMA, tools=HERRAMIENTAS, messages=mensajes,
            thinking={"type": "adaptive"}, output_config={"effort": "medium"},
            betas=["server-side-fallback-2026-07-01"], extra_body={"fallbacks": "default"})
        tokens_in += resp.usage.input_tokens + (resp.usage.cache_read_input_tokens or 0)
        tokens_out += resp.usage.output_tokens
        mensajes.append({"role": "assistant", "content": resp.content})   # se agrega tal cual (sin editar el historial)
        if resp.stop_reason == "refusal":
            resultado = Resultado(exito=False, nota=f"El modelo declinó la tarea ({resp.stop_details})")
            break
        usos = [b for b in resp.content if b.type == "tool_use"]
        if not usos:
            resultado = Resultado(exito=False, nota="El agente terminó sin reportar resultado")
            break
        resultados, fallo = [], False
        for b in usos:
            pasos += 1
            es_pc = getattr(b, "toolset_name", None) == "computer"
            base = {"type": "tool_result", "tool_use_id": b.id}
            if es_pc:
                base["toolset_name"] = "computer"
            if fallo and es_pc:
                resultados.append({**base, "is_error": True, "content": "Not executed: an earlier computer action in this turn failed."})
                continue
            try:
                contenido = _ejecutar(page, b.name, b.input, env, zips, confirmar)
                registrar(f"    paso {pasos}: {b.name} {json.dumps(b.input, ensure_ascii=False)[:90] if b.name != 'escribir_credencial' else b.input}")
                if isinstance(contenido, Resultado):
                    resultado = contenido
                    contenido = "Registrado."
                resultados.append({**base, "content": contenido})
            except Exception as e:
                fallo = es_pc
                resultados.append({**base, "is_error": True, "content": f"Error: {e}"})
        mensajes.append({"role": "user", "content": resultados})
    costo = tokens_in / 1e6 * PRECIO.get(MODELO, (4, 20))[0] + tokens_out / 1e6 * PRECIO.get(MODELO, (4, 20))[1]
    resultado = resultado or Resultado(exito=False, nota=f"Se alcanzó el máximo de {MAX_PASOS} pasos")
    resultado.update(pasos=pasos, segundos=round(time.time() - t0, 1), costo_usd=round(costo, 3),
                     tokens_entrada=tokens_in, tokens_salida=tokens_out, acuse=page.screenshot())
    if resultado.get("exito"):
        try:
            resultado["cadena"] = page.inner_text("#cadena").strip()
        except Exception:
            resultado["cadena"] = ""
    return resultado


def _png(page):
    return [{"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                         "data": base64.b64encode(page.screenshot()).decode()}}]


def _ejecutar(page, nombre, x, env, zips, confirmar):
    m = page.mouse
    if nombre == "screenshot":
        return _png(page)
    if nombre == "zoom":
        x0, y0, x1, y1 = x["region"]
        return [{"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64.b64encode(
            page.screenshot(clip={"x": x0, "y": y0, "width": max(1, x1 - x0), "height": max(1, y1 - y0)})).decode()}}]
    if nombre in ("left_click", "right_click", "middle_click", "double_click", "triple_click"):
        if x.get("coordinate"):
            m.move(*x["coordinate"])
        boton = {"right_click": "right", "middle_click": "middle"}.get(nombre, "left")
        veces = {"double_click": 2, "triple_click": 3}.get(nombre, 1)
        mods = [_tecla(t) for t in x.get("text", "").split("+") if t] if x.get("text") else []
        for k in mods:
            page.keyboard.down(k)
        pos = x.get("coordinate")
        if pos:
            m.click(*pos, button=boton, click_count=veces)
        else:
            m.down(button=boton); m.up(button=boton)
        for k in mods:
            page.keyboard.up(k)
        page.wait_for_load_state()
        return "OK"
    if nombre == "mouse_move":
        m.move(*x["coordinate"]); return "OK"
    if nombre == "left_click_drag":
        m.move(*x["start_coordinate"]); m.down(); m.move(*x["coordinate"]); m.up(); return "OK"
    if nombre == "left_mouse_down":
        m.down(); return "OK"
    if nombre == "left_mouse_up":
        m.up(); return "OK"
    if nombre == "cursor_position":
        return "Posición no disponible en este entorno"
    if nombre == "type":
        page.keyboard.type(x["text"], delay=15); return "OK"
    if nombre == "key":
        for _ in range(int(x.get("repeat", 1) or 1)):
            page.keyboard.press(_tecla(x["text"]))
        page.wait_for_load_state()
        return "OK"
    if nombre == "hold_key":
        k = _tecla(x["text"]); page.keyboard.down(k); time.sleep(min(float(x.get("duration", 1)), 5)); page.keyboard.up(k)
        return "OK"
    if nombre == "scroll":
        if x.get("coordinate"):
            m.move(*x["coordinate"])
        d = int(x.get("scroll_amount", 3)) * 100
        dx, dy = {"up": (0, -d), "down": (0, d), "left": (-d, 0), "right": (d, 0)}[x["scroll_direction"]]
        m.wheel(dx, dy); return "OK"
    if nombre == "wait":
        time.sleep(min(float(x.get("duration", 1)), 10)); return "OK"
    # herramientas propias
    if nombre == "escribir_credencial":
        clave = {"usuario_portal": "PORTAL_USUARIO", "contrasena_portal": "PORTAL_PASSWORD",
                 "contrasena_efirma": "PORTAL_EFIRMA_PASSWORD"}[x["credencial"]]
        page.keyboard.type(env[clave], delay=15)
        return "Credencial escrita en el campo con foco (valor no mostrado)."
    if nombre == "adjuntar_modulo":
        page.set_input_files(f"#archivo-{x['modulo']}", str(zips[x["modulo"]]))
        return f"Archivo {zips[x['modulo']].name} adjuntado al selector del módulo {x['modulo']}. Ahora pulsa 'Cargar'."
    if nombre == "solicitar_confirmacion":
        return confirmar(page.screenshot(), x["resumen"])
    if nombre == "reportar_resultado":
        return Resultado(exito=bool(x["exito"]), folio=x.get("folio", ""), nota=x.get("nota", ""))
    raise ValueError(f"Acción no soportada: {nombre}")
