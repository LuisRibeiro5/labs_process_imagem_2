import os
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

RAIZ = Path(__file__).resolve().parents[1]


def run_cli(
    caminho_entrada: Path,
    caminho_saida: Path,
    metodo: str,
    limiar: int | None = None,
    tamanho_bloco: int | None = None,
    constante: int | None = None,
    hsv_inferior: str | None = None,
    hsv_superior: str | None = None,
    inverter: bool = False,
) -> subprocess.CompletedProcess[str]:
    comando = [
        sys.executable,
        "-m",
        "pdi_lab",
        "--input",
        str(caminho_entrada),
        "--output",
        str(caminho_saida),
        "--operation",
        "segment",
        "--method",
        metodo,
    ]

    if limiar is not None:
        comando.extend(["--threshold", str(limiar)])
    if tamanho_bloco is not None:
        comando.extend(["--block-size", str(tamanho_bloco)])
    if constante is not None:
        comando.extend(["--constant", str(constante)])
    if hsv_inferior is not None:
        comando.extend(["--hsv-lower", hsv_inferior])
    if hsv_superior is not None:
        comando.extend(["--hsv-upper", hsv_superior])
    if inverter:
        comando.append("--invert")

    return subprocess.run(
        comando,
        cwd=RAIZ,
        env={**os.environ, "PYTHONPATH": str(RAIZ / "src")},
        capture_output=True,
        text=True,
        check=False,
    )


def create_threshold_image(caminho: Path) -> Path:
    imagem = np.array(
        [
            [50, 119, 120, 121, 255],
            [119, 120, 120, 121, 200],
            [0, 100, 110, 120, 180],
            [80, 115, 120, 125, 150],
        ],
        dtype=np.uint8,
    )
    cv2.imwrite(str(caminho), imagem)
    return caminho


def create_scene_images() -> tuple[Path, Path]:
    altura_favoravel, largura_favoravel = 160, 220
    linhas_favoravel, colunas_favoravel = np.indices((altura_favoravel, largura_favoravel))
    centro_favoravel = (100, 80)
    distancia_favoravel = np.sqrt(
        (colunas_favoravel - centro_favoravel[0]) ** 2 + (linhas_favoravel - centro_favoravel[1]) ** 2
    )
    objeto_favoravel = np.clip(160 - distancia_favoravel * 1.8, 0, 255).astype(np.uint8)
    imagem_favoravel = np.full((altura_favoravel, largura_favoravel), 35, dtype=np.uint8)
    imagem_favoravel[distancia_favoravel <= 50] = objeto_favoravel[distancia_favoravel <= 50]
    imagem_favoravel[20:90, 20:90] = 70
    imagem_favoravel[:, 180:210] = 50
    imagem_favoravel = cv2.cvtColor(imagem_favoravel, cv2.COLOR_GRAY2BGR)

    altura_dificil, largura_dificil = 180, 260
    linhas_dificeis, colunas_dificeis = np.indices((altura_dificil, largura_dificil))
    imagem_dificil = np.full((altura_dificil, largura_dificil), 70, dtype=np.uint8)
    for centro, raio, base in [((90, 90), 60, 150), ((170, 110), 40, 130), ((135, 150), 35, 120)]:
        distancia = np.sqrt((colunas_dificeis - centro[0]) ** 2 + (linhas_dificeis - centro[1]) ** 2)
        objeto = np.clip(base - distancia * 2.0, 0, 255).astype(np.uint8)
        imagem_dificil[distancia <= raio] = objeto[distancia <= raio]

    ruido = np.random.default_rng(7).integers(-20, 21, size=(altura_dificil, largura_dificil), dtype=np.int16)
    imagem_dificil = np.clip(imagem_dificil.astype(np.int16) + ruido, 0, 255).astype(np.uint8)
    imagem_dificil = cv2.cvtColor(imagem_dificil, cv2.COLOR_GRAY2BGR)

    caminho_favoravel = RAIZ / "images" / "input" / "cena_favoravel.png"
    caminho_dificil = RAIZ / "images" / "input" / "cena_dificil.png"
    caminho_favoravel.parent.mkdir(parents=True, exist_ok=True)

    cv2.imwrite(str(caminho_favoravel), imagem_favoravel)
    cv2.imwrite(str(caminho_dificil), imagem_dificil)
    return caminho_favoravel, caminho_dificil


def test_fixed_threshold_is_predictable_and_binary():
    caminho_entrada = RAIZ / "images" / "input" / "synthetic_threshold.png"
    caminho_saida = RAIZ / "images" / "output" / "pytest_threshold_fixed.png"
    create_threshold_image(caminho_entrada)

    resultado = run_cli(caminho_entrada, caminho_saida, "fixed", limiar=120)
    assert resultado.returncode == 0, resultado.stderr

    mascara = cv2.imread(str(caminho_saida), cv2.IMREAD_UNCHANGED)
    assert mascara is not None
    assert mascara.shape == (4, 5)
    assert mascara.ndim == 2
    assert set(np.unique(mascara).tolist()).issubset({0, 255})
    assert mascara[0, 0] == 0
    assert mascara[0, 1] == 0
    assert mascara[0, 2] == 255
    assert mascara[0, 3] == 255
    assert mascara[2, 2] == 0
    assert mascara[2, 3] == 255


def test_real_images_are_processed_with_two_configurations():
    caminho_favoravel, caminho_dificil = create_scene_images()

    favoravel_fixo = RAIZ / "images" / "output" / "favorable_fixed.png"
    favoravel_otsu = RAIZ / "images" / "output" / "favorable_otsu.png"
    dificil_fixo = RAIZ / "images" / "output" / "difficult_fixed.png"
    dificil_otsu = RAIZ / "images" / "output" / "difficult_otsu.png"

    for caminho_entrada, caminho_saida, metodo, limiar in [
        (caminho_favoravel, favoravel_fixo, "fixed", 120),
        (caminho_favoravel, favoravel_otsu, "otsu", None),
        (caminho_dificil, dificil_fixo, "fixed", 110),
        (caminho_dificil, dificil_otsu, "otsu", None),
    ]:
        resultado = run_cli(caminho_entrada, caminho_saida, metodo, limiar=limiar)
        assert resultado.returncode == 0, resultado.stderr
        mascara = cv2.imread(str(caminho_saida), cv2.IMREAD_UNCHANGED)
        assert mascara is not None
        assert mascara.shape == cv2.imread(str(caminho_entrada), cv2.IMREAD_UNCHANGED).shape[:2]
        assert set(np.unique(mascara).tolist()).issubset({0, 255})

    proporcao_fixa = cv2.imread(str(favoravel_fixo), cv2.IMREAD_UNCHANGED).mean() / 255.0
    proporcao_otsu = cv2.imread(str(favoravel_otsu), cv2.IMREAD_UNCHANGED).mean() / 255.0
    assert abs(proporcao_fixa - proporcao_otsu) > 0.01


def test_hsv_and_adaptive_methods_work_and_binary_masks_are_valid():
    caminho_entrada = RAIZ / "images" / "input" / "synthetic_hsv.png"
    imagem = np.zeros((80, 80, 3), dtype=np.uint8)
    cv2.circle(imagem, (40, 40), 18, (30, 180, 160), thickness=-1)
    cv2.imwrite(str(caminho_entrada), imagem)

    saida_adaptativa = RAIZ / "images" / "output" / "pytest_adaptive.png"
    saida_hsv = RAIZ / "images" / "output" / "pytest_hsv.png"

    resultado_adaptativo = run_cli(caminho_entrada, saida_adaptativa, "adaptive", tamanho_bloco=15, constante=7)
    resultado_hsv = run_cli(caminho_entrada, saida_hsv, "hsv", hsv_inferior="5,40,40", hsv_superior="70,255,255")

    assert resultado_adaptativo.returncode == 0, resultado_adaptativo.stderr
    assert resultado_hsv.returncode == 0, resultado_hsv.stderr

    for caminho_saida in (saida_adaptativa, saida_hsv):
        mascara = cv2.imread(str(caminho_saida), cv2.IMREAD_UNCHANGED)
        assert mascara is not None
        assert mascara.ndim == 2
        assert mascara.shape[:2] == (80, 80)
        assert set(np.unique(mascara).tolist()).issubset({0, 255})


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
        hsv_inferior="170,100,100",
        hsv_superior="10,255,255",
    )
    assert resultado.returncode == 0, resultado.stderr
    mascara = cv2.imread(str(caminho_saida), cv2.IMREAD_UNCHANGED)
    assert mascara is not None
    assert mascara.tolist() == [[255, 255, 0]]

    fora_do_intervalo = run_cli(
        caminho_entrada,
        tmp_path / "invalida.png",
        "hsv",
        hsv_inferior="180,0,0",
        hsv_superior="179,255,255",
    )
    assert fora_do_intervalo.returncode != 0


def test_mask_rejects_lossy_jpeg_output(tmp_path: Path):
    caminho_entrada = RAIZ / "images" / "input" / "synthetic_threshold.png"
    create_threshold_image(caminho_entrada)

    resultado = run_cli(caminho_entrada, tmp_path / "mascara.jpg", "fixed", limiar=120)

    assert resultado.returncode != 0


def test_failure_modes_are_reported_with_nonzero_exit_codes():
    caminho_inexistente = RAIZ / "images" / "input" / "arquivo_inexistente.png"
    caminho_valido = RAIZ / "images" / "input" / "synthetic_threshold.png"
    create_threshold_image(caminho_valido)

    resultado_inexistente = run_cli(caminho_inexistente, RAIZ / "images" / "output" / "missing.png", "fixed", limiar=128)
    assert resultado_inexistente.returncode != 0

    resultado_desconhecido = run_cli(caminho_valido, RAIZ / "images" / "output" / "unknown.png", "unknown")
    assert resultado_desconhecido.returncode != 0

    resultado_invalido = run_cli(caminho_valido, RAIZ / "images" / "output" / "invalid.png", "fixed", limiar=300)
    assert resultado_invalido.returncode != 0

    resultado_ok = run_cli(caminho_valido, RAIZ / "images" / "output" / "valid.png", "fixed", limiar=120)
    assert resultado_ok.returncode == 0
