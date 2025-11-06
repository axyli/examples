#!/usr/bin/env python3
import os
import sys
import random
import numpy as np
from moviepy import (
    VideoFileClip,
    ImageClip,
    concatenate_videoclips,
    AudioFileClip,
    concatenate_audioclips,
    CompositeAudioClip,
)
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip

# === НАСТРОЙКИ ===
MEDIA_DIR = "."                  # Папка с файлами
OUTPUT_FILE = "final_mix.mp4"    # Имя выходного видео
AUDIO_FILENAME = "music.mp3"     # Фоновая музыка
IMAGE_DURATION = 3               # Длительность фото
MUSIC_VOLUME = 0.25              # Громкость музыки
DUCK_VOLUME = 0.5                # Приглушение под видео
TARGET_SIZE = (1920, 1080)       # Размер кадра (только для фото)
BG_COLOR = (0, 0, 0)             # Цвет фона фото (чёрный)


# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===
def make_background(size, color):
    """Создать фоновый кадр из массива numpy."""
    frame = np.zeros((size[1], size[0], 3), dtype=np.uint8)
    frame[:, :] = color
    return ImageClip(frame)


def safe_resize(clip, size):
    """Безопасно масштабировать (учитывает API MoviePy 2.x и 1.x)."""
    for name in ("with_resized", "resize", "resized"):
        fn = getattr(clip, name, None)
        if callable(fn):
            try:
                return fn(size)
            except TypeError:
                return fn(new_size=size)
    return clip


def ensure_duration(clip, duration):
    """Безопасно задать длительность."""
    for name in ("with_duration", "set_duration"):
        fn = getattr(clip, name, None)
        if callable(fn):
            return fn(duration)
    clip.duration = duration
    return clip


def create_framed_image(path, target_size):
    """Создать фото на фоне с нужным размером кадра."""
    try:
        img = ImageClip(path)
        img = ensure_duration(img, IMAGE_DURATION)

        # Масштаб с сохранением пропорций
        ratio = min(target_size[0] / img.w, target_size[1] / img.h)
        new_size = (int(img.w * ratio), int(img.h * ratio))
        img = safe_resize(img, new_size)

        # Фон как numpy
        bg = make_background(target_size, BG_COLOR).with_duration(IMAGE_DURATION)
        composed = CompositeVideoClip([bg, img.with_position(("center", "center"))])
        return composed
    except Exception as e:
        print(f"Пропускаю {path}: {e}")
        return None


def get_media_files(folder):
    """Получить список файлов, 000.jpg первым, остальные перемешаны."""
    exts = (".mp4", ".mov", ".avi", ".mkv", ".jpg", ".jpeg", ".png")
    files = [
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if f.lower().endswith(exts)
    ]

    first_file = None
    for f in files:
        if os.path.basename(f).lower() == "000.jpg":
            first_file = f
            break

    if first_file:
        files.remove(first_file)

    random.shuffle(files)
    if first_file:
        files = [first_file] + files

    return files


def prepare_clips(media_files):
    clips = []
    for path in media_files:
        low = path.lower()
        try:
            if low.endswith((".mp4", ".mov", ".avi", ".mkv")):
                clip = VideoFileClip(path)
            else:
                clip = create_framed_image(path, TARGET_SIZE)
            if clip:
                clips.append(clip)
        except Exception as e:
            print(f"Пропускаю {path}: {e}")
    return clips


def build_music_track(bg_music, clips, base_vol, duck_vol):
    """Создать аудиодорожку с приглушением при наличии видеоаудио."""
    segments = []
    t = 0
    for clip in clips:
        dur = getattr(clip, "duration", 0) or 0
        if dur <= 0:
            continue
        has_audio = getattr(clip, "audio", None) is not None
        seg = bg_music.subclipped(t, min(t + dur, bg_music.duration))

        for fn_name in ("with_volume_x", "volumex"):
            fn = getattr(seg, fn_name, None)
            if callable(fn):
                seg = fn(duck_vol if has_audio else base_vol)
                break

        segments.append(seg)
        t += dur
        if t >= bg_music.duration:
            break
    if not segments:
        for fn_name in ("with_volume_x", "volumex"):
            fn = getattr(bg_music, fn_name, None)
            if callable(fn):
                return fn(base_vol)
        return bg_music
    return concatenate_audioclips(segments)


# === ОСНОВНОЙ ПРОЦЕСС ===
def main():
    print("Собираем материалы...")
    media_files = get_media_files(MEDIA_DIR)
    clips = prepare_clips(media_files)
    if not clips:
        print("Не удалось создать ни одного клипа!")
        sys.exit(1)

    final_clip = concatenate_videoclips(clips, method="compose")

    audio_path = os.path.join(MEDIA_DIR, AUDIO_FILENAME)
    if os.path.exists(audio_path):
        print("Добавляем музыку...")
        bg_music = AudioFileClip(audio_path)
        bg_music = build_music_track(bg_music, clips, MUSIC_VOLUME, DUCK_VOLUME)
        video_audio = getattr(final_clip, "audio", None)
        if video_audio:
            final_audio = CompositeAudioClip([video_audio, bg_music])
        else:
            final_audio = bg_music
        final_clip = final_clip.with_audio(final_audio)

    print("Экспортируем финальное видео...")
    final_clip.write_videofile(
        OUTPUT_FILE,
        fps=30,
        codec="libx264",
        audio_codec="aac",
    )
    print(f"Готово! Файл сохранён как: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
