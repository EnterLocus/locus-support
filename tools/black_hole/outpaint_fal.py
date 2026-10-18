#!/usr/bin/env python3
# Copyright 2026 EnterLocus.com
# SPDX-License-Identifier: Apache-2.0
"""Optional and paid: extend a nebula photo with a dark margin using Bria Expand on fal.ai.

A photo whose gas still glows at its edges shows a frame when it is placed in
the sky. This helper keeps the photographed area unchanged in the centre of a
larger canvas and asks fal.ai's `fal-ai/bria/expand` model to generate the
surrounding fade into black space. You are not required to use it: choosing a
nebula photographed on a black background, or the `fade` mode of
compose_sky.py, avoids most frames without AI.

Using it calls a paid third-party service with your own fal.ai account: each
run costs about US$0.04 at the time of writing (check fal.ai for current
pricing) and sends a downscaled copy of the photo to fal.ai. A View that
contains AI-generated pixels must say so in its provenance: set
`"aiGenerated": true` and an `"aiProvider"` such as
"Bria Expand (fal.ai), nebula margins only", and describe what was generated
in `modificationNotes`.

    export FAL_KEY=...            # your own key; never commit it
    python3 outpaint_fal.py weic2212a.jpg tarantula-expanded.png --confirm-paid \\
        --prompt "The Tarantula Nebula, its glowing gas fading gradually into empty black space"

A JSON record of the request (model, prompt, seed, sizes, request ID; never
the key) is written next to the output for your provenance notes.
"""
import argparse
import base64
import io
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = None
ENDPOINT = "https://queue.fal.run/fal-ai/bria/expand"
NEGATIVE = "frame, border, rectangle, text, watermark, bright edge, vignette box, grid"


def request_json(url, key, body=None, timeout=120):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST" if body is not None else "GET",
                                 headers={"Authorization": "Key " + key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def build_body(photo, inner_width, canvas, prompt, seed):
    """The Bria Expand request: the photo, downscaled to inner_width, centred on the canvas."""
    inner_height = round(inner_width * photo.height / photo.width)
    if inner_width > canvas[0] or inner_height > canvas[1]:
        raise SystemExit("the canvas must be larger than the downscaled photo (%dx%d)" % (inner_width, inner_height))
    small = photo.resize((inner_width, inner_height), Image.LANCZOS)
    buffer = io.BytesIO()
    small.save(buffer, "JPEG", quality=95)
    location = [(canvas[0] - inner_width) // 2, (canvas[1] - inner_height) // 2]
    return {"image_url": "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii"),
            "canvas_size": list(canvas), "original_image_size": [inner_width, inner_height],
            "original_image_location": location, "prompt": prompt, "negative_prompt": NEGATIVE, "seed": seed}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("photo", help="the nebula photo you downloaded")
    ap.add_argument("output", help="PNG to write")
    ap.add_argument("--prompt", required=True, help="describe the nebula fading into black space")
    ap.add_argument("--inner-width", type=int, default=2600, help="width of the kept photo on the canvas")
    ap.add_argument("--canvas", default="4400x4400", help="output canvas WIDTHxHEIGHT (default 4400x4400)")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--confirm-paid", action="store_true",
                    help="required: you understand this calls fal.ai with your own key and costs money")
    args = ap.parse_args(argv)
    if not args.confirm_paid:
        ap.error("this calls a paid service; add --confirm-paid to proceed")
    key = os.environ.get("FAL_KEY")
    if not key:
        ap.error("set FAL_KEY to your own fal.ai API key")
    out = Path(args.output)
    if out.exists():
        ap.error("refusing to overwrite %s" % out)
    canvas = tuple(int(x) for x in args.canvas.lower().split("x"))
    photo = Image.open(args.photo).convert("RGB")
    body = build_body(photo, args.inner_width, canvas, args.prompt, args.seed)

    submitted = request_json(ENDPOINT, key, body)
    print("submitted", submitted.get("request_id"), flush=True)
    for _ in range(200):
        status = request_json(submitted["status_url"], key)
        if status.get("status") == "COMPLETED":
            break
        if status.get("status") not in ("IN_QUEUE", "IN_PROGRESS"):
            sys.exit("fal.ai request failed: %s" % status)
        time.sleep(3)
    else:
        sys.exit("fal.ai request did not finish in time; request %s" % submitted.get("request_id"))
    result = request_json(submitted["response_url"], key)
    with urllib.request.urlopen(result["image"]["url"], timeout=300) as response:
        data = response.read()
    Image.open(io.BytesIO(data)).save(out)
    record = {"model": "fal-ai/bria/expand", "source": Path(args.photo).name, "prompt": args.prompt,
              "negativePrompt": NEGATIVE, "seed": args.seed, "inner": body["original_image_size"],
              "canvas": list(canvas), "location": body["original_image_location"],
              "request": submitted.get("request_id")}
    out.with_suffix(".json").write_text(json.dumps(record, indent=1) + "\n")
    print("expanded", out, "- remember aiGenerated and aiProvider in your provenance")


if __name__ == "__main__":
    main()
