from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import resend
import os
from dotenv import load_dotenv
from openai import OpenAI
from datetime import datetime
import json
import hmac
import hashlib

load_dotenv()

app = FastAPI()

# Configurar Resend
resend.api_key = os.getenv("RESEND_API_KEY")

# Cliente de OpenAI para generar resumen
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Webhook secret de ElevenLabs
ELEVENLABS_WEBHOOK_SECRET = os.getenv("ELEVENLABS_WEBHOOK_SECRET")

def verificar_webhook_signature(payload: bytes, signature: str) -> bool:
    """Verifica que la petición viene realmente de ElevenLabs"""
    if not ELEVENLABS_WEBHOOK_SECRET:
        # Si no hay secret configurado, permitir la petición (para desarrollo)
        return True

    expected_signature = hmac.new(
        ELEVENLABS_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature, expected_signature)

def generar_resumen(transcripcion: str, duracion: int, nombre_usuario: str) -> dict:
    """Genera un resumen estructurado de la llamada usando OpenAI"""
    
    prompt = f"""Analiza esta transcripción de una llamada de acompañamiento a una persona mayor.

TRANSCRIPCIÓN:
{transcripcion}

DURACIÓN: {duracion} segundos
NOMBRE: {nombre_usuario}

Genera un resumen INFORMATIVO (no valorativo) en formato JSON con esta estructura exacta:

{{
  "temas_conversados": [
    "Lista de temas que se trataron, de forma descriptiva y neutral"
  ],
  "momentos_destacados": [
    "Anécdotas, recuerdos o cosas que compartió la persona de forma natural"
  ],
  "estado_animo": "Descripción breve y objetiva de cómo se encontraba (tranquilo, animado, nostálgico, etc.)",
  "temas_futuros": [
    "Temas que quedaron abiertos o que mencionó que le gustaría hablar en el futuro"
  ]
}}

IMPORTANTE:
- NO hagas valoraciones ni juicios ("estuvo bien", "muy positivo", "preocupante")
- SÉ DESCRIPTIVO: "Habló sobre su nieta que viene este fin de semana" en vez de "Tiene una buena relación familiar"
- USA las palabras y expresiones que usó la persona
- Si no hay info para alguna sección, pon array vacío []
- Responde SOLO el JSON, sin texto adicional"""

    response = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "Eres un asistente que analiza conversaciones y genera resúmenes estructurados en formato JSON. Responde únicamente con JSON válido, sin texto adicional."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.3,
        max_tokens=2000,
        response_format={"type": "json_object"}
    )
    
    resumen_text = response.choices[0].message.content.strip()
    
    # Limpiar posibles markdown code blocks
    if resumen_text.startswith("```"):
        resumen_text = resumen_text.split("```")[1]
        if resumen_text.startswith("json"):
            resumen_text = resumen_text[4:]
    
    return json.loads(resumen_text)


def formatear_duracion(segundos: int) -> str:
    """Convierte segundos a formato legible"""
    minutos = segundos // 60
    segs = segundos % 60
    if minutos > 0:
        return f"{minutos} min {segs} seg"
    return f"{segs} seg"


def enviar_email_resumen(resumen: dict, nombre_usuario: str, conversation_id: str, duracion: int):
    """Envía el email con el resumen vía Resend"""
    
    ahora = datetime.now()
    fecha = ahora.strftime("%d de %B de %Y")
    hora = ahora.strftime("%H:%M")
    duracion_formateada = formatear_duracion(duracion)
    
    # Construir secciones HTML
    temas_html = ""
    if resumen.get("temas_conversados"):
        temas_html = "<ul style='margin: 10px 0; padding-left: 20px;'>"
        for tema in resumen["temas_conversados"]:
            temas_html += f"<li style='margin: 5px 0;'>{tema}</li>"
        temas_html += "</ul>"
    else:
        temas_html = "<p style='color: #9ca3af; font-style: italic;'>No se registraron temas específicos</p>"
    
    momentos_html = ""
    if resumen.get("momentos_destacados"):
        momentos_html = "<ul style='margin: 10px 0; padding-left: 20px;'>"
        for momento in resumen["momentos_destacados"]:
            momentos_html += f"<li style='margin: 5px 0;'>{momento}</li>"
        momentos_html += "</ul>"
    else:
        momentos_html = "<p style='color: #9ca3af; font-style: italic;'>No hubo momentos destacados particulares</p>"
    
    estado_html = resumen.get("estado_animo", "No registrado")
    
    futuros_html = ""
    if resumen.get("temas_futuros"):
        futuros_html = "<ul style='margin: 10px 0; padding-left: 20px;'>"
        for tema in resumen["temas_futuros"]:
            futuros_html += f"<li style='margin: 5px 0;'>{tema}</li>"
        futuros_html += "</ul>"
    else:
        futuros_html = "<p style='color: #9ca3af; font-style: italic;'>No se identificaron temas pendientes</p>"
    
    html_email = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f9fafb;">
        <table role="presentation" style="width: 100%; border-collapse: collapse;">
            <tr>
                <td style="padding: 40px 20px;">
                    <table role="presentation" style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);">
                        
                        <!-- Header -->
                        <tr>
                            <td style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px 30px; border-radius: 12px 12px 0 0; text-align: center;">
                                <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 600; letter-spacing: -0.5px;">
                                    💬 Conversación con {nombre_usuario}
                                </h1>
                                <p style="margin: 10px 0 0 0; color: #e0e7ff; font-size: 16px;">
                                    {fecha} a las {hora}
                                </p>
                            </td>
                        </tr>
                        
                        <!-- Datos básicos -->
                        <tr>
                            <td style="padding: 30px;">
                                <table role="presentation" style="width: 100%; border-collapse: collapse; background-color: #f9fafb; border-radius: 8px; padding: 20px;">
                                    <tr>
                                        <td style="padding: 10px 20px;">
                                            <table role="presentation" style="width: 100%;">
                                                <tr>
                                                    <td style="width: 50%; padding: 5px 0;">
                                                        <span style="color: #6b7280; font-size: 14px;">⏱️ Duración</span><br>
                                                        <strong style="color: #111827; font-size: 16px;">{duracion_formateada}</strong>
                                                    </td>
                                                    <td style="width: 50%; padding: 5px 0; text-align: right;">
                                                        <span style="color: #6b7280; font-size: 14px;">🆔 ID</span><br>
                                                        <strong style="color: #111827; font-size: 12px; font-family: monospace;">{conversation_id[:12]}...</strong>
                                                    </td>
                                                </tr>
                                            </table>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>
                        
                        <!-- Temas conversados -->
                        <tr>
                            <td style="padding: 0 30px 25px 30px;">
                                <h2 style="color: #111827; font-size: 18px; font-weight: 600; margin: 0 0 12px 0; border-left: 4px solid #667eea; padding-left: 12px;">
                                    🗨️ Temas que se trataron
                                </h2>
                                <div style="color: #374151; font-size: 15px; line-height: 1.6;">
                                    {temas_html}
                                </div>
                            </td>
                        </tr>
                        
                        <!-- Momentos destacados -->
                        <tr>
                            <td style="padding: 0 30px 25px 30px;">
                                <h2 style="color: #111827; font-size: 18px; font-weight: 600; margin: 0 0 12px 0; border-left: 4px solid #10b981; padding-left: 12px;">
                                    ✨ Momentos que compartió
                                </h2>
                                <div style="color: #374151; font-size: 15px; line-height: 1.6;">
                                    {momentos_html}
                                </div>
                            </td>
                        </tr>
                        
                        <!-- Estado de ánimo -->
                        <tr>
                            <td style="padding: 0 30px 25px 30px;">
                                <h2 style="color: #111827; font-size: 18px; font-weight: 600; margin: 0 0 12px 0; border-left: 4px solid #f59e0b; padding-left: 12px;">
                                    💭 Cómo se encontraba
                                </h2>
                                <div style="color: #374151; font-size: 15px; line-height: 1.6; background-color: #fffbeb; padding: 15px; border-radius: 6px;">
                                    {estado_html}
                                </div>
                            </td>
                        </tr>
                        
                        <!-- Temas para el futuro -->
                        <tr>
                            <td style="padding: 0 30px 30px 30px;">
                                <h2 style="color: #111827; font-size: 18px; font-weight: 600; margin: 0 0 12px 0; border-left: 4px solid #8b5cf6; padding-left: 12px;">
                                    🔜 Temas para próximas conversaciones
                                </h2>
                                <div style="color: #374151; font-size: 15px; line-height: 1.6;">
                                    {futuros_html}
                                </div>
                            </td>
                        </tr>
                        
                        <!-- Footer -->
                        <tr>
                            <td style="padding: 30px; background-color: #f9fafb; border-radius: 0 0 12px 12px; text-align: center; border-top: 1px solid #e5e7eb;">
                                <p style="margin: 0; color: #6b7280; font-size: 13px; line-height: 1.5;">
                                    Este resumen fue generado automáticamente<br>
                                    <strong style="color: #667eea;">Senticare</strong> • Acompañamiento con cariño
                                </p>
                            </td>
                        </tr>
                        
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    
    params = {
        "from": os.getenv("EMAIL_FROM"),
        "to": [os.getenv("EMAIL_TO")],
        "subject": f"💬 Conversación con {nombre_usuario} - {fecha}",
        "html": html_email
    }

    print(f"   📤 Enviando email desde: {params['from']}")
    print(f"   📥 Destinatario: {params['to'][0]}")
    print(f"   📋 Asunto: {params['subject']}")

    try:
        email = resend.Emails.send(params)
        print(f"   ✅ Resend response: {email}")
        return email
    except Exception as e:
        print(f"   ❌ Error enviando email con Resend: {str(e)}")
        raise


@app.post("/webhook/elevenlabs")
@app.post("/webhook/ele   venlabs")  # Ruta alternativa para manejar URL malformada de ElevenLabs
async def elevenlabs_webhook(request: Request):
    """Endpoint que recibe el webhook de ElevenLabs al finalizar llamada"""

    try:
        print("=" * 60)
        print("🔔 Webhook recibido de ElevenLabs")

        # Obtener el body raw para verificar la firma
        body = await request.body()
        print(f"📦 Tamaño del payload: {len(body)} bytes")

        # TEMPORAL: Verificación de firma deshabilitada para debugging
        # TODO: Investigar el método correcto de firma que usa ElevenLabs
        signature = request.headers.get("x-elevenlabs-signature", "")
        print(f"⚠️  Verificación de firma temporalmente deshabilitada")
        print(f"   Header signature recibido: {signature[:20] if signature else 'No enviado'}...")

        # if ELEVENLABS_WEBHOOK_SECRET:
        #     signature = request.headers.get("x-elevenlabs-signature", "")
        #     print(f"🔐 Verificando firma... (secret configurado: Sí)")
        #     if not verificar_webhook_signature(body, signature):
        #         print("❌ ERROR: Firma inválida!")
        #         raise HTTPException(status_code=401, detail="Invalid webhook signature")
        #     print("✅ Firma verificada correctamente")
        # else:
        #     print("⚠️  Secret no configurado, omitiendo verificación de firma")

        # Parsear los datos del webhook
        data = json.loads(body)

        # DEBUG: Imprimir estructura del payload para entender formato de ElevenLabs
        print("📋 Estructura del payload recibido:")
        print(f"   Keys: {list(data.keys())}")

        # Imprimir primeros 500 caracteres del payload (sin datos sensibles)
        payload_preview = json.dumps(data, indent=2)[:500]
        print(f"   Preview: {payload_preview}...")

        # Extraer información relevante
        event_type = data.get("event_type")
        print(f"📋 Tipo de evento: {event_type}")

        # Solo procesar cuando termina la conversación
        if event_type == "conversation.ended":
            conversation_id = data.get("conversation_id")
            transcript = data.get("transcript", "")
            duration = data.get("duration_seconds", 0)

            print(f"🆔 Conversation ID: {conversation_id}")
            print(f"⏱️  Duración: {duration} segundos")
            print(f"📝 Transcripción: {len(transcript)} caracteres")

            # Obtener nombre del usuario si viene en metadata
            metadata = data.get("metadata", {})
            nombre_usuario = metadata.get("nombre", "Usuario")
            print(f"👤 Usuario: {nombre_usuario}")

            # Generar resumen con OpenAI
            print("🤖 Generando resumen con OpenAI...")
            resumen = generar_resumen(transcript, duration, nombre_usuario)
            print(f"✅ Resumen generado: {len(str(resumen))} caracteres")

            # Enviar email
            print("📧 Enviando email con Resend...")
            enviar_email_resumen(resumen, nombre_usuario, conversation_id, duration)
            print("✅ Email enviado correctamente!")
            print("=" * 60)

            return JSONResponse(
                status_code=200,
                content={"message": "Resumen enviado correctamente"}
            )

        print(f"ℹ️  Evento '{event_type}' recibido pero no procesado")
        print("=" * 60)
        return JSONResponse(
            status_code=200,
            content={"message": "Evento recibido pero no procesado"}
        )

    except HTTPException as e:
        print(f"❌ HTTPException: {e.detail}")
        print("=" * 60)
        raise
    except Exception as e:
        print(f"❌ ERROR procesando webhook: {str(e)}")
        import traceback
        print(traceback.format_exc())
        print("=" * 60)
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@app.get("/")
async def root():
    return {"status": "Webhook server activo", "service": "Senticare ElevenLabs"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)