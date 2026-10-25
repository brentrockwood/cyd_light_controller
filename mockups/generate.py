"""Generate labeled, static scene-button studies. Run with ESPHome's Python + Pillow."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent
SCALE = 3
COLORS = [(255, 255, 255), (255, 215, 0), (200, 0, 0), (0, 0, 0)]
FONT = Path('/System/Library/Fonts/Supplemental/Arial.ttf')

# name, shape, outline, bulb, off icon
STUDIES = [
    ('01 Current direction', 'square', 'all', 'simple', False),
    ('02 Clean squares', 'square', 'black', 'simple', True),
    ('03 Clean circles', 'circle', 'black', 'simple', True),
    ('04 Outlined circles', 'circle', 'all', 'simple', True),
    ('05 Classic bulb', 'square', 'black', 'classic', True),
    ('06 Classic circles', 'circle', 'black', 'classic', True),
    ('07 Solid bulb', 'square', 'black', 'solid', True),
    ('08 Solid circles', 'circle', 'black', 'solid', True),
    ('09 Radiant bulb', 'square', 'black', 'rays', True),
    ('10 Radiant circles', 'circle', 'black', 'rays', True),
    ('11 Soft dark tile', 'square', 'none', 'classic', True),
    ('12 Soft dark circle', 'circle', 'none', 'solid', True),
    ('13 Borderless black', 'square', 'none-black', 'classic', True),
    ('14 Borderless circles', 'circle', 'none-black', 'simple', True),
    ('15 Color outlines', 'outline', 'all', 'classic', True),
    ('16 Icons only', 'icon', 'none-black', 'rays', True),
    ('17 Solid icons only', 'icon', 'none-black', 'solid', True),
]


def render(study):
    name, shape, outline, bulb, off = study
    image = Image.new('RGB', (360*SCALE, 132*SCALE), '#181818')
    d = ImageDraw.Draw(image)

    def box(coords, fill, radius=0, edge=None, width=1):
        coords = tuple(round(v*SCALE) for v in coords)
        if radius:
            d.rounded_rectangle(coords, radius=radius*SCALE, fill=fill,
                                outline=edge, width=width*SCALE)
        else:
            d.rectangle(coords, fill=fill, outline=edge, width=width*SCALE)

    def ellipse(coords, fill=None, edge=None, width=2):
        d.ellipse(tuple(round(v*SCALE) for v in coords), fill=fill,
                  outline=edge, width=width*SCALE)

    def line(points, color, width=2):
        d.line([(round(x*SCALE), round(y*SCALE)) for x, y in points],
               fill=color, width=width*SCALE, joint='curve')

    def text(x, y, content, size, color):
        d.text((x*SCALE, y*SCALE), content, font=ImageFont.truetype(str(FONT), size*SCALE), fill=color)

    text(20, 8, name, 15, 'white')
    box((20, 34, 339, 107), 'black')
    for i, color in enumerate(COLORS):
        x, y = 28+i*78, 36
        cx, cy = x+35, y+35
        fill = (32, 32, 32) if i == 3 and outline == 'none' else color
        edge = (128, 128, 128) if outline == 'all' or (outline == 'black' and i == 3) else None
        ink = (0, 0, 0) if i < 2 else (255, 255, 255)
        if shape in ('icon', 'outline'):
            ink = color if i < 3 else (210, 210, 210)
            fill = (0, 0, 0)
            edge = ink
        if shape == 'circle':
            ellipse((x, y, x+69, y+69), fill, edge, 1)
        elif shape != 'icon':
            box((x, y, x+69, y+69), fill, 16, edge, 1)

        if bulb == 'simple':
            ellipse((cx-14, cy-21, cx+14, cy+7), edge=ink)
            line([(cx-7, cy+13), (cx+7, cy+13)], ink)
            line([(cx-5, cy+19), (cx+5, cy+19)], ink)
        else:
            solid = bulb == 'solid'
            ellipse((cx-12, cy-21, cx+12, cy+3), fill=ink if solid else None, edge=ink)
            if solid:
                box((cx-7, cy-1, cx+7, cy+11), ink, 2)
            else:
                # Neck and filament distinguish this from the original circle-and-bars glyph.
                line([(cx-10, cy-1), (cx-6, cy+8), (cx-6, cy+11),
                      (cx+6, cy+11), (cx+6, cy+8), (cx+10, cy-1)], ink)
                line([(cx-4, cy-5), (cx, cy), (cx+4, cy-5)], ink, 1)
                line([(cx, cy), (cx, cy+10)], ink, 1)
            line([(cx-6, cy+15), (cx+6, cy+15)], ink)
            line([(cx-4, cy+19), (cx+4, cy+19)], ink)
            if bulb == 'rays' and i != 3:
                for a, b in [((-20, -10), (-25, -10)), ((20, -10), (25, -10)),
                             ((-15, -24), (-19, -28)), ((15, -24), (19, -28)),
                             ((0, -26), (0, -30))]:
                    line([(cx+a[0], cy+a[1]), (cx+b[0], cy+b[1])], ink)
        if i == 3 and off:
            slash = [(cx-19, cy+23), (cx+19, cy-24)]
            line(slash, fill, 6)
            line(slash, ink, 3)

    descriptions = {
        'all': 'All outlines', 'black': 'Black outline only',
        'none': 'No outlines / charcoal off button',
        'none-black': 'No outlines / black blends into background',
    }
    description = 'Colored icons on black' if shape in ('icon', 'outline') else descriptions[outline]
    text(20, 114, description, 11, '#b8b8b8')
    return image


if __name__ == '__main__':
    assert len({s[0] for s in STUDIES}) == len(STUDIES)
    sheet = Image.new('RGB', (2160, ((len(STUDIES)+3)//4)*198), '#181818')
    for index, study in enumerate(STUDIES):
        image = render(study)
        assert image.size == (1080, 396)
        filename = study[0].lower().replace(' ', '-') + '.png'
        image.save(OUT / filename)
        tile = image.resize((540, 198), Image.Resampling.LANCZOS)
        sheet.paste(tile, ((index % 4)*540, (index // 4)*198))
    sheet.save(OUT / 'comparison.png')
    print(f'Created {len(STUDIES)} labeled mockups and comparison.png; firmware untouched.')
