'''
USAGE for test_major

python test_major.py \
  --source "./images/test1.jpg" \
  --ref "./images/A1.jpg" \
  --out "./images/output.png" \
  --prompt "Use the SECOND image shows the hairstyle of a detailed cornrows: A complex, artistic geometric pattern of all-back braids that shows lots of technique, precision and symmetry. Make the FIRST image look like it has the same hairstyle. Keep the subject. Return ONLY the edited image."

'''


import os
import argparse
from google import genai
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="Path to the image to be transformed")
    ap.add_argument("--ref", required=True, help="Path to the reference image (style/object/background guide)")
    ap.add_argument("--out", default="edited.png", help="Output path (png recommended)")
    ap.add_argument(
        "--prompt",
        default=(
            "Use the SECOND image as the reference. Edit the FIRST image to match the reference's style "
            "and color palette while keeping the first image's subject and composition. "
            "Return ONLY the edited image."
        ),
        help="Editing instruction",
    )
    ap.add_argument("--model", default="gemini-3.1-flash-image-preview", help="e.g. gemini-2.5-flash-image")
    args = ap.parse_args()

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise SystemExit("Missing GEMINI_API_KEY (or GOOGLE_API_KEY) env var.")

    client = genai.Client(api_key=api_key)

    source_img = Image.open(args.source).convert("RGB")
    ref_img = Image.open(args.ref).convert("RGB")

    # Multi-image input: [prompt, source, reference]
    # Official image model examples show passing PIL Images directly. :contentReference[oaicite:2]{index=2}
    response = client.models.generate_content(
        model=args.model,
        contents=[args.prompt, source_img, ref_img],
    )

    # Prefer response.parts (as in official docs), but fall back to candidates if needed.
    parts = getattr(response, "parts", None)
    if not parts and getattr(response, "candidates", None):
        parts = response.candidates[0].content.parts

    saved = False
    for part in parts or []:
        if getattr(part, "inline_data", None) is not None:
            out_image = part.as_image()
            out_image.save(args.out)
            print(f"✅ Saved edited image to: {args.out}")
            saved = True
            break
        elif getattr(part, "text", None):
            # Sometimes the model returns text too (warnings/notes)
            print("Model text:", part.text)

    if not saved:
        raise RuntimeError("No image returned. Try strengthening the prompt: 'Return ONLY an image.'")


if __name__ == "__main__":
    main()