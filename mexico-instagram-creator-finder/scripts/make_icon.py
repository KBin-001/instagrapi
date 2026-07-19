"""生成应用图标 assets/app.ico。

简单的墨西哥国旗绿+米色字母 M 图标，256x256 → 多尺寸 ico。
运行：python scripts/make_icon.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def make_icon(size: int = 256) -> Image.Image:
    """生成单个尺寸的图标。"""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 圆角矩形背景：深绿（墨西哥国旗绿 #006847）
    margin = size // 16
    bg_color = (0, 104, 71, 255)
    radius = size // 6
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=radius,
        fill=bg_color,
    )

    # 中央字母 M（白色）
    try:
        font = ImageFont.truetype("arial.ttf", size=int(size * 0.6))
    except OSError:
        font = ImageFont.load_default()

    text = "M"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (size - text_w) // 2 - bbox[0]
    y = (size - text_h) // 2 - bbox[1]
    draw.text((x, y), text, fill=(255, 255, 255, 255), font=font)

    return img


def main() -> None:
    out_dir = Path(__file__).resolve().parent.parent / "assets"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 生成多个尺寸
    sizes = [16, 32, 48, 64, 128, 256]
    images = [make_icon(s) for s in sizes]

    ico_path = out_dir / "app.ico"
    # ico 文件：第一张是主图，其余为多尺寸
    images[0].save(ico_path, format="ICO", sizes=[(s, s) for s in sizes], append_images=images[1:])

    # 同时保存一份 png 便于预览
    png_path = out_dir / "app.png"
    images[-1].save(png_path, format="PNG")

    print(f"icon saved: {ico_path}")
    print(f"preview: {png_path}")


if __name__ == "__main__":
    main()
