import requests  # type: ignore
import streamlit as st  # type: ignore
from PIL import Image, ImageDraw, ImageFont, ImageOps  # type: ignore
import io
import os
import random

""" Convert PlantDoc dataset to a format accepted by BigML
The script assumes it is executed from the same folder that
contains the orignal dataset repository:
https://github.com/pratikkayal/PlantDoc-Object-Detection-Dataset
"""

import shutil
import json
from  pathlib import Path
from collections import Counter
import csv
import random
import string


def analyze_classes(labels: Path):
    with labels.open("r") as f:
        reader = csv.DictReader(f)
        classes = [row["class"] for row in reader]
    print(Counter(classes))

def _gen_dataset_folder(name: str):
    path = Path(name)
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(exist_ok=True)
    return path

def _hash():
    available_chars= string.hexdigits[:16]
    return ''.join(
        random.choice(available_chars)
        for dummy in range(16))

def _ensure_img(folder: Path, copied_files: dict, original_name: str, output_folder: Path):
    if original_name in copied_files:
        return copied_files[original_name]
    src = folder / original_name
    if not src.exists():
        return False
    new_name = f"{_hash()}{Path(original_name).suffix}"
    copied_files[original_name] = new_name
    shutil.copyfile(src, output_folder / new_name)
    return new_name

def _add_label(output_labels: dict, new_file_name: str, row: dict):
    if new_file_name not in output_labels:
        output_labels[new_file_name] = []
    output_labels[new_file_name].append(
        {
            "label": row["class"],
            "xmin": row["xmin"],
            "xmax": row["xmax"],
            "ymin": row["ymin"],
            "ymax": row["ymax"],

        }
    )

def _store_new_labels(output_labels: dict, output_folder: Path):
    output = []
    for fname, boxes in output_labels.items():
        output.append({"file": fname, "boxes": boxes})        
    with open(output_folder / "labels.json", 'w') as f:
         json.dump(output, f)

def gen_dataset(folder: Path, labels: Path, dataset_name: str, classes: list[str]):
    output_folder = _gen_dataset_folder(dataset_name)
    copied_files: dict = {}
    output_labels: dict = {}
    with labels.open("r") as f:
        reader = csv.DictReader(f)
        for label in reader:
            if label["class"] in classes or len(classes)==0:
                dst = _ensure_img(folder, copied_files, label["filename"], output_folder)
                if dst:
                    _add_label(output_labels, dst, label)
        _store_new_labels(output_labels, output_folder)
    
                

plantdoc_healthy = [
    "Blueberry leaf", "Peach leaf", "Raspberry leaf", "Strawberry leaf",
    "Tomato leaf", "Bell_pepper leaf", "Soyabean leaf", "Apple leaf",
    "Cherry leaf", "grape leaf", "Potato leaf"
]

plantdoc_healthy_5 = [
    "Blueberry leaf", "Peach leaf", "Raspberry leaf", "Strawberry leaf", "Tomato leaf",
]

plantdoc_10 =  [
    "Blueberry leaf", "Tomato leaf yellow virus", "Peach leaf", "Raspberry leaf",
    "Strawberry leaf", "Tomato Septoria leaf spot", "Tomato leaf", "Corn leaf blight",
    "Potato leaf early blight", "Bell_pepper leaf"
]

plantdoc = []

plantdoc_tomato = [
    "Tomato leaf yellow virus", "Tomato Septoria leaf spot", "Tomato leaf", "Tomato mold leaf",
    "Tomato leaf bacterial spot", "Tomato leaf mosaic virus", "Tomato leaf late blight",
    "Tomato Early blight leaf", "Tomato two spotted spider mites leaf"
]


if __name__ == "__main__":
    analyze_classes(Path("train_labels.csv"))                     
    gen_dataset(Path("TRAIN"), Path("train_labels.csv"), "plantdoc-healthy-10-train", plantdoc_healthy_10)
API_URL = "https://labs.dev.bigml.io/andromeda/"
API_USERNAME = os.getenv("BIGML_USERNAME")
API_KEY = os.getenv("BIGML_API_KEY")
API_AUTH = f"username={API_USERNAME};api_key={API_KEY}"
FONT = ImageFont.truetype("img/roboto.ttf", 25)
MODEL = "deepnet/5JidvaoVsQ28fCiJg3tBge21vwS"
PREDICTION_THRESHOLD = 0.4
HEALTHY_CLASSES =  ["Blueberry leaf", "Peach leaf", "Raspberry leaf", "Strawberry leaf",
                    "Tomato leaf", "Bell_pepper leaf"]
DISEASE_CLASSES = ["Tomato leaf yellow virus", "Tomato Septoria leaf spot",
                   "Corn leaf blight", "Potato leaf early blight"]


def resize(img, width):
    """ Resize an imge to a given width maintaining aspect ratio """
    percent = width / float(img.size[0])
    return img.resize((width, int((float(img.size[1]) * float(percent)))))


API_URL = "https://labs.dev.bigml.io/andromeda/"
API_USERNAME = os.getenv("BIGML_USERNAME")
API_KEY = os.getenv("BIGML_API_KEY")
API_AUTH = f"username={API_USERNAME};api_key={API_KEY}"

def detection(uploaded_file):
    # Upload image to BigML as a source
    source_response = requests.post(
        f"{API_URL}source?{API_AUTH}",
        files={"file": ("plant_image", uploaded_file)}
    )
    source = source_response.json()["resource"]
    # Generate prediction data
    data = {"model": MODEL, "input_data": {"000002": source}}
    response = requests.post(f"{API_URL}prediction?{API_AUTH}", json=data)
    regions = response.json()["prediction"].get("000000", [])
    # Remove the source, we don't need it any more
    requests.delete(f"{API_URL}{source}?{API_AUTH}")
    return [r for r in regions if r[5]>PREDICTION_THRESHOLD]


def draw_predictions(pil_image, boxes):
    """ Draw BigML predictions in the image, adding a black border too """
    w, h = pil_image.size
    draw = ImageDraw.Draw(pil_image)
    for box in boxes:
        label, xmin,ymin, xmax, ymax, confidence = box
        draw.rectangle(((xmin*w, ymin*h), (xmax*w, ymax*h)), width=9, outline="#eee")
        draw.text(
            (xmin*w+20, ymin*h+random.randint(10, 40)),
            f"{label}: {str(confidence)[:3]}", font=FONT,  fill="#eee"
        )
    return ImageOps.expand(pil_image ,border=50,fill='black')


def gen_message(boxes):
    """ Generate output message for predictions """
    labels = set([box[0] for box in boxes])
    healthy = labels.intersection(set(HEALTHY_CLASSES))
    diseases = labels.intersection(set(DISEASE_CLASSES))
    if len(diseases) > 0:        
        st.warning(f"🦠 Your plants needs a doctor! Found **{','.join(diseases)}**!")
    elif len(healthy) > 0:
        st.success(f"🪴 Your plants have good health! Found **{','.join(healthy)}**!")
    else:
        st.error("No plant was found")


st.set_page_config(
    layout="wide",
    page_title="Plant Disease Detection",
    page_icon="🌱",
)

# Sidebar information
description = """ Detect leafs from different kinds of plants and
diagnose common **diseases** in them.  """
image = Image.open('img/BigML.png')
st.sidebar.image(image, width=100)
st.sidebar.write(description)
st.sidebar.write("Powered by [BigML](https://bigml.com)")

# Page title
st.title("🌱 BigML Plant Disease Detection")
classes = "HEALTHY:\n"
for leaf in HEALTHY_CLASSES:
    classes += f"- {leaf}\n"
classes += "\nDISEASES:\n"
for leaf in DISEASE_CLASSES:
    classes += f"- {leaf}\n"

with st.expander("⚠️ Disease detection model was trained with a small dataset. It can be inaccurate sometimes. It should be able to find the following classes: "):
    st.write(classes) 


left, right = st.columns(2)

# Example images
examples = {
    "Example Tomato": "img/tomato-septoria-3-500x384.jpg",
    "Example Raspberry": "img/plant8.jpg",
    "Example Potato": "img/Potato-Blight-on-Leaves.jpg",    
    "Example Bell pepper": "img/Bell-pepper-leaves.jpg"
}

with left.expander(label="Example Plants", expanded=True):
    option = st.selectbox('Choose one example image...', examples.keys(),index=0)
    clicked = st.button("Diagnose selected image")
    if clicked:
        example_file = open(examples[option], 'rb')

# File uploader
msg = "Or upload your plant image..."
with right.form("submit", clear_on_submit=True):
    uploaded_file = st.file_uploader(msg, type=["png ", "jpg", "jpeg"])
    submitted = st.form_submit_button("Diagnose uploaded image")


file_to_predict = None
if clicked and example_file:
    file_to_predict = example_file
elif uploaded_file and submitted:
    file_to_predict = uploaded_file


# Prediction Output
if file_to_predict:
    st.subheader("Detection result")
    with st.spinner('Diagnose in progress. Please wait...'):
        boxes = detection(file_to_predict)
        image = resize(Image.open(file_to_predict), 1000)
        output_image = draw_predictions(image, boxes)
        gen_message(boxes)
        st.image(output_image, width=700)
        uploaded_file = None
