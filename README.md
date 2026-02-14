# Senticare - Webhook ElevenLabs

Servidor webhook que recibe transcripciones de conversaciones de ElevenLabs, genera resúmenes con OpenAI y los envía por email.

## Características

- 🎙️ Recibe webhooks de ElevenLabs al finalizar conversaciones
- 🤖 Genera resúmenes estructurados con GPT-4
- 📧 Envía emails HTML elegantes con Resend
- ⚡ Desplegado en Railway

## Variables de entorno

Copia `.env.example` a `.env` y configura:

- `RESEND_API_KEY`: Tu API key de Resend
- `OPENAI_API_KEY`: Tu API key de OpenAI
- `EMAIL_FROM`: Email remitente (debe estar verificado en Resend)
- `EMAIL_TO`: Email destinatario de los resúmenes

## Instalación local

```bash
pip install -r requirements.txt
python mail.py
```

## Despliegue en Railway

1. Conecta este repositorio a Railway
2. Configura las variables de entorno
3. Railway detectará automáticamente el archivo Python y lo desplegará
4. Copia la URL pública generada

## Configurar webhook en ElevenLabs

1. Ve a tu configuración de ElevenLabs
2. Añade la URL del webhook: `https://tu-app.railway.app/webhook/elevenlabs`
3. Asegúrate de que el evento `conversation.ended` esté activado

## Endpoint

- `POST /webhook/elevenlabs` - Recibe webhooks de ElevenLabs
- `GET /` - Health check
