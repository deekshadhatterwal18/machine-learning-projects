import pickle
from pathlib import Path
import os
import cv2
import face_recognition
from PIL import Image, ExifTags
import numpy as np


ROOT = Path(__file__).parent
IMAGES_DIR = ROOT / "images"
ENC_DIR = ROOT / "encoded_faces"
ENC_DIR.mkdir(parents=True, exist_ok=True)
ENC_FILE = ENC_DIR / "encodings.pkl"


def load_and_fix_image(image_path):
    """
    Load image using PIL, auto-correct orientation (iPhone/Mac EXIF issue)
    then convert to OpenCV BGR for face_recognition.
    """

    try:
        img = Image.open(image_path)

        # Auto-rotate based on EXIF orientation
        try:
            for orientation in ExifTags.TAGS.keys():
                if ExifTags.TAGS[orientation] == "Orientation":
                    break
            if hasattr(img, "_getexif"):
                exif = img._getexif()
                if exif is not None:
                    orientation_value = exif.get(orientation, None)
                    if orientation_value == 3:
                        img = img.rotate(180, expand=True)
                    elif orientation_value == 6:
                        img = img.rotate(270, expand=True)
                    elif orientation_value == 8:
                        img = img.rotate(90, expand=True)
        except:
            pass

        # Convert to CV2 RGB array
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

    except Exception as e:
        print(f"[ERROR] Unable to process image {image_path}: {e}")
        return None



def detect_face_encodings(rgb_image):
    """
    Try multiple detection strategies until a face is found.
    """

    # First try: CNN model (highest accuracy)
    boxes = face_recognition.face_locations(
        rgb_image, number_of_times_to_upsample=2, model="cnn"
    )
    if boxes:
        enc = face_recognition.face_encodings(rgb_image, boxes, num_jitters=5)
        if enc:
            return enc[0]

    # Second try: HOG model (default)
    boxes = face_recognition.face_locations(
        rgb_image, number_of_times_to_upsample=2, model="hog"
    )
    if boxes:
        enc = face_recognition.face_encodings(rgb_image, boxes, num_jitters=3)
        if enc:
            return enc[0]

    # Third try: resize image & detect
    small = cv2.resize(rgb_image, (0, 0), fx=0.75, fy=0.75)
    boxes = face_recognition.face_locations(small, model="hog")
    if boxes:
        enc = face_recognition.face_encodings(small, boxes, num_jitters=2)
        if enc:
            return enc[0]

    # If still nothing → fail
    return None


def build_encodings():
    known_encodings = []
    known_names = []

    if not IMAGES_DIR.exists():
        print(f"[ERROR] Images folder not found: {IMAGES_DIR}")
        return

    people = [p for p in IMAGES_DIR.iterdir() if p.is_dir()]
    if not people:
        print("[ERROR] No student folders in images/.")
        return

    print(f"[INFO] Found {len(people)} student folder(s).")

    for person_dir in sorted(people):
        name = person_dir.name
        img_files = [
            f for f in person_dir.iterdir()
            if f.suffix.lower() in (".jpg", ".jpeg", ".png")
        ]

        if not img_files:
            print(f"[WARN] No images for {name}, skipping.")
            continue

        for img_path in img_files:
            print(f"[INFO] Processing {name}: {img_path.name}")

            # Load image safely + fix orientation
            img = load_and_fix_image(str(img_path))
            if img is None:
                print(f"[WARN] Could not load {img_path.name}, skipping.")
                continue

            # Resize big images for better detection
            img = cv2.resize(img, (600, 600))

            # Convert to RGB
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

            # -------- DETECT FACE --------
            enc = detect_face_encodings(rgb)

            if enc is None:
                print(f"[WARN] No face found in {img_path.name}, skipping.")
                continue

            # SAVE encoding
            known_encodings.append(enc)
            known_names.append(name)
            print(f"[OK] Face encoded for {name}")

    # ------------ SAVE FILE ------------
    if not known_encodings:
        print("[ERROR] No encodings created. Fix images.")
        return

    data = {"encodings": known_encodings, "names": known_names}

    with open(ENC_FILE, "wb") as f:
        pickle.dump(data, f)

    print(f"[DONE] Saved {len(known_encodings)} encodings for {len(set(known_names))} student(s).")
    print(f"-> {ENC_FILE}")


if __name__ == "__main__":
    build_encodings()
