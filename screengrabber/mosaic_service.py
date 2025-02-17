import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, List
from PIL import Image as PILImage
from io import BytesIO


@dataclass
class Image:
    file: bytes
    width: int
    height: int

    def to_pil_image(self) -> PILImage.Image:
        """Convert bytes to PIL Image."""
        return PILImage.open(BytesIO(self.file))

    @property
    def aspect_ratio(self) -> float:
        """Calculate aspect ratio of the image."""
        return self.width / self.height


class MosaicLayout:
    def __init__(self, target_width: int, images: List[Image], border_size: int = 10):
        self.target_width = target_width
        self.images = images
        self.border_size = border_size
        self.rows: List[List[Tuple[Image, Tuple[int, int]]]] = []

    def _should_combine_horizontally(
        self, img1: Image, img2: Image, tolerance: float = 0.2
    ) -> bool:
        """
        Determine if two images should be combined horizontally based on their aspect ratios.

        Args:
            img1: First image
            img2: Second image
            tolerance: Maximum allowed difference in aspect ratios (as a fraction)

        Returns:
            bool: True if images should be combined horizontally
        """
        # Compare aspect ratios
        ar1 = img1.aspect_ratio
        ar2 = img2.aspect_ratio

        # Calculate relative difference
        diff = abs(ar1 - ar2) / max(ar1, ar2)

        # Images with similar aspect ratios should be combined horizontally
        return diff <= tolerance

    def _group_images(self) -> List[List[Image]]:
        """
        Group images into rows based on aspect ratios and similarity.
        """
        if not self.images:
            return []

        groups = []
        current_group = [self.images[0]]

        for i in range(1, len(self.images)):
            current_img = self.images[i]
            prev_img = current_group[-1]

            # Check if current image should be combined with previous group
            if (
                self._should_combine_horizontally(prev_img, current_img)
                and len(current_group) < 3
            ):  # Limit group size to prevent overly wide rows
                current_group.append(current_img)
            else:
                groups.append(current_group)
                current_group = [current_img]

        if current_group:
            groups.append(current_group)

        return groups

    def calculate_layout(
        self,
    ) -> Tuple[List[List[Tuple[Image, Tuple[int, int]]]], Tuple[int, int]]:
        """
        Calculate the optimal layout for the mosaic, prioritizing horizontal arrangement.
        Returns the layout and the final dimensions (width, height).
        """
        if not self.images:
            raise ValueError("No images provided for mosaic")

        # Group images based on aspect ratios
        grouped_images = self._group_images()

        # Process each group into a row
        for group in grouped_images:
            # Calculate optimal height for this group
            group_width_ratio = sum(img.aspect_ratio for img in group)
            target_height = int(self.target_width / group_width_ratio)

            # Scale images in the group
            row = []
            available_width = self.target_width - (self.border_size * (len(group) - 1))
            total_scaled_width = 0

            for img in group:
                width = int(target_height * img.aspect_ratio)
                height = target_height
                row.append((img, (width, height)))
                total_scaled_width += width

            # Adjust for exact fit
            scale_factor = available_width / total_scaled_width
            adjusted_row = []
            for img, (width, height) in row:
                new_width = int(width * scale_factor)
                new_height = int(height * scale_factor)
                adjusted_row.append((img, (new_width, new_height)))

            self.rows.append(adjusted_row)

        # Calculate final dimensions
        final_width = self.target_width
        final_height = 0
        for i, row in enumerate(self.rows):
            row_height = max(img[1][1] for img in row)
            if i > 0:  # Add border height only between rows
                final_height += self.border_size
            final_height += row_height

        return self.rows, (final_width, final_height)


class MosaicService:
    def __init__(self, logger: Optional[logging.Logger] = None):
        self._logger = logger or logging.getLogger(__name__)

    def create_mosaic(
        self, images: List[Image], width: int = 1200, border_size: int = 10
    ) -> bytes:
        """
        Create a mosaic from multiple images without borders on edges

        Args:
            images: List of Image objects
            width: Target width of the mosaic
            border_size: Size of the border between images in pixels

        Returns:
            bytes: Mosaic image in PNG format
        """
        try:
            layout = MosaicLayout(width, images, border_size)
            rows, (mosaic_width, mosaic_height) = layout.calculate_layout()

            # Create new image with white background
            mosaic = PILImage.new("RGB", (mosaic_width, mosaic_height), "white")

            # Current Y position (start at 0, no border)
            y_offset = 0

            for row_index, row in enumerate(rows):
                x_offset = 0  # Start at 0, no left border
                row_height = max(dims[1] for _, dims in row)

                for img_index, (image, (img_width, img_height)) in enumerate(row):
                    try:
                        # Open and resize image
                        pil_image = image.to_pil_image()
                        resized_image = pil_image.resize(
                            (img_width, img_height), PILImage.Resampling.LANCZOS
                        )

                        # Calculate vertical centering in row
                        y_center_offset = (row_height - img_height) // 2

                        # Paste image
                        mosaic.paste(
                            resized_image, (x_offset, y_offset + y_center_offset)
                        )

                        # Add border only between images
                        if img_index < len(row) - 1:
                            x_offset += img_width + border_size
                        else:
                            x_offset += img_width

                    except Exception as e:
                        self._logger.error(
                            f"Error processing image in mosaic: {str(e)}"
                        )
                        raise

                # Add vertical border only between rows
                if row_index < len(rows) - 1:
                    y_offset += row_height + border_size
                else:
                    y_offset += row_height

            # Convert to bytes
            output = BytesIO()
            mosaic.save(output, format="PNG")
            return output.getvalue()

        except Exception as e:
            self._logger.error(f"Error creating mosaic: {str(e)}")
            raise


def load_images_from_directory(directory_path: str | Path) -> List[Image]:
    logger = logging.getLogger(__name__)
    directory = (
        Path(directory_path) if isinstance(directory_path, str) else directory_path
    )

    if not directory.is_dir():
        raise ValueError(f"'{directory}' is not a valid directory")

    SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".bmp", ".gif"}

    images = []

    # Iterate through all files in directory
    for file_path in directory.iterdir():
        if file_path.suffix.lower() in SUPPORTED_FORMATS:
            try:
                with PILImage.open(file_path) as pil_image:
                    # Convert to RGB if necessary (handles PNG with transparency)
                    if pil_image.mode in ("RGBA", "P"):
                        pil_image = pil_image.convert("RGB")

                    # Get image dimensions
                    width, height = pil_image.size

                    # Convert PIL Image to bytes
                    buffer = BytesIO()
                    pil_image.save(buffer, format="PNG")
                    image_bytes = buffer.getvalue()

                    # Create Image object
                    image = Image(file=image_bytes, width=width, height=height)
                    images.append(image)

            except Exception as e:
                logger.error(f"Error loading image {file_path}: {str(e)}")
                continue

    if not images:
        raise ValueError(f"No valid images found in directory '{directory}'")

    return images


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    images = load_images_from_directory("./tests/mosaic_test_images")

    mosaic_service = MosaicService()
    result = mosaic_service.create_mosaic(
        images=images,
        width=1200,
        border_size=10,
    )

    with open("mosaic.png", "wb") as f:
        f.write(result)
