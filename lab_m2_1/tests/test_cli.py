import os
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def run_cli(
    input_path: Path,
    output_path: Path,
    method: str,
    threshold: int | None = None,
    block_size: int | None = None,
    constant: int | None = None,
    hsv_lower: str | None = None,
    hsv_upper: str | None = None,
    invert: bool = False,
) -> subprocess.CompletedProcess[str]:
    cmd = [
        sys.executable,
        "-m",
        "pdi_lab",
        "--input",
        str(input_path),
        "--output",
        str(output_path),
        "--operation",
        "segment",
        "--method",
        method,
    ]

    if threshold is not None:
        cmd.extend(["--threshold", str(threshold)])
    if block_size is not None:
        cmd.extend(["--block-size", str(block_size)])
    if constant is not None:
        cmd.extend(["--constant", str(constant)])
    if hsv_lower is not None:
        cmd.extend(["--hsv-lower", hsv_lower])
    if hsv_upper is not None:
        cmd.extend(["--hsv-upper", hsv_upper])
    if invert:
        cmd.append("--invert")

    return subprocess.run(
        cmd,
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        text=True,
        check=False,
    )


def create_threshold_image(path: Path) -> Path:
    image = np.array(
        [
            [50, 119, 120, 121, 255],
            [119, 120, 120, 121, 200],
            [0, 100, 110, 120, 180],
            [80, 115, 120, 125, 150],
        ],
        dtype=np.uint8,
    )
    cv2.imwrite(str(path), image)
    return path


def create_scene_images() -> tuple[Path, Path]:
    favorable_h, favorable_w = 160, 220
    favorable_y, favorable_x = np.indices((favorable_h, favorable_w))
    favorable_center = (100, 80)
    favorable_distance = np.sqrt((favorable_x - favorable_center[0]) ** 2 + (favorable_y - favorable_center[1]) ** 2)
    favorable_object = np.clip(160 - favorable_distance * 1.8, 0, 255).astype(np.uint8)
    favorable = np.full((favorable_h, favorable_w), 35, dtype=np.uint8)
    favorable[favorable_distance <= 50] = favorable_object[favorable_distance <= 50]
    favorable[20:90, 20:90] = 70
    favorable[:, 180:210] = 50
    favorable = cv2.cvtColor(favorable, cv2.COLOR_GRAY2BGR)

    difficult_h, difficult_w = 180, 260
    difficult_y, difficult_x = np.indices((difficult_h, difficult_w))
    difficult = np.full((difficult_h, difficult_w), 70, dtype=np.uint8)
    for center, radius, base in [((90, 90), 60, 150), ((170, 110), 40, 130), ((135, 150), 35, 120)]:
        difficulty_distance = np.sqrt((difficult_x - center[0]) ** 2 + (difficult_y - center[1]) ** 2)
        difficulty_object = np.clip(base - difficulty_distance * 2.0, 0, 255).astype(np.uint8)
        difficult[difficulty_distance <= radius] = difficulty_object[difficulty_distance <= radius]

    noise = np.random.default_rng(7).integers(-20, 21, size=(difficult_h, difficult_w), dtype=np.int16)
    difficult = np.clip(difficult.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    difficult = cv2.cvtColor(difficult, cv2.COLOR_GRAY2BGR)

    favorable_path = ROOT / "images" / "input" / "cena_favoravel.png"
    difficult_path = ROOT / "images" / "input" / "cena_dificil.png"
    favorable_path.parent.mkdir(parents=True, exist_ok=True)

    cv2.imwrite(str(favorable_path), favorable)
    cv2.imwrite(str(difficult_path), difficult)
    return favorable_path, difficult_path


def test_fixed_threshold_is_predictable_and_binary():
    input_path = ROOT / "images" / "input" / "synthetic_threshold.png"
    output_path = ROOT / "images" / "output" / "pytest_threshold_fixed.png"
    create_threshold_image(input_path)

    proc = run_cli(input_path, output_path, "fixed", threshold=120)
    assert proc.returncode == 0, proc.stderr

    mask = cv2.imread(str(output_path), cv2.IMREAD_UNCHANGED)
    assert mask is not None
    assert mask.shape == (4, 5)
    assert mask.ndim == 2
    assert set(np.unique(mask).tolist()).issubset({0, 255})
    assert mask[0, 0] == 0
    assert mask[0, 1] == 0
    assert mask[0, 2] == 255
    assert mask[0, 3] == 255
    assert mask[2, 2] == 0
    assert mask[2, 3] == 255


def test_real_images_are_processed_with_two_configurations():
    favorable_path, difficult_path = create_scene_images()

    favorable_fixed = ROOT / "images" / "output" / "favorable_fixed.png"
    favorable_otsu = ROOT / "images" / "output" / "favorable_otsu.png"
    difficult_fixed = ROOT / "images" / "output" / "difficult_fixed.png"
    difficult_otsu = ROOT / "images" / "output" / "difficult_otsu.png"

    for input_path, output_path, method, threshold in [
        (favorable_path, favorable_fixed, "fixed", 120),
        (favorable_path, favorable_otsu, "otsu", None),
        (difficult_path, difficult_fixed, "fixed", 110),
        (difficult_path, difficult_otsu, "otsu", None),
    ]:
        proc = run_cli(input_path, output_path, method, threshold=threshold)
        assert proc.returncode == 0, proc.stderr
        mask = cv2.imread(str(output_path), cv2.IMREAD_UNCHANGED)
        assert mask is not None
        assert mask.shape == cv2.imread(str(input_path), cv2.IMREAD_UNCHANGED).shape[:2]
        assert set(np.unique(mask).tolist()).issubset({0, 255})

    fixed_ratio = cv2.imread(str(favorable_fixed), cv2.IMREAD_UNCHANGED).mean() / 255.0
    otsu_ratio = cv2.imread(str(favorable_otsu), cv2.IMREAD_UNCHANGED).mean() / 255.0
    assert abs(fixed_ratio - otsu_ratio) > 0.01


def test_hsv_and_adaptive_methods_work_and_binary_masks_are_valid():
    input_path = ROOT / "images" / "input" / "synthetic_hsv.png"
    image = np.zeros((80, 80, 3), dtype=np.uint8)
    cv2.circle(image, (40, 40), 18, (30, 180, 160), thickness=-1)
    cv2.imwrite(str(input_path), image)

    adaptive_output = ROOT / "images" / "output" / "pytest_adaptive.png"
    hsv_output = ROOT / "images" / "output" / "pytest_hsv.png"

    proc_adaptive = run_cli(input_path, adaptive_output, "adaptive", block_size=15, constant=7)
    proc_hsv = run_cli(input_path, hsv_output, "hsv", hsv_lower="5,40,40", hsv_upper="70,255,255")

    assert proc_adaptive.returncode == 0, proc_adaptive.stderr
    assert proc_hsv.returncode == 0, proc_hsv.stderr

    for output_path in (adaptive_output, hsv_output):
        mask = cv2.imread(str(output_path), cv2.IMREAD_UNCHANGED)
        assert mask is not None
        assert mask.ndim == 2
        assert mask.shape[:2] == (80, 80)
        assert set(np.unique(mask).tolist()).issubset({0, 255})


def test_hsv_wraps_hue_range_and_rejects_invalid_ranges(tmp_path: Path):
    imagem_hsv = np.array([[[178, 220, 220], [2, 220, 220], [90, 220, 220]]], dtype=np.uint8)
    imagem_bgr = cv2.cvtColor(imagem_hsv, cv2.COLOR_HSV2BGR)
    caminho_entrada = tmp_path / "matiz.png"
    caminho_saida = tmp_path / "mascara.png"
    cv2.imwrite(str(caminho_entrada), imagem_bgr)

    resultado = run_cli(
        caminho_entrada,
        caminho_saida,
        "hsv",
        hsv_lower="170,100,100",
        hsv_upper="10,255,255",
    )
    assert resultado.returncode == 0, resultado.stderr
    mascara = cv2.imread(str(caminho_saida), cv2.IMREAD_UNCHANGED)
    assert mascara is not None
    assert mascara.tolist() == [[255, 255, 0]]

    fora_do_intervalo = run_cli(
        caminho_entrada,
        tmp_path / "invalida.png",
        "hsv",
        hsv_lower="180,0,0",
        hsv_upper="179,255,255",
    )
    assert fora_do_intervalo.returncode != 0


def test_mask_rejects_lossy_jpeg_output(tmp_path: Path):
    caminho_entrada = ROOT / "images" / "input" / "synthetic_threshold.png"
    create_threshold_image(caminho_entrada)

    resultado = run_cli(caminho_entrada, tmp_path / "mascara.jpg", "fixed", threshold=120)

    assert resultado.returncode != 0


def test_failure_modes_are_reported_with_nonzero_exit_codes():
    missing_input = ROOT / "images" / "input" / "arquivo_inexistente.png"
    good_input = ROOT / "images" / "input" / "synthetic_threshold.png"
    create_threshold_image(good_input)

    missing_proc = run_cli(missing_input, ROOT / "images" / "output" / "missing.png", "fixed", threshold=128)
    assert missing_proc.returncode != 0

    unknown_proc = run_cli(good_input, ROOT / "images" / "output" / "unknown.png", "unknown")
    assert unknown_proc.returncode != 0

    invalid_proc = run_cli(good_input, ROOT / "images" / "output" / "invalid.png", "fixed", threshold=300)
    assert invalid_proc.returncode != 0

    success_proc = run_cli(good_input, ROOT / "images" / "output" / "valid.png", "fixed", threshold=120)
    assert success_proc.returncode == 0
