def load_image(image_path):
    from PIL import Image
    return Image.open(image_path)

def save_image(image, save_path):
    image.save(save_path)

def generate_json(icon_data, json_path):
    import json
    with open(json_path, 'w') as json_file:
        json.dump(icon_data, json_file)