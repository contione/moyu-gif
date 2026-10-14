"""Readable, keyword-led comic captions for the office duck series."""

from functools import lru_cache
import math

from PIL import Image, ImageDraw, ImageFont


SCALE = 3
INK = (35, 38, 42)
AMBER = (255, 183, 57)
MINT = (101, 211, 173)
CORAL = (255, 135, 103)
CAPTION_STYLES = {
    "收到，马上办": ("", "收到", "，马上办", "stamp", MINT),
    "马上安排": ("马上", "安排", "", "stamp", AMBER),
    "在做了在做了": ("在做了", "在做了", "", "echo", CORAL),
    "先对齐一下": ("先", "对齐", "一下", "align", MINT),
    "这个优先": ("这个", "优先", "", "stamp", CORAL),
    "进度如何啦": ("进度如何", "啦？", "", "peek", AMBER),
    "等你拍板": ("等你", "拍板", "", "waiting", MINT),
    "已交付，请查收": ("", "已交付", "，请查收", "stamp", MINT),
    "效率拉满": ("效率", "拉满", "", "rush", AMBER),
    "别再加需求了": ("别再加", "需求", "了", "squash", CORAL),
    "喝口再卷": ("喝口", "再卷", "", "bounce", AMBER),
    "高效下班": ("高效", "下班", "", "rush", AMBER),
}


def has_caption_effect(title: str) -> bool:
    return title in CAPTION_STYLES


@lru_cache(maxsize=192)
def text_sprite(text: str, font_path: str, font_size: int, color: tuple[int, int, int]) -> Image.Image:
    font = ImageFont.truetype(font_path, font_size * SCALE, index=0)
    bounds = font.getbbox(text, anchor="lt")
    padding = 5 * SCALE
    sprite = Image.new("RGBA", (bounds[2] - bounds[0] + 2 * padding, bounds[3] - bounds[1] + 2 * padding))
    draw = ImageDraw.Draw(sprite)
    origin = (padding - bounds[0], padding - bounds[1])
    draw.text((origin[0] + 2 * SCALE, origin[1] + 3 * SCALE), text, font=font, anchor="lt", fill=(201, 205, 210), stroke_width=SCALE)
    draw.text(origin, text, font=font, anchor="lt", fill=color, stroke_width=3 * SCALE, stroke_fill="white")
    draw.text(origin, text, font=font, anchor="lt", fill=color, stroke_width=SCALE if color != INK else 0, stroke_fill=INK)
    return sprite


def sample_keyframes(progress: float, keyframes: tuple[tuple[float, ...], ...]) -> tuple[float, ...]:
    for previous, following in zip(keyframes, keyframes[1:]):
        if progress <= following[0]:
            fraction = max(0.0, (progress - previous[0]) / (following[0] - previous[0]))
            fraction = fraction * fraction * (3 - 2 * fraction)
            return tuple(start + (finish - start) * fraction for start, finish in zip(previous[1:], following[1:]))
    return keyframes[-1][1:]


def keyword_transform(style: str, phase: float) -> tuple[float, ...]:
    rest = (1.0, 1.0, 0.0, 0.0, 0.0)
    if style == "stamp":
        return sample_keyframes(phase, (
            (0.0, *rest), (0.10, 1.10, 1.12, 0, -7, -3),
            (0.20, 1.12, 0.80, 0, 4, 0), (0.32, 0.98, 1.06, 0, -2, 0), (0.46, *rest),
        ))
    if style == "echo":
        return sample_keyframes(phase, (
            (0.0, *rest), (0.12, 0.90, 0.93, 10, 5, 0),
            (0.25, 1.06, 1.06, -3, -2, -2), (0.36, 1.0, 1.0, 2, 0, 2), (0.48, *rest),
        ))
    if style == "rush":
        return sample_keyframes(phase, (
            (0.0, *rest), (0.12, 0.94, 1.0, -6, 0, 0),
            (0.27, 1.10, 0.92, 10, -2, -4), (0.43, *rest),
        ))
    if style == "squash":
        return sample_keyframes(phase, (
            (0.0, *rest), (0.18, 1.10, 0.70, 0, 5, 0),
            (0.29, 0.94, 1.10, 0, -2, -3), (0.48, *rest),
        ))
    if style == "peek":
        return sample_keyframes(phase, (
            (0.0, *rest), (0.25, 1.14, 1.14, 2, -3, -7), (0.50, *rest),
        ))
    if style == "align":
        return sample_keyframes(phase, (
            (0.0, *rest), (0.14, 1.0, 1.0, 6, -3, 7),
            (0.30, 1.0, 1.0, -2, 1, -2), (0.45, *rest),
        ))
    if style == "waiting":
        return sample_keyframes(phase, ((0.0, *rest), (0.32, 1.0, 0.94, 0, 3, 0), (0.50, *rest)))
    return sample_keyframes(phase, ((0.0, *rest), (0.18, 1.06, 1.08, 0, -7, -3), (0.42, *rest)))


def draw_animated_caption(
    frame: Image.Image,
    title: str,
    caption_font: ImageFont.FreeTypeFont,
    frame_index: int,
    frame_count: int,
    top: int,
) -> bool:
    if title not in CAPTION_STYLES:
        return False
    prefix, keyword, suffix, style, accent = CAPTION_STYLES[title]
    phase = frame_index / frame_count
    font = caption_font
    while font.size > 20:
        total_width = sum(font.getlength(part) for part in (prefix, keyword, suffix))
        if total_width + font.getlength(keyword) * 0.18 <= frame.width - 42:
            break
        font = font.font_variant(size=font.size - 1)
    widths = [font.getlength(part) for part in (prefix, keyword, suffix)]
    total_width = sum(widths)
    region_height = frame.height - top
    canvas = Image.new("RGBA", (frame.width * SCALE, region_height * SCALE), "white")
    draw = ImageDraw.Draw(canvas)
    cursor = (frame.width - total_width) / 2
    focus_box = None
    transform = keyword_transform(style, phase)
    for position, (part, width) in enumerate(zip((prefix, keyword, suffix), widths)):
        if not part:
            continue
        focus = position == 1
        sprite = text_sprite(part, str(font.path), font.size, accent if focus else INK)
        scale_x, scale_y, offset_x, offset_y, angle = transform if focus else (1, 1, 0, 0, 0)
        if style == "squash" and position == 2 and phase < 0.50:
            offset_y = 5 * math.sin(math.pi * phase / 0.50)
        transformed = sprite.resize((round(sprite.width * scale_x), round(sprite.height * scale_y)), Image.Resampling.LANCZOS)
        if angle:
            transformed = transformed.rotate(angle, Image.Resampling.BICUBIC, expand=True)
        center_x = (cursor + width / 2 + offset_x) * SCALE
        center_y = (region_height / 2 - 3 + offset_y) * SCALE
        left = max(SCALE, min(canvas.width - transformed.width - SCALE, round(center_x - transformed.width / 2)))
        upper = max(SCALE, min(canvas.height - transformed.height - SCALE, round(center_y - transformed.height / 2)))
        if focus:
            focus_box = (cursor, cursor + width, center_y / SCALE)
            underline_y = min(region_height - 9, center_y / SCALE + font.size * 0.45)
            draw.rounded_rectangle(
                (round((cursor - 2) * SCALE), round(underline_y * SCALE), round((cursor + width + 3) * SCALE), round((underline_y + 5) * SCALE)),
                radius=2 * SCALE,
                fill=tuple(round(channel * 0.38 + 255 * 0.62) for channel in accent),
            )
        canvas.alpha_composite(transformed, (left, upper))
        cursor += width
    if focus_box is not None:
        left, right, center_y = focus_box
        if style in {"stamp", "rush", "echo"} and 0.12 <= phase <= 0.38:
            for line_index in range(2):
                line_y = center_y - 18 + line_index * 6
                start_x = max(7, left - 12 - line_index * 3)
                draw.line((round(start_x * SCALE), round(line_y * SCALE), round((left - 3) * SCALE), round((line_y - 2) * SCALE)), fill=accent, width=2 * SCALE)
        if style == "waiting":
            dots = min(3, int(phase / 0.14) + 1)
            for dot_index in range(dots):
                center_x = (left + right) / 2 + (dot_index - 1) * 10
                draw.ellipse(((center_x - 2) * SCALE, (region_height - 7) * SCALE, (center_x + 2) * SCALE, (region_height - 3) * SCALE), fill=INK)
    region = canvas.convert("RGB").resize((frame.width, region_height), Image.Resampling.LANCZOS)
    frame.paste(region, (0, top))
    return True
