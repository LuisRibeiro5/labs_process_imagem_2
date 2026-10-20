import argparse
import sys
from pathlib import Path

import cv2
import numpy as np


SUPPORTED_METHODS = ("fixed", "otsu", "adaptive", "hsv")


def parse_hsv_range(raw_value: str) -> tuple[int, int, int]:
    parts = [item.strip() for item in raw_value.split(",")]
    if len(parts) != 3:
        raise ValueError("O intervalo HSV deve ter o formato 'h,s,v'.")

    try:
        values = [int(item) for item in parts]
    except ValueError as exc:
        raise ValueError("Os valores HSV devem ser inteiros.") from exc

    h, s, v = values
    if not 0 <= h <= 179 or not 0 <= s <= 255 or not 0 <= v <= 255:
        raise ValueError("HSV deve usar H entre 0 e 179 e S/V entre 0 e 255.")
    return h, s, v


def to_grayscale(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return image.astype(np.uint8)
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def fixed_threshold_mask(gray: np.ndarray, threshold: int, invert: bool = False) -> np.ndarray:
    if not 0 <= threshold <= 255:
        raise ValueError("O limiar fixo deve estar entre 0 e 255.")

    if invert:
        mask = (gray < threshold).astype(np.uint8) * 255
    else:
        mask = (gray >= threshold).astype(np.uint8) * 255
    return mask.astype(np.uint8)


def otsu_threshold_mask(gray: np.ndarray, invert: bool = False) -> np.ndarray:
    _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if invert:
        mask = cv2.bitwise_not(mask)
    return mask.astype(np.uint8)


def adaptive_threshold_mask(gray: np.ndarray, block_size: int, constant: int, invert: bool = False) -> np.ndarray:
    if block_size < 3 or block_size % 2 == 0:
        raise ValueError("O bloco adaptativo deve ser ímpar e maior ou igual a 3.")

    mode = cv2.THRESH_BINARY_INV if invert else cv2.THRESH_BINARY
    mask = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, mode, block_size, constant)
    return mask.astype(np.uint8)


def hsv_mask(image: np.ndarray, lower_range: tuple[int, int, int], upper_range: tuple[int, int, int], invert: bool = False) -> np.ndarray:
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    h_low, s_low, v_low = lower_range
    h_high, s_high, v_high = upper_range
    if s_low > s_high or v_low > v_high:
        raise ValueError("Os limites inferiores de S e V não podem superar os limites superiores.")
    if h_low <= h_high:
        mask = cv2.inRange(
            hsv,
            np.array(lower_range, dtype=np.uint8),
            np.array(upper_range, dtype=np.uint8),
        )
    else:
        faixa_alta = cv2.inRange(
            hsv,
            np.array([h_low, s_low, v_low], dtype=np.uint8),
            np.array([179, s_high, v_high], dtype=np.uint8),
        )
        faixa_baixa = cv2.inRange(
            hsv,
            np.array([0, s_low, v_low], dtype=np.uint8),
            np.array([h_high, s_high, v_high], dtype=np.uint8),
        )
        mask = cv2.bitwise_or(faixa_alta, faixa_baixa)
    if invert:
        mask = cv2.bitwise_not(mask)
    return mask.astype(np.uint8)


def validate_mask(mask: np.ndarray, image_shape: tuple[int, ...]) -> np.ndarray:
    if mask.ndim != 2:
        raise ValueError("A máscara final deve possuir apenas um canal em tom de cinza.")

    if mask.shape[:2] != image_shape[:2]:
        raise ValueError("A máscara final precisa manter a mesma largura e altura da imagem de entrada.")

    unique_values = set(np.unique(mask).tolist())
    if not unique_values.issubset({0, 255}):
        raise ValueError("A máscara final deve conter somente 0 e 255 como valores válidos.")

    return mask.astype(np.uint8)


def segment_image(
    image: np.ndarray,
    method: str,
    threshold: int | None = None,
    block_size: int = 31,
    constant: int = 5,
    invert: bool = False,
    hsv_lower: str | None = None,
    hsv_upper: str | None = None,
) -> np.ndarray:
    if method not in SUPPORTED_METHODS:
        raise ValueError(f"Método desconhecido: {method}")

    if method == "fixed":
        if threshold is None:
            raise ValueError("O método 'fixed' exige o parâmetro --threshold.")
        gray = to_grayscale(image)
        return validate_mask(fixed_threshold_mask(gray, threshold, invert), image.shape)

    if method == "otsu":
        gray = to_grayscale(image)
        return validate_mask(otsu_threshold_mask(gray, invert), image.shape)

    if method == "adaptive":
        gray = to_grayscale(image)
        return validate_mask(adaptive_threshold_mask(gray, block_size, constant, invert), image.shape)

    lower_range = parse_hsv_range(hsv_lower or "10,40,40")
    upper_range = parse_hsv_range(hsv_upper or "80,255,255")
    return validate_mask(hsv_mask(image, lower_range, upper_range, invert), image.shape)


def save_image(image: np.ndarray, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    success = cv2.imwrite(str(path), image)
    if not success:
        raise IOError(f"Falha ao salvar a imagem em {path}")


def validate_mask_output_path(path: Path) -> None:
    lossless_extensions = {".png", ".bmp", ".tif", ".tiff"}
    if path.suffix.lower() not in lossless_extensions:
        raise ValueError("A máscara deve ser salva em PNG, BMP ou TIFF sem perdas.")


def get_output_path(base_output: Path, default_name: str) -> Path:
    if base_output.is_dir() or str(base_output).endswith(("/", "\\")):
        return base_output / default_name
    return base_output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Laboratório M2.1 — segmentação binária")
    parser.add_argument("--input", required=True, help="Caminho da imagem de entrada")
    parser.add_argument("--output", required=True, help="Diretório ou arquivo de saída")
    parser.add_argument("--operation", required=True, choices=["segment"], help="Operação a ser executada")
    parser.add_argument("--method", required=True, choices=SUPPORTED_METHODS, help="Método de segmentação")
    parser.add_argument("--threshold", type=int, default=None, help="Limiar fixo em 0..255 para o método fixed")
    parser.add_argument("--block-size", type=int, default=31, help="Tamanho de bloco para threshold adaptativo")
    parser.add_argument("--constant", type=int, default=5, help="Constante C do threshold adaptativo")
    parser.add_argument("--hsv-lower", type=str, default="10,40,40", help="Limite inferior em HSV: h,s,v")
    parser.add_argument("--hsv-upper", type=str, default="80,255,255", help="Limite superior em HSV: h,s,v")
    parser.add_argument("--invert", action="store_true", help="Inverte a máscara final quando necessário")
    return parser


def main() -> None:
    args = build_parser().parse_args()

    try:
        image = cv2.imread(args.input, cv2.IMREAD_UNCHANGED)
        if image is None:
            raise FileNotFoundError(f"Não foi possível ler a imagem em {args.input}")

        mask = segment_image(
            image=image,
            method=args.method,
            threshold=args.threshold,
            block_size=args.block_size,
            constant=args.constant,
            invert=args.invert,
            hsv_lower=args.hsv_lower,
            hsv_upper=args.hsv_upper,
        )

        output_path = get_output_path(Path(args.output), f"mask_{args.method}.png")
        validate_mask_output_path(output_path)
        save_image(mask, output_path)

        foreground_ratio = float(np.mean(mask == 255))
        print(f"Máscara salva em: {output_path}")
        print(f"Proporção de primeiro plano: {foreground_ratio:.4f}")
    except (OSError, RuntimeError, ValueError, cv2.error) as exc:  # pragma: no cover - guard for CLI usage
        print(f"Erro: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
