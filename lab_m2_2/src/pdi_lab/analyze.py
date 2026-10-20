import csv
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np


FORMAS_KERNEL = {
    "rect": cv2.MORPH_RECT,
    "ellipse": cv2.MORPH_ELLIPSE,
    "cross": cv2.MORPH_CROSS,
}


def load_binary_mask(caminho: Path) -> np.ndarray:
    mascara = cv2.imread(str(caminho), cv2.IMREAD_UNCHANGED)
    if mascara is None:
        raise FileNotFoundError(f"Não foi possível ler a máscara em {caminho}")
    if mascara.ndim != 2:
        raise ValueError("A entrada de analyze deve ser uma máscara de um canal.")
    valores = set(np.unique(mascara).tolist())
    if not valores.issubset({0, 255}):
        raise ValueError(f"A máscara deve conter somente 0 e 255; valores encontrados: {sorted(valores)}")
    return mascara.astype(np.uint8)


def validate_morphology(tamanho_kernel: int, forma_kernel: str, iteracoes_abertura: int, iteracoes_fechamento: int) -> None:
    if forma_kernel not in FORMAS_KERNEL:
        raise ValueError("A forma do elemento estruturante deve ser rect, ellipse ou cross.")
    if tamanho_kernel < 1 or tamanho_kernel % 2 == 0:
        raise ValueError("O tamanho do elemento estruturante deve ser ímpar e maior ou igual a 1.")
    if iteracoes_abertura < 1 or iteracoes_fechamento < 1:
        raise ValueError("As iterações de abertura e fechamento devem ser pelo menos 1.")


def label_components(mascara: np.ndarray, conectividade: int) -> tuple[np.ndarray, list[dict[str, Any]]]:
    if conectividade not in (4, 8):
        raise ValueError("A conectividade deve ser 4 ou 8.")

    primeiro_plano = (mascara == 255).astype(np.uint8)
    quantidade, rotulos, estatisticas, centroides = cv2.connectedComponentsWithStats(
        primeiro_plano, connectivity=conectividade, ltype=cv2.CV_32S
    )
    componentes: list[dict[str, Any]] = []
    for rotulo in range(1, quantidade):
        x, y, largura, altura, area = (int(valor) for valor in estatisticas[rotulo])
        centro_x, centro_y = (float(valor) for valor in centroides[rotulo])
        componentes.append(
            {
                "label": rotulo,
                "area": area,
                "x": x,
                "y": y,
                "width": largura,
                "height": altura,
                "cx": centro_x,
                "cy": centro_y,
            }
        )
    return rotulos, componentes


def write_components_csv(caminho: Path, componentes: list[dict[str, Any]], area_minima: int | None) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", newline="", encoding="utf-8") as arquivo_csv:
        escritor = csv.DictWriter(
            arquivo_csv,
            fieldnames=["label", "area", "x", "y", "width", "height", "cx", "cy", "kept"],
            lineterminator="\n",
        )
        escritor.writeheader()
        for componente in componentes:
            escritor.writerow(
                {
                    **componente,
                    "cx": f"{componente['cx']:.3f}",
                    "cy": f"{componente['cy']:.3f}",
                    "kept": str(area_minima is None or componente["area"] >= area_minima).lower(),
                }
            )


def draw_component_labels(
    mascara: np.ndarray,
    rotulos: np.ndarray,
    componentes: list[dict[str, Any]],
    area_minima: int | None,
) -> np.ndarray:
    imagem = cv2.cvtColor(mascara, cv2.COLOR_GRAY2BGR)
    for componente in componentes:
        if area_minima is not None and componente["area"] < area_minima:
            continue
        rotulo = componente["label"]
        cor = (
            int((37 * rotulo + 83) % 256),
            int((97 * rotulo + 149) % 256),
            int((17 * rotulo + 211) % 256),
        )
        pixels_componente = rotulos == rotulo
        imagem[pixels_componente] = cv2.addWeighted(
            imagem[pixels_componente],
            0.35,
            np.full_like(imagem[pixels_componente], cor),
            0.65,
            0,
        )
        x, y = componente["x"], componente["y"]
        largura, altura = componente["width"], componente["height"]
        cv2.rectangle(imagem, (x, y), (x + largura - 1, y + altura - 1), cor, 1)
        cv2.putText(
            imagem,
            str(rotulo),
            (x, max(y - 3, 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.35,
            cor,
            1,
            cv2.LINE_AA,
        )
    return imagem


def component_stats(mascara: np.ndarray, conectividade: int, area_minima: int | None) -> dict[str, int]:
    _, componentes = label_components(mascara, conectividade)
    mantidos = [item for item in componentes if area_minima is None or item["area"] >= area_minima]
    return {
        "count_raw": len(componentes),
        "count_filtered": len(mantidos),
        "area_foreground_raw": int(np.count_nonzero(mascara == 255)),
        "area_components_filtered": int(sum(item["area"] for item in mantidos)),
    }


def analyze_mask(
    caminho_entrada: Path,
    prefixo_saida: Path,
    conectividade: int = 8,
    area_minima: int | None = None,
    forma_kernel: str = "ellipse",
    tamanho_kernel: int = 3,
    iteracoes_abertura: int = 1,
    iteracoes_fechamento: int = 1,
) -> dict[str, Any]:
    if conectividade not in (4, 8):
        raise ValueError("A conectividade deve ser 4 ou 8.")
    if area_minima is not None and area_minima < 0:
        raise ValueError("O valor de --min-area deve ser não negativo.")
    validate_morphology(tamanho_kernel, forma_kernel, iteracoes_abertura, iteracoes_fechamento)

    mascara_inicial = load_binary_mask(caminho_entrada)
    prefixo = prefixo_saida
    prefixo.parent.mkdir(parents=True, exist_ok=True)
    kernel = cv2.getStructuringElement(FORMAS_KERNEL[forma_kernel], (tamanho_kernel, tamanho_kernel))

    mascara_aberta = cv2.morphologyEx(
        mascara_inicial,
        cv2.MORPH_OPEN,
        kernel,
        iterations=iteracoes_abertura,
        borderType=cv2.BORDER_CONSTANT,
    )
    mascara_final = cv2.morphologyEx(
        mascara_aberta,
        cv2.MORPH_CLOSE,
        kernel,
        iterations=iteracoes_fechamento,
        borderType=cv2.BORDER_CONSTANT,
    )
    caminhos_etapas = {
        "initial": prefixo.with_name(f"{prefixo.name}_initial.png"),
        "opened": prefixo.with_name(f"{prefixo.name}_opened.png"),
        "final": prefixo.with_name(f"{prefixo.name}_final.png"),
    }
    for etapa, imagem_etapa in (
        ("initial", mascara_inicial),
        ("opened", mascara_aberta),
        ("final", mascara_final),
    ):
        if not cv2.imwrite(str(caminhos_etapas[etapa]), imagem_etapa):
            raise OSError(f"Falha ao salvar o estágio morfológico: {caminhos_etapas[etapa]}")

    rotulos_iniciais, componentes_iniciais = label_components(mascara_inicial, conectividade)
    rotulos_finais, componentes_finais = label_components(mascara_final, conectividade)
    csv_inicial = prefixo.with_name(f"{prefixo.name}_initial.csv")
    csv_final = prefixo.with_name(f"{prefixo.name}_final.csv")
    write_components_csv(csv_inicial, componentes_iniciais, area_minima)
    write_components_csv(csv_final, componentes_finais, area_minima)

    caminho_rotulos = prefixo.with_name(f"{prefixo.name}_labels.png")
    imagem_rotulos = draw_component_labels(mascara_final, rotulos_finais, componentes_finais, area_minima)
    if not cv2.imwrite(str(caminho_rotulos), imagem_rotulos):
        raise OSError(f"Falha ao salvar a visualização dos rótulos: {caminho_rotulos}")

    contagens_conectividade = {
        etapa: {
            str(valor): component_stats(mascara, valor, area_minima)
            for valor in (4, 8)
        }
        for etapa, mascara in (
            ("initial", mascara_inicial),
            ("opened", mascara_aberta),
            ("final", mascara_final),
        )
    }
    resumo: dict[str, Any] = {
        "input": str(caminho_entrada),
        "connectivity": conectividade,
        "min_area": area_minima,
        "morphology": {
            "sequence": ["opening", "closing"],
            "kernel_shape": forma_kernel,
            "kernel_size": tamanho_kernel,
            "open_iterations": iteracoes_abertura,
            "close_iterations": iteracoes_fechamento,
        },
        "files": {
            **{chave: str(valor) for chave, valor in caminhos_etapas.items()},
            "initial_csv": str(csv_inicial),
            "final_csv": str(csv_final),
            "labels": str(caminho_rotulos),
        },
        "connectivity_counts": contagens_conectividade,
        "initial": contagens_conectividade["initial"][str(conectividade)],
        "opened": contagens_conectividade["opened"][str(conectividade)],
        "final": contagens_conectividade["final"][str(conectividade)],
        "area_foreground_change": int(
            np.count_nonzero(mascara_final == 255) - np.count_nonzero(mascara_inicial == 255)
        ),
    }
    caminho_resumo = prefixo.with_name(f"{prefixo.name}_summary.json")
    resumo["files"]["summary"] = str(caminho_resumo)
    with caminho_resumo.open("w", encoding="utf-8") as arquivo_resumo:
        json.dump(resumo, arquivo_resumo, indent=2, ensure_ascii=False)

    for nome_etapa, rotulos, componentes in (
        ("initial", rotulos_iniciais, componentes_iniciais),
        ("final", rotulos_finais, componentes_finais),
    ):
        if len(componentes) and int(np.count_nonzero(rotulos)) != sum(item["area"] for item in componentes):
            raise RuntimeError(f"A soma das áreas não confere no estágio {nome_etapa}.")
    return resumo
