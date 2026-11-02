"""Generate clearly fake sample files for manual testing of the onboarding flow.

Usage:  python scripts/generate_samples.py
Output: samples/sample_id_sharp.png, samples/sample_id_blurry.png, samples/sample_unsupported.pdf

The ID card is synthetic, uses a made-up person and number, and is watermarked SAMPLE.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "samples"


def make_card() -> Image.Image:
    width, height = 1000, 630
    card = Image.new("RGB", (width, height), (232, 238, 244))
    draw = ImageDraw.Draw(card)
    title = ImageFont.load_default(size=30)
    label = ImageFont.load_default(size=18)
    value = ImageFont.load_default(size=32)

    draw.rectangle([0, 0, width, 90], fill=(170, 30, 45))
    draw.text((40, 14), "REPUBLICA DEL PERU", font=title, fill="white")
    draw.text((40, 52), "DOCUMENTO NACIONAL DE IDENTIDAD  (SAMPLE)", font=label, fill="white")

    draw.rectangle([40, 130, 280, 430], fill=(160, 170, 185), outline=(60, 70, 90), width=3)
    draw.text((100, 270), "PHOTO", font=title, fill=(90, 100, 115))

    rows = [
        ("DNI", "12345678"),
        ("Primer apellido", "FERNANDEZ"),
        ("Segundo apellido", "TORRES"),
        ("Pre nombres", "MARIA"),
        ("Fecha de nacimiento", "01 01 1990"),
    ]
    y = 125
    for name, text in rows:
        draw.text((320, y), name, font=label, fill=(90, 100, 115))
        draw.text((320, y + 22), text, font=value, fill=(15, 25, 40))
        y += 72

    draw.text((40, 560), "SAMPLE - NOT A REAL DOCUMENT - FOR SOFTWARE TESTING ONLY", font=label, fill=(150, 30, 45))
    return card


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    card = make_card()
    card.save(OUTPUT_DIR / "sample_id_sharp.png")
    card.filter(ImageFilter.GaussianBlur(6)).save(OUTPUT_DIR / "sample_id_blurry.png")
    (OUTPUT_DIR / "sample_unsupported.pdf").write_bytes(
        b"%PDF-1.4\n% Fake PDF used to test the unsupported file type error (415).\n%%EOF\n"
    )
    print(f"Samples written to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
