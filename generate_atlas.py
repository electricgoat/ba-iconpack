import os
import json
from PIL import Image
from model.Icon import Icon, CROP_BOX

def main():
    icon_folder = 'icons'
    output_image_path = 'output/atlas.png'
    json_output_path = 'output/icons.json'


    file_list = [f for f in os.listdir('icons') if f.endswith('.png')]
    icons = [Icon(os.path.join('icons', f)) for f in file_list]
    icon_data = [{"name": icon.name, "type": icon.type, "effect": icon.effect, "path": icon.path} for icon in icons]  
    print(json.dumps(icon_data, indent=4))


    # Dictionary to hold icons by type
    icons_by_type = {}

    # Load icons and categorize them by type
    for icon in icons:
        if icon.type not in icons_by_type:
            icons_by_type[icon.type] = []
        icons_by_type[icon.type].append(icon)





    icon_width = CROP_BOX['right'] - CROP_BOX['left']
    icon_height = CROP_BOX['lower'] - CROP_BOX['upper']
    print(f"Icon dimensions: {icon_width}x{icon_height}")

    # Create a new image for the atlas
    atlas_width = 0
    atlas_height = 0
    current_height = 0

    #calculate atlas size
    for icon_type in icons_by_type:
        atlas_width = max(atlas_width, icon_width * len(icons_by_type[icon_type]))
        atlas_height += icon_height

    atlas_image = Image.new('RGBA', (atlas_width, atlas_height))

    for icon_type in icons_by_type:
        print(f"Type: {icon_type}, Count: {len(icons_by_type[icon_type])}")

        section_image = Image.new('RGBA', (icon_width * len(icons), icon_height), (255, 255, 255, 255))
        for index, icon in enumerate(icons_by_type[icon_type]):
            section_image.paste(icon.get_image_cropped(), (index * icon_width, 0))


        atlas_image.paste(section_image, (0, current_height))
        current_height += section_image.height



    # for icon_type, icons in icons_by_type.items():
    #     background = Image.new('RGBA', (ICON_DIMENSIONS['width'] * len(icons), ICON_DIMENSIONS['height']), (255, 255, 255, 255))
    #     for index, icon in enumerate(icons):
    #         icon_path = os.path.join(icon_folder, icon)
    #         icon_image = Image.open(icon_path).resize((ICON_DIMENSIONS['width'],  ICON_DIMENSIONS['height']))
    #         background.paste(icon_image, (index * ICON_DIMENSIONS['width'], 0))


    #     atlas_image.paste(background, (0, current_height))
       

    # Save the atlas image
    atlas_image.save(output_image_path)




if __name__ == "__main__":
    main()