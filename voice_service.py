import edge_tts

VOCES_DISPONIBLES = {
    "dalia": "es-MX-DaliaNeural",    # Femenina
    "jorge": "es-MX-JorgeNeural"     # Masculina
}

async def sintetizar_voz(texto: str, voz_id: str = "dalia") -> bytes:
    """
    Sintetiza un texto en voz usando edge-tts y la voz especificada.
    Devuelve los bytes en formato MP3.
    """
    nombre_voz = VOCES_DISPONIBLES.get(voz_id.lower(), voz_id)
    communicate = edge_tts.Communicate(texto, nombre_voz)
    audio_data = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data += chunk["data"]
            
    return audio_data
