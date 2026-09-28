def extract_icons(icon_folder):
    import os
    from PIL import Image

    icons = {}
    for filename in os.listdir(icon_folder):
        if filename.endswith('.png'):
            icon_name = os.path.splitext(filename)[0]
            icon_path = os.path.join(icon_folder, filename)
            icons[icon_name] = Image.open(icon_path)

    return icons

def crop_icon(icon_image, crop_box):
    return icon_image.crop(crop_box)

def apply_mask(icon_image, mask_image):
    icon_image.paste(mask_image, (0, 0), mask_image)
    return icon_image

def extract_and_crop_icons(icon_folder, mask_folder, crop_box):
    icons = extract_icons(icon_folder)
    cropped_icons = {}

    for icon_name, icon_image in icons.items():
        mask_path = os.path.join(mask_folder, f"{icon_name}_mask.png")
        if os.path.exists(mask_path):
            mask_image = Image.open(mask_path)
            icon_image = apply_mask(icon_image, mask_image)

        cropped_icons[icon_name] = crop_icon(icon_image, crop_box)

    return cropped_icons