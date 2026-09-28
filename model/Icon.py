from PIL import Image
import os

ICON_TYPES = {
    "Combat_Icon_Buff": "buff",
    "Combat_Icon_CC": "cc",
    "Combat_Icon_Debuff": "debuff",
    "Combat_Icon_Special": "special",
}

ICON_DIMENSIONS = {
    "width": 47,
    "height": 54,
}

CROP_BOX = {
    "left": 4,
    "upper": 6,
    "right": 43,
    "lower": 48,
}

BG_COLOR = {
    "Combat_Icon_Buff": (255, 80, 50, 255),
    "Combat_Icon_CC": (175, 105, 245, 255),
    "Combat_Icon_Debuff": (63 , 158, 238, 255),
    "Combat_Icon_Special": (255, 200, 50, 255),
}

class Icon:

    @property
    def name(self):
        return os.path.splitext(os.path.basename(self.filename))[0]
    
    @property
    def path(self):
        return os.path.abspath(self.filename)
    
    @property
    def effect(self):
        words = self.name.split('_',3)
        return words[-1] if len(words) >= 4 else "unknown"
    
    @property
    def type(self):
        words = self.name.split('_',3)
        return f"{words[0]}_{words[1]}_{words[2]}" if len(words) >= 3 else "unknown"
    


    def __init__(self, filename: str,):
        self.filename = filename

    def __get_mask(self):
        individual_mask_path = os.path.join('masks', f"{self.name}_mask.png")
        type_mask_path = os.path.join('masks', f"{self.type}_mask.png")

        if os.path.exists(individual_mask_path):
            return Image.open(individual_mask_path)
        elif os.path.exists(type_mask_path):
            return Image.open(type_mask_path)
        else:
            print(f"No mask found for {self.name}")
            return None


    def __normalize_background(self, img: Image.Image):
        bg_color = BG_COLOR.get(self.type, (0, 0, 0, 0))
        img = img.convert("RGBA")
        pixels = img.load()
        width, height = img.size

        def is_close(c1, c2, threshold=15):
            #print(f"Comparing {c1} to {c2} with threshold {threshold}: {all(abs(a - b) <= threshold for a, b in zip(c1, c2))}")
            return all(abs(a - b) <= threshold for a, b in zip(c1, c2))

        for y in range(height):
            for x in range(width):
                if is_close(pixels[x, y], bg_color):
                    pixels[x, y] = bg_color
        return img


    def get_image(self):
        """Returns the PIL Image object of the icon."""
        return Image.open(self.filename)
    
    def get_image_masked(self):
        with Image.open(self.filename) as img:
            mask = self.__get_mask()
            if mask is not None:
                img.paste(mask, (0, 0), mask)
            return img.copy()
        

    def get_image_cropped(self):
        return self.__normalize_background(self.get_image_masked().crop((CROP_BOX['left'], CROP_BOX['upper'], CROP_BOX['right'], CROP_BOX['lower'])))