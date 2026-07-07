from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


class ContactSheetService:
    def build(self, frame_paths: list[str], output_path: str | Path, *, columns: int = 3) -> str:
        if not frame_paths:
            raise ValueError("frame_paths cannot be empty.")
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        thumbs: list[Image.Image] = []
        for index, frame_path in enumerate(frame_paths, start=1):
            image = Image.open(frame_path).convert("RGB")
            image.thumbnail((240, 426))
            tile = Image.new("RGB", (260, 466), "white")
            x = (260 - image.width) // 2
            tile.paste(image, (x, 28))
            draw = ImageDraw.Draw(tile)
            draw.text((12, 8), f"Frame {index}", fill=(20, 20, 20))
            draw.text((12, 444), Path(frame_path).name[:34], fill=(80, 80, 80))
            thumbs.append(tile)
        rows = (len(thumbs) + columns - 1) // columns
        sheet = Image.new("RGB", (columns * 260, rows * 466), (245, 245, 245))
        for index, tile in enumerate(thumbs):
            x = (index % columns) * 260
            y = (index // columns) * 466
            sheet.paste(tile, (x, y))
        sheet.save(output)
        return output.as_posix()
