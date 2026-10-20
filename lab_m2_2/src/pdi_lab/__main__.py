import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

from pdi_lab.analyze import analyze_mask


METODOS_SUPORTADOS = ("fixed", "otsu", "adaptive", "hsv")


def parse_hsv_range(texto_original: str) -> tuple[int, int, int]:
    partes = [item.strip() for item in texto_original.split(",")]
    if len(partes) != 3:
        raise ValueError("O intervalo HSV deve ter o formato 'h,s,v'.")

    try:
        valores = [int(item) for item in partes]
    except ValueError as exc:
        raise ValueError("Os valores HSV devem ser inteiros.") from exc

    matiz, saturacao, valor = valores
    if not 0 <= matiz <= 179 or not 0 <= saturacao <= 255 or not 0 <= valor <= 255:
        raise ValueError("HSV deve usar H entre 0 e 179 e S/V entre 0 e 255.")
    return matiz, saturacao, valor


def to_grayscale(imagem: np.ndarray) -> np.ndarray:
    if imagem.ndim == 2:
        return imagem.astype(np.uint8)
    return cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)


def fixed_threshold_mask(imagem_cinza: np.ndarray, limiar: int, inverter: bool = False) -> np.ndarray:
    if not 0 <= limiar <= 255:
        raise ValueError("O limiar fixo deve estar entre 0 e 255.")

    if inverter:
        mascara = (imagem_cinza < limiar).astype(np.uint8) * 255
    else:
        mascara = (imagem_cinza >= limiar).astype(np.uint8) * 255
    return mascara.astype(np.uint8)


def otsu_threshold_mask(imagem_cinza: np.ndarray, inverter: bool = False) -> np.ndarray:
    _, mascara = cv2.threshold(imagem_cinza, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if inverter:
        mascara = cv2.bitwise_not(mascara)
    return mascara.astype(np.uint8)


def adaptive_threshold_mask(imagem_cinza: np.ndarray, tamanho_bloco: int, constante: int, inverter: bool = False) -> np.ndarray:
    if tamanho_bloco < 3 or tamanho_bloco % 2 == 0:
        raise ValueError("O bloco adaptativo deve ser ímpar e maior ou igual a 3.")

    modo = cv2.THRESH_BINARY_INV if inverter else cv2.THRESH_BINARY
    mascara = cv2.adaptiveThreshold(
        imagem_cinza, 255, cv2.ADAPTIVE_THRESH_MEAN_C, modo, tamanho_bloco, constante
    )
    return mascara.astype(np.uint8)


def hsv_mask(
    imagem: np.ndarray,
    faixa_inferior: tuple[int, int, int],
    faixa_superior: tuple[int, int, int],
    inverter: bool = False,
) -> np.ndarray:
    if imagem.ndim == 2:
        imagem = cv2.cvtColor(imagem, cv2.COLOR_GRAY2BGR)

    imagem_hsv = cv2.cvtColor(imagem, cv2.COLOR_BGR2HSV)
    h_low, s_low, v_low = faixa_inferior
    h_high, s_high, v_high = faixa_superior
    if s_low > s_high or v_low > v_high:
        raise ValueError("Os limites inferiores de S e V não podem superar os limites superiores.")
    if h_low <= h_high:
        mascara = cv2.inRange(
            imagem_hsv,
            np.array(faixa_inferior, dtype=np.uint8),
            np.array(faixa_superior, dtype=np.uint8),
        )
    else:
        faixa_alta = cv2.inRange(
            imagem_hsv,
            np.array([h_low, s_low, v_low], dtype=np.uint8),
            np.array([179, s_high, v_high], dtype=np.uint8),
        )
        faixa_baixa = cv2.inRange(
            imagem_hsv,
            np.array([0, s_low, v_low], dtype=np.uint8),
            np.array([h_high, s_high, v_high], dtype=np.uint8),
        )
        mascara = cv2.bitwise_or(faixa_alta, faixa_baixa)
    if inverter:
        mascara = cv2.bitwise_not(mascara)
    return mascara.astype(np.uint8)


def validate_mask(mascara: np.ndarray, formato_imagem: tuple[int, ...]) -> np.ndarray:
    if mascara.ndim != 2:
        raise ValueError("A máscara final deve possuir apenas um canal em tom de cinza.")

    if mascara.shape[:2] != formato_imagem[:2]:
        raise ValueError("A máscara final precisa manter a mesma largura e altura da imagem de entrada.")

    valores_unicos = set(np.unique(mascara).tolist())
    if not valores_unicos.issubset({0, 255}):
        raise ValueError("A máscara final deve conter somente 0 e 255 como valores válidos.")

    return mascara.astype(np.uint8)


def segment_image(
    imagem: np.ndarray,
    metodo: str,
    limiar: int | None = None,
    tamanho_bloco: int = 31,
    constante: int = 5,
    inverter: bool = False,
    hsv_inferior: str | None = None,
    hsv_superior: str | None = None,
) -> np.ndarray:
    if metodo not in METODOS_SUPORTADOS:
        raise ValueError(f"Método desconhecido: {metodo}")

    if metodo == "fixed":
        if limiar is None:
            raise ValueError("O método 'fixed' exige o parâmetro --threshold.")
        imagem_cinza = to_grayscale(imagem)
        return validate_mask(fixed_threshold_mask(imagem_cinza, limiar, inverter), imagem.shape)

    if metodo == "otsu":
        imagem_cinza = to_grayscale(imagem)
        return validate_mask(otsu_threshold_mask(imagem_cinza, inverter), imagem.shape)

    if metodo == "adaptive":
        imagem_cinza = to_grayscale(imagem)
        return validate_mask(
            adaptive_threshold_mask(imagem_cinza, tamanho_bloco, constante, inverter), imagem.shape
        )

    faixa_inferior = parse_hsv_range(hsv_inferior or "10,40,40")
    faixa_superior = parse_hsv_range(hsv_superior or "80,255,255")
    return validate_mask(hsv_mask(imagem, faixa_inferior, faixa_superior, inverter), imagem.shape)


def save_image(imagem: np.ndarray, caminho: Path) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    sucesso = cv2.imwrite(str(caminho), imagem)
    if not sucesso:
        raise IOError(f"Falha ao salvar a imagem em {caminho}")


def validar_caminho_mascara(caminho: Path) -> None:
    extensoes_sem_perda = {".png", ".bmp", ".tif", ".tiff"}
    if caminho.suffix.lower() not in extensoes_sem_perda:
        raise ValueError("A máscara deve ser salva em PNG, BMP ou TIFF sem perdas.")


def get_output_path(caminho_saida: Path, nome_padrao: str) -> Path:
    if caminho_saida.is_dir() or str(caminho_saida).endswith(("/", "\\")):
        return caminho_saida / nome_padrao
    return caminho_saida


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Laboratório M2.2 — segmentação e análise de componentes")
    parser.add_argument("--input", dest="caminho_entrada", required=True, help="Caminho da imagem de entrada")
    parser.add_argument("--output", dest="caminho_saida", required=True, help="Arquivo de saída para segment ou prefixo para analyze")
    parser.add_argument("--operation", dest="operacao", required=True, choices=["segment", "analyze"], help="Operação a ser executada")
    parser.add_argument("--method", dest="metodo", choices=METODOS_SUPORTADOS, help="Método de segmentação")
    parser.add_argument("--threshold", dest="limiar", type=int, default=None, help="Limiar fixo em 0..255 para o método fixed")
    parser.add_argument("--block-size", dest="tamanho_bloco", type=int, default=31, help="Tamanho de bloco para threshold adaptativo")
    parser.add_argument("--constant", dest="constante", type=int, default=5, help="Constante C do threshold adaptativo")
    parser.add_argument("--hsv-lower", dest="hsv_inferior", type=str, default="10,40,40", help="Limite inferior em HSV: h,s,v")
    parser.add_argument("--hsv-upper", dest="hsv_superior", type=str, default="80,255,255", help="Limite superior em HSV: h,s,v")
    parser.add_argument("--invert", dest="inverter", action="store_true", help="Inverte a máscara final quando necessário")
    parser.add_argument("--connectivity", dest="conectividade", type=int, choices=[4, 8], default=8, help="Conectividade dos componentes")
    parser.add_argument("--min-area", dest="area_minima", type=int, default=None, help="Área mínima para marcar componentes como mantidos")
    parser.add_argument("--kernel-shape", dest="forma_kernel", choices=["rect", "ellipse", "cross"], default="ellipse", help="Forma do elemento estruturante")
    parser.add_argument("--kernel-size", dest="tamanho_kernel", type=int, default=3, help="Tamanho ímpar do elemento estruturante")
    parser.add_argument("--open-iterations", dest="iteracoes_abertura", type=int, default=1, help="Iterações da abertura")
    parser.add_argument("--close-iterations", dest="iteracoes_fechamento", type=int, default=1, help="Iterações do fechamento após a abertura")
    return parser


def main() -> None:
    opcoes = build_parser().parse_args()

    try:
        if opcoes.operacao == "analyze":
            resumo = analyze_mask(
                caminho_entrada=Path(opcoes.caminho_entrada),
                prefixo_saida=Path(opcoes.caminho_saida),
                conectividade=opcoes.conectividade,
                area_minima=opcoes.area_minima,
                forma_kernel=opcoes.forma_kernel,
                tamanho_kernel=opcoes.tamanho_kernel,
                iteracoes_abertura=opcoes.iteracoes_abertura,
                iteracoes_fechamento=opcoes.iteracoes_fechamento,
            )
            print(f"Análise salva em: {resumo['files']['summary']}")
            print(
                f"Componentes brutos: {resumo['initial']['count_raw']} -> {resumo['final']['count_raw']}"
            )
            return

        if opcoes.metodo is None:
            raise ValueError("A operação 'segment' exige --method.")
        imagem = cv2.imread(opcoes.caminho_entrada, cv2.IMREAD_UNCHANGED)
        if imagem is None:
            raise FileNotFoundError(f"Não foi possível ler a imagem em {opcoes.caminho_entrada}")

        mascara = segment_image(
            imagem=imagem,
            metodo=opcoes.metodo,
            limiar=opcoes.limiar,
            tamanho_bloco=opcoes.tamanho_bloco,
            constante=opcoes.constante,
            inverter=opcoes.inverter,
            hsv_inferior=opcoes.hsv_inferior,
            hsv_superior=opcoes.hsv_superior,
        )

        caminho_saida = get_output_path(Path(opcoes.caminho_saida), f"mask_{opcoes.metodo}.png")
        validar_caminho_mascara(caminho_saida)
        save_image(mascara, caminho_saida)

        proporcao_primeiro_plano = float(np.mean(mascara == 255))
        print(f"Máscara salva em: {caminho_saida}")
        print(f"Proporção de primeiro plano: {proporcao_primeiro_plano:.4f}")
    except (OSError, RuntimeError, ValueError, cv2.error) as exc:  # pragma: no cover - guard for CLI usage
        print(f"Erro: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
