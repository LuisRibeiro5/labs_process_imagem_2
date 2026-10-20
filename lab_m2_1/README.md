# Laboratório M2.1 — Máscara binária e segmentação

## Objetivo

Implementar uma CLI em Python para gerar máscaras binárias por segmentação de objetos, com foco em limiar fixo, limiar Otsu, threshold adaptativo e seleção por faixa HSV. A solução segue a mesma organização do projeto M1, com módulo `pdi_lab`, testes automatizados e documentação em relatório.

## Estrutura

```text
lab_m2_1/
├── README.md
├── REPORT.md
├── AI_USAGE.md
├── lab.json
├── pyproject.toml
├── requirements.txt
├── images/
│   ├── input/
│   │   ├── cena_favoravel.png
│   │   ├── cena_dificil.png
│   │   └── synthetic_threshold.png
│   └── output/
├── results/
├── src/
│   └── pdi_lab/
│       ├── __init__.py
│       └── __main__.py
└── tests/
    └── test_cli.py
```

## Ambiente

```bash
cd lab_m2_1
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
```

## Execução

A interface mínima do laboratório é:

```bash
python -m pdi_lab --input images/input/cena_favoravel.png --output images/output/cena_favoravel_fixed.png --operation segment --method fixed --threshold 120
```

Outras combinações válidas:

```bash
python -m pdi_lab --input images/input/cena_favoravel.png --output images/output/cena_favoravel_otsu.png --operation segment --method otsu

python -m pdi_lab --input images/input/cena_dificil.png --output images/output/cena_dificil_fixed.png --operation segment --method fixed --threshold 110

python -m pdi_lab --input images/input/cena_dificil.png --output images/output/cena_dificil_otsu.png --operation segment --method otsu

python -m pdi_lab --input images/input/cena_dificil.png --output images/output/cena_dificil_hsv.png --operation segment --method hsv --hsv-lower 10,40,40 --hsv-upper 80,255,255

python -m pdi_lab --input images/input/cena_dificil.png --output images/output/cena_dificil_adaptive.png --operation segment --method adaptive --block-size 15 --constant 7
```

Para comparar fixed e Otsu no mesmo conjunto, use os dois primeiros métodos para `cena_favoravel.png` e os dois comandos correspondentes para `cena_dificil.png`. Os arquivos usados e a proporção de primeiro plano estão apresentados no `REPORT.md`.

A faixa HSV de exemplo não seleciona pixels na cena difícil: as imagens são em tons de cinza e, por isso, têm saturação zero, abaixo do limite padrão `40`. Esse comando demonstra a opção HSV da CLI, mas não faz parte da comparação registrada no relatório.

## Métodos implementados

- `fixed`: usa limiar fixo em escala de cinza. O valor `--threshold` varia em 0..255 e a regra aplicada é `valor >= limiar` → foreground (`255`). Isso torna o limiar explícito e consistente para análise de borda.
- `otsu`: calcula o limiar automaticamente com OpenCV usando `THRESH_OTSU`.
- `adaptive`: aplica `adaptiveThreshold` com `cv2.ADAPTIVE_THRESH_MEAN_C` e parâmetros `--block-size` e `--constant`.
- `hsv`: converte para HSV e seleciona o objeto por faixa de tons, saturação e valor, com limites `--hsv-lower` e `--hsv-upper` no formato `h,s,v`.

Para HSV, a matiz aceita o intervalo 0..179 e saturação/valor aceitam 0..255. Se a faixa da matiz cruzar 179/0, por exemplo `--hsv-lower 170,40,40 --hsv-upper 10,255,255`, o programa combina as duas partes da faixa. A saída da máscara aceita formatos sem perdas: PNG, BMP ou TIFF.

## Validação

```bash
python -m pytest -q
```

Os testes verificam:

- imagem sintética com limiar fixo previsível;
- processamento das duas cenas com duas configurações;
- método HSV e adaptativo;
- falhas de leitura, método desconhecido e parâmetro inválido;
- máscara final binária com dimensões coerentes e valores `0` ou `255`.

## Observações

- A máscara final é salva em PNG com um canal e valores binários.
- O roteador deste marco aceita a operação `segment`.
- O `--output` aceita tanto um arquivo quanto um diretório: quando for diretório, a saída recebe um nome padrão com o método respectivo.
