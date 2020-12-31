#!/usr/local/bin/python3
'''
We need to do the following for each image:
    1. Get the date
    2. Convert to JPEG
    3. Overlay date on top of picture
    4. Save picture to S3 ? (question 1)

The images to be processed should be listed from an S3 bucket.

Then:
    1. Re-create GIF from all other images and new images
    2. Upload GIF to S3

Questions:
    1. Can we create a gif from a gif and an/some image(s)?
        If so, we don't need to save any images on S3, only the GIF.

Ideas:
    1. Can we use threading to make this faster?
'''
from datetime import datetime
import exifread
import io
import os
from PIL import Image, ImageFont, ImageDraw
import pyheif
import sys
from wand.image import Image as WandImage  # Depends on ImageMagick
import whatimage


def _get_image_original_date(path: str) -> str:
    '''Return the date that an HEIC image was created as a string.

    Taken from https://stackoverflow.com/a/56946294/3801865.
    '''
    with open(path, 'rb') as image_bytes:
        image_contents = image_bytes.read()

    fmt = whatimage.identify_image(image_contents)
    if fmt in ['heic', 'avif']:
        # https://github.com/carsales/pyheif#the-heiffile-object
        heif_file = pyheif.read_heif(image_contents)

        # Extract metadata
        for metadata in heif_file.metadata or []:
            if metadata['type'] == 'Exif':
                # NOTE: Why don't we break here?
                fstream = io.BytesIO(metadata['data'][6:])

        if 'EXIF DateTimeOriginal' in (tags := exifread.process_file(fstream)):
            return str(tags['EXIF DateTimeOriginal'])

    return ''


def _convert_heic_to_jpeg(input_path: str, output_path: str):
    '''Convert an HEIC image to JPEG.

    Taken from https://stackoverflow.com/a/65064641/3801865.
    '''
    with WandImage(filename=input_path) as original:
        original.format = 'jpeg'
        original.thumbnail(600, 800)  # Resize because iPhone XR originals are huge
        original.save(filename=output_path)


def _overlay_image_with_text(path: str, text: str):
    '''Overlay an image with text.

    Taken from https://stackoverflow.com/a/16377244/3801865.
    '''
    # NOTE: This image should probably be closed, right?
    image = Image.open(path)
    draw = ImageDraw.Draw(image)
    draw.text(
        (25, 0),
        text,
        'white',
        font=ImageFont.truetype("OpenSans-Regular.ttf", 100),
        stroke_fill='black',
        stroke_width=2,
    )
    image.save(path)

def _create_gif(input_path: str, output_path: str):
    '''Create a gif from all images in a directory.'''
    # NOTE: These images should probably be closed, right?
    images = [
        Image.open(os.path.join(input_path, filename))
        for filename in sorted(os.listdir(input_path))
    ]

    images[0].save(
        output_path,
        save_all=True,
        append_images=images[1:],
        duration=100,
        loop=0,
    )


def main():
    # TODO: Get images from an S3 bucket, not a local directory
    IMAGE_FOLDER = sys.argv[1]

    for filename in os.listdir(IMAGE_FOLDER):
        # TODO: Handle non-image files, non-HEIC files, etc.
        IMAGE_PATH = os.path.join(IMAGE_FOLDER, filename)

        # Get the date
        date = datetime.strptime(
            _get_image_original_date(IMAGE_PATH),
            '%Y:%m:%d %H:%M:%S'
        )

        # Convert image to JPEG
        JPEG_PATH = 'jpegs/' + date.strftime('%Y_%m_%d') + '.jpeg'
        _convert_heic_to_jpeg(IMAGE_PATH, JPEG_PATH)

        # Overlay JPEG with date
        _overlay_image_with_text(JPEG_PATH, date.strftime('%m/%d/%Y'))

    _create_gif('jpegs', 'selfies.gif')


if __name__ == "__main__":
    main()
