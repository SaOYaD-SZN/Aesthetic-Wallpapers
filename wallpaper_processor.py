"""Wallpaper processing utilities for the Aesthetic Wallpapers collection.

Provides batch image processing, validation, optimisation, and format conversion
using Pillow.  All public functions accept :class:`pathlib.Path` objects and use
proper type annotations throughout.

Requirements:
    pip install Pillow

Usage:
    python wallpaper_processor.py --help
    python wallpaper_processor.py info aesthetic-wallpapers/
    python wallpaper_processor.py optimize aesthetic-wallpapers/ --output optimized/
    python wallpaper_processor.py convert aesthetic-wallpapers/ --format webp --output converted/

Example::

    from wallpaper_processor import WallpaperProcessor

    processor = WallpaperProcessor(source_dir="aesthetic-wallpapers")
    results = processor.process_all(output_dir="optimized", quality=85)
    print(processor.report(results))
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

try:
    from PIL import Image, UnidentifiedImageError
except ImportError as _pil_err:  # pragma: no cover
    raise ImportError(
        "Pillow is required for wallpaper processing. " "Install it with: pip install Pillow"
    ) from _pil_err

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SUPPORTED_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif"}
)

DEFAULT_QUALITY: Final[int] = 85
DEFAULT_MAX_SIZE: Final[tuple[int, int]] = (3840, 2160)  # 4K UHD

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class WallpaperError(Exception):
    """Base exception for wallpaper processing errors."""


class InvalidImageError(WallpaperError):
    """Raised when an image file cannot be opened or is corrupt."""


class UnsupportedFormatError(WallpaperError):
    """Raised when a requested output format is not supported."""


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ImageInfo:
    """Metadata about a single wallpaper image.

    Attributes:
        path: Absolute path to the image file.
        width: Image width in pixels.
        height: Image height in pixels.
        format: Pillow format string (e.g. ``'PNG'``, ``'JPEG'``).
        mode: Pillow colour mode (e.g. ``'RGB'``, ``'RGBA'``).
        file_size_bytes: Size of the file on disk in bytes.
    """

    path: Path
    width: int
    height: int
    format: str
    mode: str
    file_size_bytes: int

    @property
    def resolution(self) -> str:
        """Human-readable resolution string, e.g. ``'1920x1080'``."""
        return f"{self.width}x{self.height}"

    @property
    def aspect_ratio(self) -> float:
        """Aspect ratio as a float (width / height)."""
        return self.width / self.height if self.height else 0.0

    @property
    def megapixels(self) -> float:
        """Total pixel count in megapixels."""
        return (self.width * self.height) / 1_000_000


@dataclass
class ProcessingResult:
    """Result of a single image processing operation.

    Attributes:
        source: Path to the source image.
        output: Path to the output image, or *None* when the operation failed.
        success: Whether the operation completed without errors.
        error: Error message when *success* is ``False``.
        original_size_bytes: File size before processing.
        output_size_bytes: File size after processing, or 0 on failure.
    """

    source: Path
    output: Path | None
    success: bool
    error: str = ""
    original_size_bytes: int = 0
    output_size_bytes: int = 0

    @property
    def size_delta_bytes(self) -> int:
        """Byte reduction achieved (negative means the file grew)."""
        return self.original_size_bytes - self.output_size_bytes

    @property
    def compression_ratio(self) -> float:
        """Fraction of the original size retained (0–1)."""
        if not self.original_size_bytes:
            return 1.0
        return self.output_size_bytes / self.original_size_bytes


@dataclass
class BatchReport:
    """Aggregated report for a batch processing run.

    Attributes:
        results: Individual :class:`ProcessingResult` objects.
    """

    results: list[ProcessingResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        """Total number of images processed."""
        return len(self.results)

    @property
    def succeeded(self) -> int:
        """Number of images processed successfully."""
        return sum(1 for r in self.results if r.success)

    @property
    def failed(self) -> int:
        """Number of images that failed to process."""
        return self.total - self.succeeded

    @property
    def total_saved_bytes(self) -> int:
        """Total bytes saved across all successful operations."""
        return sum(r.size_delta_bytes for r in self.results if r.success)

    def __str__(self) -> str:
        lines = [
            "Batch processing report",
            f"  Total:     {self.total}",
            f"  Succeeded: {self.succeeded}",
            f"  Failed:    {self.failed}",
            f"  Saved:     {self.total_saved_bytes / 1024:.1f} KB",
        ]
        if self.failed:
            lines.append("\nFailed files:")
            for r in self.results:
                if not r.success:
                    lines.append(f"  {r.source}: {r.error}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Core processor
# ---------------------------------------------------------------------------


class WallpaperProcessor:
    """High-level interface for batch wallpaper processing.

    Args:
        source_dir: Directory containing source wallpaper images.

    Raises:
        FileNotFoundError: If *source_dir* does not exist.
        NotADirectoryError: If *source_dir* is not a directory.
    """

    def __init__(self, source_dir: str | Path) -> None:
        self.source_dir = Path(source_dir)
        if not self.source_dir.exists():
            raise FileNotFoundError(f"Source directory not found: {self.source_dir}")
        if not self.source_dir.is_dir():
            raise NotADirectoryError(f"Not a directory: {self.source_dir}")

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover(self) -> list[Path]:
        """Return all supported image files in *source_dir* (non-recursive).

        Returns:
            Sorted list of :class:`~pathlib.Path` objects for each image.
        """
        return sorted(
            p
            for p in self.source_dir.iterdir()
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
        )

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    def get_info(self, image_path: str | Path) -> ImageInfo:
        """Return metadata for a single image.

        Args:
            image_path: Path to the image file.

        Returns:
            An :class:`ImageInfo` populated with the image's metadata.

        Raises:
            InvalidImageError: If the file cannot be opened as an image.
        """
        path = Path(image_path)
        try:
            with Image.open(path) as img:
                img.load()
                return ImageInfo(
                    path=path.resolve(),
                    width=img.width,
                    height=img.height,
                    format=img.format or path.suffix.lstrip(".").upper(),
                    mode=img.mode,
                    file_size_bytes=path.stat().st_size,
                )
        except (UnidentifiedImageError, OSError) as exc:
            raise InvalidImageError(f"Cannot open image '{path}': {exc}") from exc

    def info_all(self) -> list[ImageInfo]:
        """Return :class:`ImageInfo` for every discovered image.

        Returns:
            List of :class:`ImageInfo` objects, one per image.
        """
        infos: list[ImageInfo] = []
        for path in self.discover():
            try:
                infos.append(self.get_info(path))
            except InvalidImageError as exc:
                logger.warning("Skipping '%s': %s", path.name, exc)
        return infos

    # ------------------------------------------------------------------
    # Single-image operations
    # ------------------------------------------------------------------

    def optimize(
        self,
        image_path: str | Path,
        output_path: str | Path,
        *,
        quality: int = DEFAULT_QUALITY,
        max_size: tuple[int, int] = DEFAULT_MAX_SIZE,
    ) -> ProcessingResult:
        """Optimise a single image and write it to *output_path*.

        The image is resized to fit within *max_size* while preserving its
        aspect ratio, then saved at the requested *quality*.

        Args:
            image_path: Source image path.
            output_path: Destination path (extension determines the format).
            quality: JPEG/WebP compression quality (1–95).
            max_size: ``(max_width, max_height)`` bounding box for resizing.

        Returns:
            A :class:`ProcessingResult` describing the outcome.
        """
        src = Path(image_path)
        dst = Path(output_path)
        original_size = src.stat().st_size

        try:
            with Image.open(src) as img:
                img.load()

                # Convert palette/RGBA to RGB for JPEG compatibility
                if img.mode in {"P", "RGBA"} and dst.suffix.lower() in {".jpg", ".jpeg"}:
                    img = img.convert("RGB")

                # Downscale if necessary
                if img.width > max_size[0] or img.height > max_size[1]:
                    img.thumbnail(max_size, Image.LANCZOS)
                    logger.debug("Resized '%s' to %dx%d", src.name, img.width, img.height)

                dst.parent.mkdir(parents=True, exist_ok=True)
                save_kwargs: dict[str, object] = {"optimize": True}
                if dst.suffix.lower() in {".jpg", ".jpeg", ".webp"}:
                    save_kwargs["quality"] = quality

                img.save(dst, **save_kwargs)

            output_size = dst.stat().st_size
            logger.info("✅ Optimized '%s' → '%s'", src.name, dst.name)
            return ProcessingResult(
                source=src,
                output=dst,
                success=True,
                original_size_bytes=original_size,
                output_size_bytes=output_size,
            )

        except (UnidentifiedImageError, OSError) as exc:
            logger.error("❌ Failed to optimize '%s': %s", src.name, exc)
            return ProcessingResult(
                source=src,
                output=None,
                success=False,
                error=str(exc),
                original_size_bytes=original_size,
            )

    def convert(
        self,
        image_path: str | Path,
        output_path: str | Path,
        *,
        quality: int = DEFAULT_QUALITY,
    ) -> ProcessingResult:
        """Convert an image to the format implied by *output_path*'s extension.

        Args:
            image_path: Source image path.
            output_path: Destination path (extension determines the format).
            quality: Compression quality for lossy formats.

        Returns:
            A :class:`ProcessingResult` describing the outcome.
        """
        src = Path(image_path)
        dst = Path(output_path)
        ext = dst.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise UnsupportedFormatError(
                f"Output format '{ext}' is not supported. "
                f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            )

        original_size = src.stat().st_size
        try:
            with Image.open(src) as img:
                img.load()

                if img.mode in {"P", "RGBA"} and ext in {".jpg", ".jpeg"}:
                    img = img.convert("RGB")

                dst.parent.mkdir(parents=True, exist_ok=True)
                save_kwargs: dict[str, object] = {}
                if ext in {".jpg", ".jpeg", ".webp"}:
                    save_kwargs["quality"] = quality

                img.save(dst, **save_kwargs)

            output_size = dst.stat().st_size
            logger.info("✅ Converted '%s' → '%s'", src.name, dst.name)
            return ProcessingResult(
                source=src,
                output=dst,
                success=True,
                original_size_bytes=original_size,
                output_size_bytes=output_size,
            )
        except (UnidentifiedImageError, OSError) as exc:
            logger.error("❌ Failed to convert '%s': %s", src.name, exc)
            return ProcessingResult(
                source=src,
                output=None,
                success=False,
                error=str(exc),
                original_size_bytes=original_size,
            )

    # ------------------------------------------------------------------
    # Batch operations
    # ------------------------------------------------------------------

    def process_all(
        self,
        output_dir: str | Path,
        *,
        quality: int = DEFAULT_QUALITY,
        max_size: tuple[int, int] = DEFAULT_MAX_SIZE,
        output_format: str | None = None,
    ) -> BatchReport:
        """Optimise all discovered images and write them to *output_dir*.

        Args:
            output_dir: Destination directory (created if absent).
            quality: JPEG/WebP compression quality (1–95).
            max_size: ``(max_width, max_height)`` bounding box.
            output_format: If provided (e.g. ``'webp'``), convert all images to
                this format.  Otherwise each image keeps its original extension.

        Returns:
            A :class:`BatchReport` summarising the run.
        """
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        images = self.discover()
        if not images:
            logger.warning("No supported images found in '%s'", self.source_dir)
            return BatchReport()

        report = BatchReport()
        logger.info("Processing %d image(s)…", len(images))

        for src in images:
            if output_format:
                ext = f".{output_format.lstrip('.')}"
            else:
                ext = src.suffix
            dst = out / (src.stem + ext)
            result = self.optimize(src, dst, quality=quality, max_size=max_size)
            report.results.append(result)

        logger.info("%s", report)
        return report

    def convert_all(
        self,
        output_dir: str | Path,
        *,
        output_format: str = "webp",
        quality: int = DEFAULT_QUALITY,
    ) -> BatchReport:
        """Convert all discovered images to *output_format*.

        Args:
            output_dir: Destination directory (created if absent).
            output_format: Target format extension (e.g. ``'webp'``).
            quality: Compression quality for lossy formats.

        Returns:
            A :class:`BatchReport` summarising the run.
        """
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        images = self.discover()
        report = BatchReport()

        for src in images:
            ext = f".{output_format.lstrip('.')}"
            dst = out / (src.stem + ext)
            result = self.convert(src, dst, quality=quality)
            report.results.append(result)

        return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wallpaper_processor",
        description="Wallpaper image processing utilities",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # -- info -----------------------------------------------------------------
    info_p = sub.add_parser("info", help="Display metadata for all images in a directory")
    info_p.add_argument("source", help="Directory containing wallpaper images")

    # -- optimize -------------------------------------------------------------
    opt_p = sub.add_parser("optimize", help="Optimise images (resize + compress)")
    opt_p.add_argument("source", help="Directory containing source images")
    opt_p.add_argument("--output", required=True, help="Output directory")
    opt_p.add_argument(
        "--quality", type=int, default=DEFAULT_QUALITY, help="JPEG/WebP quality (1-95)"
    )
    opt_p.add_argument(
        "--max-width", type=int, default=DEFAULT_MAX_SIZE[0], help="Maximum output width"
    )
    opt_p.add_argument(
        "--max-height", type=int, default=DEFAULT_MAX_SIZE[1], help="Maximum output height"
    )

    # -- convert --------------------------------------------------------------
    conv_p = sub.add_parser("convert", help="Batch-convert images to another format")
    conv_p.add_argument("source", help="Directory containing source images")
    conv_p.add_argument("--output", required=True, help="Output directory")
    conv_p.add_argument(
        "--format",
        dest="fmt",
        default="webp",
        help="Target format (e.g. webp, jpg, png)",
    )
    conv_p.add_argument(
        "--quality", type=int, default=DEFAULT_QUALITY, help="JPEG/WebP quality (1-95)"
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    """Entry point for the :command:`wallpaper_processor` CLI.

    Args:
        argv: Argument list (defaults to :data:`sys.argv` when *None*).
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    processor = WallpaperProcessor(args.source)

    match args.command:
        case "info":
            infos = processor.info_all()
            if not infos:
                print("No supported images found.")
                return
            print(f"{'File':<50} {'Resolution':<12} {'Format':<8} {'MP':>6} {'Size':>10}")
            print("-" * 90)
            for info in infos:
                size_kb = info.file_size_bytes / 1024
                print(
                    f"{info.path.name:<50} {info.resolution:<12} {info.format:<8} "
                    f"{info.megapixels:>5.1f}  {size_kb:>8.1f} KB"
                )

        case "optimize":
            report = processor.process_all(
                args.output,
                quality=args.quality,
                max_size=(args.max_width, args.max_height),
            )
            print(report)
            sys.exit(0 if report.failed == 0 else 1)

        case "convert":
            report = processor.convert_all(
                args.output,
                output_format=args.fmt,
                quality=args.quality,
            )
            print(report)
            sys.exit(0 if report.failed == 0 else 1)


if __name__ == "__main__":
    main()
