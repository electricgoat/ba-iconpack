import os
import json
from PIL import Image
from src.extractor import extract_icons
from src.atlas import create_icon_atlas
from src.utils import save_image, generate_json
from src.icon_types import ICON_TYPES

def main():
    # Step 1: Extract icons from the PNG files
    icons = extract_icons('icons')

    # # Step 2: Create an atlas from the extracted icons
    # atlas_image, icon_order = create_atlas(icons)  # <-- fix usage

    # # Step 3: Save the atlas image
    # save_image(atlas_image, 'output/atlas.png')

    # # Step 4: Generate and save the JSON file
    # generate_json(icon_order, 'output/icons.json')
    create_icon_atlas('icons', 'output/atlas.png', 'output/icons.json')

if __name__ == "__main__":
    main()