import json
from typing import AsyncGenerator
import logging

logger = logging.getLogger("uvicorn")


async def parrot_stream(message: str) -> AsyncGenerator[str, None]:
    """
    Simula l'output di stream_query prendendo un messaggio in input e restituendolo
    in formato SSE con lo stesso schema JSON usato da StreamingHandler.

    Il messaggio viene diviso in 2 chunk per simulare lo streaming reale.
    Applica lo stesso escape automatico di json.dumps() usato da stream_query.

    Args:
        message: Il messaggio da "ripetere" (parrot)

    Yields:
        Stringhe formattate in formato SSE: "data: {JSON}"
    """
    try:
        logger.info(f"PARROT - Starting stream for message: {message[:50]}...")

        # Dividi il messaggio in 2 chunk (prima metà e seconda metà)
        if not message:
            logger.warning("PARROT - Empty message received")
            return

        mid_point = len(message) // 2

        # Trova uno spazio vicino al punto medio per non spezzare parole
        # Cerca fino a 20 caratteri prima o dopo il punto medio
        split_point = mid_point
        for offset in range(min(20, mid_point)):
            if message[mid_point + offset] == ' ':
                split_point = mid_point + offset + 1
                break
            elif mid_point - offset > 0 and message[mid_point - offset] == ' ':
                split_point = mid_point - offset + 1
                break

        chunk1 = message[:split_point]
        chunk2 = message[split_point:]

        chunks = [chunk1, chunk2] if chunk2 else [chunk1]

        # Produce eventi in formato identico a StreamingHandler._handle_model_stream()
        for i, chunk in enumerate(chunks):
            if chunk:
                # Stesso formato di streaming_handler.py:124-128
                ai_response = {
                    "type": "agent_message",
                    "data": chunk
                }
                # json.dumps() applica automaticamente l'escape dei caratteri speciali
                yield f"data: {json.dumps(ai_response)}"
                logger.debug(f"PARROT - Chunk {i+1}/{len(chunks)} sent")

        logger.info("PARROT - Stream completed successfully")

    except Exception as e:
        logger.error(f"PARROT - Error during streaming: {e}")
        error_response = {
            "type": "error",
            "data": f"Error: {str(e)}"
        }
        yield f"data: {json.dumps(error_response)}"
