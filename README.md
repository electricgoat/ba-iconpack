# Icon Atlas Generator

This project is designed to generate an atlas of icons from PNG images. It extracts and crops icons based on their types and creates a JSON file with icon names and their order for CSS generation.

## Project Structure

```
icon-atlas-generator
├── src
│   ├── main.py          # Entry point of the application
│   ├── atlas            # Module for assembling the icon atlas
│   │   └── __init__.py
│   ├── extractor        # Module for extracting and cropping icons
│   │   └── __init__.py
│   ├── utils            # Module for utility functions
│   │   └── __init__.py
│   └── types            # Module for custom types and constants
│       └── __init__.py
├── icons                # Directory for PNG files
│   └── [your PNG files here]
├── output               # Directory for generated files
│   ├── atlas.png        # Assembled icon atlas image
│   └── icons.json       # JSON representation of icon names and order
├── requirements.txt      # Dependencies for the project
└── README.md            # Project documentation
```

## Setup Instructions

1. Clone the repository:
   ```
   git clone [repository-url]
   cd icon-atlas-generator
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Place your PNG files in the `icons` directory.

## Usage

To generate the icon atlas and JSON file, run the following command:
```
python src/main.py
```

This will process the PNG files in the `icons` directory, create an atlas image in the `output` directory, and generate a JSON file with the icon names and their order.

## Contributing

Feel free to submit issues or pull requests if you have suggestions for improvements or new features.