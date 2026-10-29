"""Bounded admission/cost of the runtime layered image-coordinate proxy.

This inspects the authored mask; it neither paints nor generates reflections.
The Swift reader uses the same periodic, four-neighbour dry-run topology.
"""
import io
from PIL import Image


def background_branch(red, width, height, field):
    """Mask-only interval identities and constrained hidden continuation.

    This matches the Swift image proxy, not a physical depth estimator.
    Raster-contour breaks never promote a lower water interval by column rank.
    """
    columns, parents, lower = [], [], set()
    first = [None] * width

    def root(node):
        while parents[node] != node:
            parents[node] = parents[parents[node]]
            node = parents[node]
        return node

    def crossing(x, y):
        a, b = red[(y - 1) * width + x] / 255, red[y * width + x] / 255
        return (y - .5 + (.5 - a) / (b - a)) / height

    for x in range(width):
        col, begin = [], None
        for y in range(height + 1):
            wet = y < height and red[y * width + x] >= 128
            if wet and begin is None:
                begin = y
            if not wet and begin is not None:
                label = len(parents)
                parents.append(label)
                col.append((begin, y, label))
                begin = None
        if col:
            first[x] = crossing(x, col[0][0])
        columns.append(col)

    for x, left in enumerate(columns):
        right = columns[(x + 1) % width]
        pairs = {(i, j): abs(a - c) for i, (a, b, _) in enumerate(left)
                 for j, (c, d, _) in enumerate(right) if max(a, c) < min(b, d)}
        lbest = {i: min((j for ii, j in pairs if ii == i), key=lambda j: (pairs[i, j], j))
                 for i in range(len(left)) if any(ii == i for ii, _ in pairs)}
        rbest = {j: min((i for i, jj in pairs if jj == j), key=lambda i: (pairs[i, j], i))
                 for j in range(len(right)) if any(jj == j for _, jj in pairs)}
        for i, j in lbest.items():
            if rbest.get(j) == i:
                delta = right[j][0] - left[i][0]
                if abs(delta) <= 1:
                    a, b = root(left[i][2]), root(right[j][2])
                    if a != b:
                        parents[b] = a
                else:
                    lower.add(right[j][2] if delta > 0 else left[i][2])
            for child in range(j + 1, len(right)):
                if (i, child) in pairs and rbest.get(child) == i:
                    lower.add(right[child][2])
        for j, i in rbest.items():
            for prior in range(i + 1, len(left)):
                if (prior, j) in pairs and lbest.get(prior) == j:
                    lower.add(left[prior][2])

    foreground = {root(label) for label in lower}
    observed = [next((crossing(x, a) for a, _, k in col if root(k) not in foreground), None)
                for x, col in enumerate(columns)]
    valid = [x for x, value in enumerate(observed) if value is not None]
    if not valid:
        raise ValueError(field + " has no observable background branch")
    result = [0.] * width
    for index, left in enumerate(valid):
        right = valid[(index + 1) % len(valid)]
        if right <= left:
            right += width
        hull = []
        for x in range(left, right + 1):
            value = observed[x % width] if x in (left, right) else first[x % width]
            if value is None:
                continue
            while len(hull) >= 2:
                a, av = hull[-2]
                b, bv = hull[-1]
                if (bv - av) * (x - b) >= (value - bv) * (b - a):
                    hull.pop()
                else:
                    break
            hull.append((x, value))
        for (a, av), (b, bv) in zip(hull, hull[1:]):
            for x in range(a, b + 1):
                result[x % width] = av + (bv - av) * (x - a) / (b - a)
    return result


def validate_mask_bytes(data, field):
    with Image.open(io.BytesIO(data)) as image:
        if image.mode != "L" or image.width != 2 * image.height or not 2 <= image.width <= 4096:
            raise ValueError(field + " requires a 2:1 grayscale mask")
        width, height = image.size
        red = image.tobytes()
    parents = []
    columns = []
    layered = False
    any_water = False
    for x in range(width):
        col = red[x::width]
        if col[0] >= 128:
            raise ValueError(field + " requires dry pixels above water")
        runs = []
        start = 0
        previous = False
        water_runs = 0
        for y in range(1, height + 1):
            wet = y < height and col[y] >= 128
            if y == height or wet != previous:
                if not previous:
                    if len(parents) >= 65536:
                        raise ValueError(field + " mask topology is too complex")
                    label = len(parents)
                    parents.append(label)
                    runs.append((start, y, label))
                if y < height and wet:
                    water_runs += 1
                    if water_runs > 8:
                        raise ValueError(field + " has too many water intervals")
                start, previous = y, wet
        any_water = any_water or water_runs > 0
        layered = layered or water_runs > 1
        columns.append(runs)
    if not any_water:
        raise ValueError(field + " contains no water")

    def root(node):
        while parents[node] != node:
            parents[node] = parents[parents[node]]
            node = parents[node]
        return node

    for x in range(width):
        for start, end, label in columns[x]:
            for other_start, other_end, other_label in columns[(x + 1) % width]:
                if max(start, other_start) < min(end, other_end):
                    left, right = root(label), root(other_label)
                    if left != right:
                        parents[right] = left
    top = {root(label) for col in columns for start, _, label in col if start == 0}
    objects = {root(label) for col in columns for start, end, label in col
               if start > 0 and end < height and root(label) not in top}
    if len(objects) > 64:
        raise ValueError(field + " has too many isolated dry components")
    if layered:
        background_branch(red, width, height, field)
    return {"width": width, "height": height, "layered": layered,
            "isolatedComponents": len(objects),
            "textureBytes": width * 4 * (3 * 256 + 2 if layered else 256 + 1)}
