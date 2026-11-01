"""Generate deterministic desktop icons from the LegalMask shield mark."""

from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
SIZE = 1024


def _draw_icon() -> Image.Image:
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle(
        (36, 36, SIZE - 36, SIZE - 36),
        radius=220,
        fill="#0b1f3a",
    )
    draw.rounded_rectangle(
        (66, 66, SIZE - 66, SIZE - 66),
        radius=194,
        outline="#204b79",
        width=12,
    )

    shield = [
        (512, 190),
        (770, 285),
        (744, 584),
        (680, 706),
        (512, 838),
        (344, 706),
        (280, 584),
        (254, 285),
    ]
    draw.polygon(shield, fill="#173a63", outline="#f8f4e8", width=28)
    draw.line(
        [(378, 522), (472, 616), (665, 414)],
        fill="#f8f4e8",
        width=46,
        joint="curve",
    )
    return image


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    image = _draw_icon()
    image.save(ASSETS / "icon.png")
    image.save(
        ASSETS / "icon.ico",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    image.save(
        ASSETS / "icon.icns",
        sizes=[
            (16, 16),
            (32, 32),
            (64, 64),
            (128, 128),
            (256, 256),
            (512, 512),
            (1024, 1024),
        ],
    )


if __name__ == "__main__":
    main()
