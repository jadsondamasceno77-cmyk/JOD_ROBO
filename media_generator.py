#!/usr/bin/env python3
"""
Media Generator — clone de voz + avatar em vídeo (100% open source, roda em CPU)

Camadas:
  1. Voz: gTTS (Google TTS gratuito) → áudio MP3
  2. Voz clone: pyttsx3 (offline) com ajuste de rate/pitch por marca
  3. Vídeo: imagem estática (avatar) + áudio + legendas → MP4 via moviepy
  4. Futura integração: SadTalker (quando GPU disponível)
"""
import os
import asyncio
import hashlib
import json
import numpy as np
from pathlib import Path
from typing import Optional
from gtts import gTTS
from moviepy.editor import (
    ImageClip, AudioFileClip, TextClip, CompositeVideoClip, concatenate_videoclips
)

# ─── Dirs ─────────────────────────────────────────────────────────────────────
_BASE      = Path(__file__).parent
_MEDIA_DIR = _BASE / "social_sessions" / "media"
_VOICE_DIR = _MEDIA_DIR / "voices"
_VIDEO_DIR = _MEDIA_DIR / "videos"
_AVATAR_DIR = _MEDIA_DIR / "avatars"

for d in [_MEDIA_DIR, _VOICE_DIR, _VIDEO_DIR, _AVATAR_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ─── Voz Kokoro (qualidade premium, CPU-only, open source) ───────────────────

_KOKORO_VOICES = {
    # brand_id % 8 → voz única por marca
    0: "af_heart",   # feminina calorosa
    1: "af_nova",    # feminina moderna
    2: "af_sky",     # feminina clara
    3: "af_bella",   # feminina suave
    4: "am_adam",    # masculina jovem
    5: "am_michael", # masculina profissional
    6: "bf_emma",    # britânica feminina
    7: "bm_george",  # britânica masculina
}

async def gerar_voz_kokoro(texto: str, brand_id: int, lang: str = "pt-br") -> str:
    """
    Voz de alta qualidade via Kokoro ONNX (open source, CPU-only).
    Cada brand_id recebe uma voz única — simula identidade vocal distinta.
    Retorna path do arquivo WAV.
    """
    loop = asyncio.get_event_loop()
    h = hashlib.md5(f"{brand_id}_{texto[:50]}".encode()).hexdigest()[:8]
    output_path = str(_VOICE_DIR / f"brand{brand_id}_{h}_kokoro.wav")

    if os.path.exists(output_path):
        return output_path

    voice = _KOKORO_VOICES.get(brand_id % 8, "af_heart")

    def _generate():
        try:
            import soundfile as sf
            from kokoro_onnx import Kokoro
            kokoro = Kokoro("kokoro-v1.0.onnx", "voices-v1.0.bin")
            samples, sample_rate = kokoro.create(texto[:500], voice=voice, speed=1.0, lang=lang)
            sf.write(output_path, samples, sample_rate)
            return output_path
        except Exception as e:
            return None  # Fallback para gTTS

    result = await loop.run_in_executor(None, _generate)
    return result  # None = fallback


# ─── Voz (gTTS — fallback gratuito) ──────────────────────────────────────────

async def gerar_voz(texto: str, brand_id: int, lang: str = "pt") -> str:
    """
    Converte texto em áudio MP3 usando gTTS (gratuito, open source).
    Cada marca tem voz própria identificada pelo brand_id.
    Retorna path do arquivo MP3.
    """
    loop = asyncio.get_event_loop()

    # Hash do texto para cache (não regera se já existe)
    h = hashlib.md5(f"{brand_id}_{texto[:50]}".encode()).hexdigest()[:8]
    output_path = str(_VOICE_DIR / f"brand{brand_id}_{h}.mp3")

    if os.path.exists(output_path):
        return output_path

    def _generate():
        tts = gTTS(text=texto, lang=lang, slow=False)
        tts.save(output_path)
        return output_path

    await loop.run_in_executor(None, _generate)
    return output_path


async def gerar_voz_offline(texto: str, brand_id: int, rate: int = 150) -> str:
    """
    Voz offline via pyttsx3 (zero dependência de internet).
    Cada brand_id tem rate/pitch diferente — simula vozes distintas.
    Retorna path do arquivo WAV.
    """
    import pyttsx3
    loop = asyncio.get_event_loop()

    h = hashlib.md5(f"{brand_id}_{texto[:50]}".encode()).hexdigest()[:8]
    output_path = str(_VOICE_DIR / f"brand{brand_id}_{h}_offline.wav")

    if os.path.exists(output_path):
        return output_path

    # Varia rate por brand_id para personalizar voz
    brand_rate = rate + (brand_id % 5) * 10  # 150, 160, 170, 180, 190...

    def _generate():
        engine = pyttsx3.init()
        engine.setProperty("rate", brand_rate)
        engine.setProperty("volume", 0.9)
        engine.save_to_file(texto, output_path)
        engine.runAndWait()
        return output_path

    await loop.run_in_executor(None, _generate)
    return output_path


# ─── Avatar (imagem placeholder → será substituída por foto real da marca) ────

def _get_or_create_avatar(brand_id: int, brand_name: str = "") -> str:
    """
    Retorna avatar da marca. Se não existir, cria imagem colorida com as iniciais.
    Para usar foto real: salve em social_sessions/media/avatars/brand{brand_id}.png
    """
    avatar_path = str(_AVATAR_DIR / f"brand{brand_id}.png")

    if os.path.exists(avatar_path):
        return avatar_path

    # Cria imagem de placeholder com iniciais da marca
    try:
        import cv2
        import numpy as np

        # Cor única por brand_id
        hue = (brand_id * 47) % 180
        img = np.zeros((1080, 1080, 3), dtype=np.uint8)
        img[:] = cv2.cvtColor(
            np.uint8([[[hue, 180, 200]]]), cv2.COLOR_HSV2BGR
        )[0][0]

        # Iniciais da marca
        iniciais = "".join(w[0].upper() for w in brand_name.split()[:2]) or f"B{brand_id}"
        cv2.putText(img, iniciais,
                    (200, 620), cv2.FONT_HERSHEY_SIMPLEX, 15, (255, 255, 255), 30)

        cv2.imwrite(avatar_path, img)
    except Exception:
        # Fallback: imagem preta simples
        try:
            import cv2, numpy as np
            cv2.imwrite(avatar_path, np.zeros((1080, 1080, 3), np.uint8))
        except Exception:
            pass

    return avatar_path


# ─── Vídeo (avatar + voz + legendas) ─────────────────────────────────────────

async def gerar_video_reels(
    brand_id: int,
    brand_name: str,
    roteiro: str,
    legenda: str,
    duracao: int = 30,
    use_offline_voice: bool = False
) -> str:
    """
    Gera vídeo estilo Reels/TikTok:
    - Formato vertical 9:16 (1080x1920)
    - Avatar da marca como background
    - Voz narrada (gTTS ou pyttsx3)
    - Legenda animada no rodapé

    Retorna path do arquivo MP4.
    """
    loop = asyncio.get_event_loop()

    h = hashlib.md5(f"{brand_id}_{roteiro[:30]}".encode()).hexdigest()[:8]
    output_path = str(_VIDEO_DIR / f"brand{brand_id}_reels_{h}.mp4")

    if os.path.exists(output_path):
        return output_path

    # Passo 1: gerar áudio (Kokoro → gTTS → pyttsx3)
    texto_narrado = roteiro[:500]
    audio_path = None
    if not use_offline_voice:
        audio_path = await gerar_voz_kokoro(texto_narrado, brand_id)
    if not audio_path or not os.path.exists(str(audio_path)):
        if use_offline_voice:
            audio_path = await gerar_voz_offline(texto_narrado, brand_id)
        else:
            audio_path = await gerar_voz(texto_narrado, brand_id)

    # Passo 2: montar vídeo em executor (moviepy é bloqueante)
    avatar_path = _get_or_create_avatar(brand_id, brand_name)

    def _build_video():
        try:
            audio = AudioFileClip(audio_path)
            video_duration = min(audio.duration, 60)  # máx 60s

            # Background: avatar redimensionado para 9:16
            bg = ImageClip(avatar_path).resize((1080, 1920)).set_duration(video_duration)

            # Legenda no rodapé
            legenda_curta = legenda[:120] + "..." if len(legenda) > 120 else legenda
            try:
                txt = TextClip(
                    legenda_curta,
                    fontsize=42,
                    color="white",
                    bg_color="rgba(0,0,0,0.6)",
                    size=(1000, None),
                    method="caption",
                    font="DejaVu-Sans",
                ).set_duration(video_duration).set_position(("center", 1600))
                video = CompositeVideoClip([bg, txt])
            except Exception:
                # Fallback sem legenda se TextClip falhar
                video = bg

            video = video.set_audio(audio.subclip(0, video_duration))
            video.write_videofile(
                output_path,
                fps=24,
                codec="libx264",
                audio_codec="aac",
                verbose=False,
                logger=None,
            )
            return output_path
        except Exception as e:
            return f"ERRO: {e}"

    result = await loop.run_in_executor(None, _build_video)
    return result


async def gerar_video_stories(
    brand_id: int,
    brand_name: str,
    texto: str,
) -> str:
    """
    Gera Stories: 15s, vertical, texto animado sobre avatar.
    """
    return await gerar_video_reels(
        brand_id=brand_id,
        brand_name=brand_name,
        roteiro=texto[:200],
        legenda=texto[:80],
        duracao=15,
    )


# ─── Pipeline completo de mídia para uma marca ────────────────────────────────

async def gerar_pack_midia(
    brand_id: int,
    brand_name: str,
    roteiro: str,
    legenda: str,
) -> dict:
    """
    Gera pack completo: voz + reels + stories.
    Retorna paths de todos os arquivos gerados.
    """
    resultados = {}

    # Voz narrada
    try:
        voz_path = await gerar_voz(roteiro[:400], brand_id)
        resultados["voz_mp3"] = voz_path
    except Exception as e:
        resultados["voz_mp3"] = f"erro: {e}"

    # Reels (30s)
    try:
        reels_path = await gerar_video_reels(brand_id, brand_name, roteiro, legenda, duracao=30)
        resultados["reels_mp4"] = reels_path
    except Exception as e:
        resultados["reels_mp4"] = f"erro: {e}"

    # Stories (15s)
    try:
        stories_path = await gerar_video_stories(brand_id, brand_name, roteiro[:200])
        resultados["stories_mp4"] = stories_path
    except Exception as e:
        resultados["stories_mp4"] = f"erro: {e}"

    return {
        "brand_id": brand_id,
        "brand_name": brand_name,
        "arquivos": resultados,
        "status": "ok" if all("erro" not in str(v) for v in resultados.values()) else "parcial"
    }
