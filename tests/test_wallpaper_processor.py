"""Tests for wallpaper_processor.py."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from wallpaper_processor import (
    BatchReport,
    InvalidImageError,
    ProcessingResult,
    UnsupportedFormatError,
    WallpaperProcessor,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_png(tmp_path: Path, name: str = "test.png", size: tuple[int, int] = (100, 60)) -> Path:
    """Create a minimal PNG image for testing."""
    img_path = tmp_path / name
    img = Image.new("RGB", size, color=(128, 64, 255))
    img.save(img_path, format="PNG")
    return img_path


def _make_jpeg(tmp_path: Path, name: str = "test.jpg", size: tuple[int, int] = (100, 60)) -> Path:
    img_path = tmp_path / name
    img = Image.new("RGB", size, color=(200, 100, 50))
    img.save(img_path, format="JPEG")
    return img_path


# ---------------------------------------------------------------------------
# WallpaperProcessor construction
# ---------------------------------------------------------------------------


def test_processor_nonexistent_dir_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        WallpaperProcessor(tmp_path / "nonexistent")


def test_processor_file_path_raises(tmp_path: Path) -> None:
    f = tmp_path / "file.txt"
    f.write_text("hello")
    with pytest.raises(NotADirectoryError):
        WallpaperProcessor(f)


def test_processor_accepts_path_object(tmp_path: Path) -> None:
    proc = WallpaperProcessor(tmp_path)
    assert proc.source_dir == tmp_path


def test_processor_accepts_string(tmp_path: Path) -> None:
    proc = WallpaperProcessor(str(tmp_path))
    assert proc.source_dir == tmp_path


# ---------------------------------------------------------------------------
# WallpaperProcessor.discover
# ---------------------------------------------------------------------------


def test_discover_finds_images(tmp_path: Path) -> None:
    _make_png(tmp_path, "a.png")
    _make_jpeg(tmp_path, "b.jpg")
    (tmp_path / "not_an_image.txt").write_text("text")
    proc = WallpaperProcessor(tmp_path)
    found = proc.discover()
    assert {p.name for p in found} == {"a.png", "b.jpg"}


def test_discover_empty_dir(tmp_path: Path) -> None:
    proc = WallpaperProcessor(tmp_path)
    assert proc.discover() == []


def test_discover_returns_sorted(tmp_path: Path) -> None:
    _make_png(tmp_path, "z.png")
    _make_png(tmp_path, "a.png")
    proc = WallpaperProcessor(tmp_path)
    names = [p.name for p in proc.discover()]
    assert names == sorted(names)


# ---------------------------------------------------------------------------
# WallpaperProcessor.get_info
# ---------------------------------------------------------------------------


def test_get_info_png(tmp_path: Path) -> None:
    path = _make_png(tmp_path, size=(200, 100))
    proc = WallpaperProcessor(tmp_path)
    info = proc.get_info(path)
    assert info.width == 200
    assert info.height == 100
    assert info.format == "PNG"
    assert info.mode == "RGB"
    assert info.file_size_bytes > 0


def test_get_info_invalid_file_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not an image")
    proc = WallpaperProcessor(tmp_path)
    with pytest.raises(InvalidImageError):
        proc.get_info(bad)


def test_image_info_resolution_property(tmp_path: Path) -> None:
    path = _make_png(tmp_path, size=(1920, 1080))
    proc = WallpaperProcessor(tmp_path)
    info = proc.get_info(path)
    assert info.resolution == "1920x1080"


def test_image_info_megapixels(tmp_path: Path) -> None:
    path = _make_png(tmp_path, size=(1000, 1000))
    proc = WallpaperProcessor(tmp_path)
    info = proc.get_info(path)
    assert abs(info.megapixels - 1.0) < 0.01


def test_image_info_aspect_ratio(tmp_path: Path) -> None:
    path = _make_png(tmp_path, size=(160, 90))
    proc = WallpaperProcessor(tmp_path)
    info = proc.get_info(path)
    assert abs(info.aspect_ratio - 16 / 9) < 0.01


# ---------------------------------------------------------------------------
# WallpaperProcessor.optimize
# ---------------------------------------------------------------------------


def test_optimize_creates_output(tmp_path: Path) -> None:
    src = _make_png(tmp_path, "src.png", size=(100, 60))
    out = tmp_path / "out" / "src.png"
    proc = WallpaperProcessor(tmp_path)
    result = proc.optimize(src, out)
    assert result.success is True
    assert out.exists()


def test_optimize_resizes_large_image(tmp_path: Path) -> None:
    src = _make_png(tmp_path, "big.png", size=(500, 300))
    out = tmp_path / "small.png"
    proc = WallpaperProcessor(tmp_path)
    result = proc.optimize(src, out, max_size=(100, 100))
    assert result.success is True
    with Image.open(out) as img:
        assert img.width <= 100
        assert img.height <= 100


def test_optimize_invalid_source_returns_failure(tmp_path: Path) -> None:
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"garbage")
    out = tmp_path / "out.png"
    proc = WallpaperProcessor(tmp_path)
    result = proc.optimize(bad, out)
    assert result.success is False
    assert result.error != ""


def test_optimize_creates_parent_dirs(tmp_path: Path) -> None:
    src = _make_png(tmp_path)
    out = tmp_path / "a" / "b" / "c" / "output.png"
    proc = WallpaperProcessor(tmp_path)
    result = proc.optimize(src, out)
    assert result.success is True
    assert out.exists()


# ---------------------------------------------------------------------------
# WallpaperProcessor.convert
# ---------------------------------------------------------------------------


def test_convert_png_to_jpeg(tmp_path: Path) -> None:
    src = _make_png(tmp_path, size=(80, 60))
    dst = tmp_path / "out.jpg"
    proc = WallpaperProcessor(tmp_path)
    result = proc.convert(src, dst)
    assert result.success is True
    assert dst.exists()
    with Image.open(dst) as img:
        assert img.format == "JPEG"


def test_convert_unsupported_format_raises(tmp_path: Path) -> None:
    src = _make_png(tmp_path)
    dst = tmp_path / "out.xyz"
    proc = WallpaperProcessor(tmp_path)
    with pytest.raises(UnsupportedFormatError):
        proc.convert(src, dst)


# ---------------------------------------------------------------------------
# WallpaperProcessor.process_all
# ---------------------------------------------------------------------------


def test_process_all_produces_report(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    _make_png(src_dir, "a.png")
    _make_png(src_dir, "b.png")
    out_dir = tmp_path / "out"
    proc = WallpaperProcessor(src_dir)
    report = proc.process_all(out_dir)
    assert report.total == 2
    assert report.succeeded == 2
    assert report.failed == 0


def test_process_all_with_format_conversion(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    _make_png(src_dir, "img.png")
    out_dir = tmp_path / "out"
    proc = WallpaperProcessor(src_dir)
    report = proc.process_all(out_dir, output_format="jpeg")
    assert report.succeeded == 1
    assert (out_dir / "img.jpeg").exists()


def test_process_all_empty_dir_returns_empty_report(tmp_path: Path) -> None:
    proc = WallpaperProcessor(tmp_path)
    report = proc.process_all(tmp_path / "out")
    assert report.total == 0


# ---------------------------------------------------------------------------
# WallpaperProcessor.convert_all
# ---------------------------------------------------------------------------


def test_convert_all_to_webp(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    _make_png(src_dir, "wall.png")
    _make_jpeg(src_dir, "wall2.jpg")
    out_dir = tmp_path / "out"
    proc = WallpaperProcessor(src_dir)
    report = proc.convert_all(out_dir, output_format="webp")
    assert report.succeeded == 2
    assert (out_dir / "wall.webp").exists()
    assert (out_dir / "wall2.webp").exists()


# ---------------------------------------------------------------------------
# BatchReport helpers
# ---------------------------------------------------------------------------


def test_batch_report_str_contains_summary() -> None:
    report = BatchReport(
        results=[
            ProcessingResult(
                source=Path("a.png"),
                output=Path("a.png"),
                success=True,
                original_size_bytes=1000,
                output_size_bytes=800,
            ),
            ProcessingResult(
                source=Path("b.png"),
                output=None,
                success=False,
                error="oops",
                original_size_bytes=500,
            ),
        ]
    )
    text = str(report)
    assert "Total:     2" in text
    assert "Succeeded: 1" in text
    assert "Failed:    1" in text
    assert "oops" in text


def test_processing_result_compression_ratio() -> None:
    r = ProcessingResult(
        source=Path("x"),
        output=Path("y"),
        success=True,
        original_size_bytes=1000,
        output_size_bytes=500,
    )
    assert r.compression_ratio == 0.5
    assert r.size_delta_bytes == 500


def test_processing_result_zero_original_size() -> None:
    r = ProcessingResult(
        source=Path("x"), output=Path("y"), success=True, original_size_bytes=0, output_size_bytes=0
    )
    assert r.compression_ratio == 1.0
