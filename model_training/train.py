from ultralytics import YOLO


def start_training():
    # Load a model
    model = YOLO("yolo11n.pt")  # load a pretrained model (recommended for training)

    # Train the model
    results = model.train(data="../ultralytics/cfg/datasets/wow_coco8.yaml", epochs=500, imgsz=1600, batch=6, workers=4)


if __name__ == '__main__':
    start_training()
    