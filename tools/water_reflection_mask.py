"""Eligibility of the opt-in single-boundary image reflection proxy.

Read the raw gray mask, including tRNS gray values. Do not infer a coast through
missing water or merge intervals across foreground rocks. Pixel admission is
paired with WaterReflectionRegistration.profile in the reader.
"""
import io
from PIL import Image


def validate_mask_bytes(data, field):
    with Image.open(io.BytesIO(data)) as image:
        if image.mode != 'L' or image.width != 2 * image.height or not 2 <= image.width <= 4096:
            raise ValueError(field + ' requires a 2:1 grayscale shoreline mask')
        width, height = image.size
        red = image.tobytes()
    rows = []
    for x in range(width):
        column = red[x::width]
        starts = [y for y, value in enumerate(column) if value >= 128 and (y == 0 or column[y-1] < 128)]
        if len(starts) != 1 or starts[0] == 0:
            raise ValueError(field + ' requires one water interval below dry pixels in every column')
        rows.append(starts[0])
    for x in range(width):
        other = (x + 1) % width
        lo, hi = min(rows[x], rows[other]) - 1, min(height - 1, max(rows[x], rows[other]) + 1)
        if hi - lo > 256:
            raise ValueError(field + ' shoreline changes too abruptly between columns')
        phases = {0.0, 1.0}
        for y in range(lo, hi + 1):
            a, b = red[y * width + x], red[y * width + other]
            if a != b:
                t = (127.5 - a) / (b - a)
                if 0 < t < 1:
                    phases.add(t)
        phases = sorted(phases)
        if len(phases) > 256:
            raise ValueError(field + ' shoreline interpolation is too complex')
        for a, b in zip(phases, phases[1:]):
            t = (a + b) / 2
            wet = [red[y * width + x] * (1-t) + red[y * width + other] * t >= 127.5 for y in range(lo, hi + 1)]
            starts = [i for i, value in enumerate(wet) if value and (i == 0 or not wet[i-1])]
            if len(starts) != 1 or starts[0] + lo == 0:
                raise ValueError(field + ' shoreline interpolation has an unsupported interval')
