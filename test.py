# import a utility function for loading Roboflow models
from inference import get_model

# define the image url to use for inference
image = "https://media.roboflow.com/inference/people-walking.jpg"

# load a pre-trained yolov8n model
model = get_model(model_id="yolov8n-640")

# run inference on our chosen image, image can be a url, a numpy array, a PIL image, etc.
results = model.infer(image)

# for p in results[0].predictions:
#     print(f"Class: {p.class_name}")
#     print(f"Confidence: {p.confidence:.2f}")
#     print(f"Bounding Box: x={p.x}, y={p.y}, w={p.width}, h={p.height}")
#     print("-" * 30)

clean = [
    {
        "class": p.class_name,
        "confidence": float(p.confidence),
        "x": float(p.x),
        "y": float(p.y),
        "width": float(p.width),
        "height": float(p.height)
    }
    for p in results[0].predictions
]

print(clean)
