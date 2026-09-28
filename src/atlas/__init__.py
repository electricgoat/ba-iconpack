def create_icon_atlas(icon_folder, output_image_path, json_output_path):
    import os
    from PIL import Image
    import json

    # Dictionary to hold icons by type
    icons_by_type = {}

    # Load icons and categorize them by type
    for filename in os.listdir(icon_folder):
        if filename.endswith('.png'):
            icon_type = filename.split('_')[2]  # Assuming the type is the third part of the filename
            if icon_type not in icons_by_type:
                icons_by_type[icon_type] = []
            icons_by_type[icon_type].append(filename)

    # Create a new image for the atlas
    atlas_width = 0
    atlas_height = 0
    icon_size = 64  # Assuming each icon is 64x64 pixels
    for icon_type, icons in icons_by_type.items():
        # Create a solid color background for each type
        background = Image.new('RGBA', (icon_size * len(icons), icon_size), (255, 255, 255, 255))
        for index, icon_name in enumerate(icons):
            icon_path = os.path.join(icon_folder, icon_name)
            icon_image = Image.open(icon_path).resize((icon_size, icon_size))
            background.paste(icon_image, (index * icon_size, 0))

        # Update atlas dimensions
        atlas_width = max(atlas_width, background.width)
        atlas_height += background.height

    # Create the final atlas image
    atlas_image = Image.new('RGBA', (atlas_width, atlas_height))
    current_height = 0
    icon_order = []

    for icon_type, icons in icons_by_type.items():
        background = Image.new('RGBA', (icon_size * len(icons), icon_size), (255, 255, 255, 255))
        for index, icon_name in enumerate(icons):
            icon_path = os.path.join(icon_folder, icon_name)
            icon_image = Image.open(icon_path).resize((icon_size, icon_size))
            background.paste(icon_image, (index * icon_size, 0))
            icon_order.append(icon_name)

        atlas_image.paste(background, (0, current_height))
        current_height += background.height

    # Save the atlas image
    atlas_image.save(output_image_path)

    # Save the JSON file
    with open(json_output_path, 'w') as json_file:
        json.dump(icon_order, json_file)

def create_atlas(icons):
    """
    Accepts a list of icon dicts: [{'name': ..., 'type': ..., 'image': PIL.Image}, ...]
    Returns: (atlas_image, icon_order)
    """
    # Group icons by type
    icons_by_type = {}
    for icon in icons:
        icon_type = icon['type']
        icons_by_type.setdefault(icon_type, []).append(icon)

    # Set cropped icon size (as per your requirements)
    icon_width, icon_height = 40, 42

    # Calculate atlas dimensions
    atlas_width = max(len(group) for group in icons_by_type.values()) * icon_width
    atlas_height = len(icons_by_type) * icon_height

    # Create atlas image
    atlas_image = Image.new('RGBA', (atlas_width, atlas_height), (255, 255, 255, 0))
    icon_order = []

    y_offset = 0
    for icon_type, group in icons_by_type.items():
        x_offset = 0
        for icon in group:
            # Assume icon['image'] is already cropped/masked
            atlas_image.paste(icon['image'], (x_offset, y_offset), icon['image'])
            icon_order.append(icon['name'])
            x_offset += icon_width
        y_offset += icon_height

    return atlas_image, icon_order

# Example usage
# create_icon_atlas('path_to_icons', 'output/atlas.png', 'output/icons.json')