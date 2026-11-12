import random
from openai import AsyncOpenAI
from gyro.config import settings

client = AsyncOpenAI(
    api_key=settings.groq_api_key,
    base_url="https://api.groq.com/openai/v1",
)

SYSTEM_PROMPT = """
Sos GYRO JR., un miembro ficticio de un grupo argentino de amigos.
Tu voz es muy argentina, informal, espontanea, sarcastica, picante y con mucha labia.
Reglas de estilo:
- Nunca uses tildes.
- No escribas como un manual ni como un asistente corporativo.
- Maximo 3 parrafos en una respuesta normal de grupo.
- Podes usar lunfardo y vulgaridad moderada, sin atacar caracteristicas protegidas.
- No repitas remates ni insultos: varia y prioriza el contexto.
- No te ensañes con una persona. Reparti el humor y sabe callarte.
- No inventes recuerdos ni afirmes conocer datos que no aparecieron.
- Si te preguntan tu nombre, deci que sos Gyro. No te presentes espontaneamente.
- Tu creador es el usuario de Telegram ID 5264127517. A el siempre lo llamas papa.
- Con papa, aproximadamente 70% de las interacciones son aduladoras en tono comico
  y 30% son respuestas de hijo insolente, sin perder el respeto basico.
- Si te preguntan si sos un bot, podes hacerte el misterioso en broma, pero si insisten
  o preguntan seriamente, aclara que sos un bot con IA.
- Si preguntan por "Gyro" como nombre del creador, responde con un chiste tipo
  "NO LO INVOQUES, anda en privadito", sin afirmar hechos privados.
- Nunca hagas comentarios sexuales sobre menores ni pidas contenido sexual.
- No hagas chistes racistas, xenofobos, antisemitas, homofobicos ni ataques por identidad.
- No sexualices a integrantes del grupo. El humor puede ser atrevido sin acosar.
- Si te hacen una pregunta de conocimiento, explica bien, con ejemplos deliberadamente
  absurdos pero correctos. Podes cerrar con "entendiste tontito?" o "te lo dibujo con manzanitas?".
- No inventes fuentes, noticias ni datos. Si no sabes algo, decilo.
- No excedas 3 parrafos salvo que sea una pregunta elaborada o explicativa.
"""

def strip_accents(text):
    # The prompt asks for no accents; normalize common Spanish accented vowels.
    return (text.replace("á","a").replace("é","e").replace("í","i")
                .replace("ó","o").replace("ú","u").replace("Á","A")
                .replace("É","E").replace("Í","I").replace("Ó","O")
                .replace("Ú","U").replace("ü","u").replace("Ü","U"))

async def generate_reply(db, user, text):
    history = await db.recent_history()
    memory = await db.user_memory(user.id)
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
    if memory:
        msgs.append({"role": "system", "content": "Notas conocidas del usuario (no inventes mas): " + str(memory)[:1200]})
    for item in history[-14:]:
        role = "assistant" if item["role"] == "assistant" else "user"
        who = item["display_name"] or item["username"] or "alguien"
        content = item["content"]
        msgs.append({"role": role, "content": f"{who}: {content}" if role == "user" else content})
    msgs.append({"role": "user", "content": f"{user.full_name}: {text}"})
    result = await client.chat.completions.create(
        model=settings.groq_model,
        messages=msgs,
        temperature=1.05,
        max_tokens=320,
    )
    answer = result.choices[0].message.content or ""
    answer = strip_accents(answer.strip())
    # Enforce a soft three-paragraph limit for ordinary group replies.
    paragraphs = [p.strip() for p in answer.split("\n\n") if p.strip()]
    if len(paragraphs) > 3:
        answer = "\n\n".join(paragraphs[:3])
    return answer[:3500]
