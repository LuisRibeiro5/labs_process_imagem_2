import csv
import json
import os
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

from pdi_lab.analyze import analyze_mask, label_components


RAIZ = Path(__file__).resolve().parents[1]


def run_cli(*argumentos: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pdi_lab", *argumentos],
        cwd=RAIZ,
        env={**os.environ, "PYTHONPATH": str(RAIZ / "src")},
        capture_output=True,
        text=True,
        check=False,
    )


def test_diagonal_pixels_depend_on_connectivity():
    mascara = np.array([[255, 0], [0, 255]], dtype=np.uint8)

    _, componentes_4 = label_components(mascara, 4)
    _, componentes_8 = label_components(mascara, 8)

    assert len(componentes_4) == 2
    assert len(componentes_8) == 1
    assert componentes_8[0]["area"] == 2


def test_opening_removes_isolated_noise_and_closing_fills_small_hole(tmp_path: Path):
    mascara = np.zeros((21, 21), dtype=np.uint8)
    mascara[5:16, 5:16] = 255
    mascara[10, 10] = 0
    mascara[2, 2] = 255
    caminho_entrada = tmp_path / "mask.png"
    cv2.imwrite(str(caminho_entrada), mascara)

    resumo = analyze_mask(
        caminho_entrada,
        tmp_path / "result",
        forma_kernel="rect",
        tamanho_kernel=3,
        iteracoes_abertura=1,
        iteracoes_fechamento=1,
    )

    mascara_inicial = cv2.imread(resumo["files"]["initial"], cv2.IMREAD_UNCHANGED)
    mascara_aberta = cv2.imread(resumo["files"]["opened"], cv2.IMREAD_UNCHANGED)
    mascara_final = cv2.imread(resumo["files"]["final"], cv2.IMREAD_UNCHANGED)
    assert mascara_inicial[2, 2] == 255
    assert mascara_aberta[2, 2] == 0
    assert mascara_aberta[10, 10] == 0
    assert mascara_final[10, 10] == 255
    assert resumo["initial"]["count_raw"] == 2
    assert resumo["final"]["count_raw"] == 1


def test_empty_mask_border_component_and_area_conservation(tmp_path: Path):
    mascara_vazia = np.zeros((8, 9), dtype=np.uint8)
    caminho_vazio = tmp_path / "empty.png"
    cv2.imwrite(str(caminho_vazio), mascara_vazia)
    resumo_vazio = analyze_mask(caminho_vazio, tmp_path / "empty_result")
    assert resumo_vazio["initial"]["count_raw"] == 0
    assert resumo_vazio["final"]["count_raw"] == 0

    mascara_borda = np.zeros((8, 9), dtype=np.uint8)
    mascara_borda[0:3, 0:4] = 255
    mascara_borda[5, 7] = 255
    caminho_borda = tmp_path / "border.png"
    cv2.imwrite(str(caminho_borda), mascara_borda)
    resumo_borda = analyze_mask(
        caminho_borda,
        tmp_path / "border_result",
        tamanho_kernel=1,
        iteracoes_abertura=1,
        iteracoes_fechamento=1,
    )
    with Path(resumo_borda["files"]["initial_csv"]).open(encoding="utf-8", newline="") as arquivo_csv:
        linhas = list(csv.DictReader(arquivo_csv))
    assert len(linhas) == 2
    assert linhas[0]["x"] == "0"
    assert linhas[0]["y"] == "0"
    assert sum(int(linha["area"]) for linha in linhas) == int(np.count_nonzero(mascara_borda))


def test_min_area_is_recorded_without_changing_raw_count(tmp_path: Path):
    mascara = np.zeros((12, 12), dtype=np.uint8)
    mascara[1:5, 1:5] = 255
    mascara[9, 9] = 255
    caminho_entrada = tmp_path / "filter.png"
    cv2.imwrite(str(caminho_entrada), mascara)

    resumo = analyze_mask(caminho_entrada, tmp_path / "filter_result", area_minima=2, tamanho_kernel=1)

    assert resumo["final"]["count_raw"] == 2
    assert resumo["final"]["count_filtered"] == 1
    with Path(resumo["files"]["final_csv"]).open(encoding="utf-8", newline="") as arquivo_csv:
        linhas = list(csv.DictReader(arquivo_csv))
    assert {linha["kept"] for linha in linhas} == {"true", "false"}


def test_cli_analyzes_both_study_masks_and_writes_reproducible_outputs(tmp_path: Path):
    for cena, metodo, limiar in (
        ("cena_favoravel", "fixed", "120"),
        ("cena_dificil", "fixed", "110"),
    ):
        caminho_imagem = RAIZ / "images" / "input" / f"{cena}.png"
        caminho_mascara = tmp_path / f"{cena}_mask.png"
        argumentos_segmentacao = [
            "--input",
            str(caminho_imagem),
            "--output",
            str(caminho_mascara),
            "--operation",
            "segment",
            "--method",
            metodo,
        ]
        if metodo == "fixed":
            argumentos_segmentacao.extend(["--threshold", limiar])
        resultado_segmentacao = run_cli(*argumentos_segmentacao)
        assert resultado_segmentacao.returncode == 0, resultado_segmentacao.stderr

        prefixo = tmp_path / cena
        resultado_analise = run_cli(
            "--input",
            str(caminho_mascara),
            "--output",
            str(prefixo),
            "--operation",
            "analyze",
            "--connectivity",
            "8",
        )
        assert resultado_analise.returncode == 0, resultado_analise.stderr
        resumo = json.loads((tmp_path / f"{cena}_summary.json").read_text(encoding="utf-8"))

        for sufixo in ("initial.png", "opened.png", "final.png", "initial.csv", "final.csv", "labels.png"):
            assert (tmp_path / f"{cena}_{sufixo}").is_file()
        for etapa in ("initial", "final"):
            mascara_etapa = cv2.imread(resumo["files"][etapa], cv2.IMREAD_UNCHANGED)
            with Path(resumo["files"][f"{etapa}_csv"]).open(encoding="utf-8", newline="") as arquivo_csv:
                linhas = list(csv.DictReader(arquivo_csv))
            assert sum(int(linha["area"]) for linha in linhas) == int(np.count_nonzero(mascara_etapa == 255))


def test_invalid_connectivity_is_rejected_by_cli(tmp_path: Path):
    caminho_entrada = tmp_path / "mask.png"
    cv2.imwrite(str(caminho_entrada), np.zeros((5, 5), dtype=np.uint8))
    resultado = run_cli(
        "--input",
        str(caminho_entrada),
        "--output",
        str(tmp_path / "invalid"),
        "--operation",
        "analyze",
        "--connectivity",
        "6",
    )
    assert resultado.returncode != 0


def test_cli_rejects_invalid_masks_and_analysis_parameters(tmp_path: Path):
    caminho_colorido = tmp_path / "color.png"
    caminho_nao_binario = tmp_path / "non_binary.png"
    caminho_valido = tmp_path / "valid.png"
    cv2.imwrite(str(caminho_colorido), np.zeros((5, 5, 3), dtype=np.uint8))
    cv2.imwrite(str(caminho_nao_binario), np.array([[0, 127], [255, 0]], dtype=np.uint8))
    cv2.imwrite(str(caminho_valido), np.zeros((5, 5), dtype=np.uint8))

    casos = [
        (tmp_path / "missing.png", []),
        (caminho_colorido, []),
        (caminho_nao_binario, []),
        (caminho_valido, ["--min-area", "-1"]),
        (caminho_valido, ["--kernel-size", "2"]),
        (caminho_valido, ["--open-iterations", "0"]),
    ]
    for indice, (caminho_entrada, argumentos_extras) in enumerate(casos):
        resultado = run_cli(
            "--input",
            str(caminho_entrada),
            "--output",
            str(tmp_path / f"invalid_{indice}"),
            "--operation",
            "analyze",
            *argumentos_extras,
        )
        assert resultado.returncode != 0
        assert "Erro:" in resultado.stderr
