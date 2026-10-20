# Laboratório M2.2 — Componentes conexos e sequência morfológica

## Objetivo

Continuação do M2.1 no mesmo pacote Python `pdi_lab`: preserva a operação `segment` e acrescenta `analyze` para limpar uma máscara binária, medir e rotular componentes conexos e comparar os resultados antes e depois de uma sequência morfológica.

Este é o projeto consolidado dos dois marcos. Seu [lab.json](./lab.json) registra as etapas `m2.1` e `m2.2`.

## Estrutura

```text
lab_m2_2/
├── README.md
├── REPORT.md
├── AI_USAGE.md
├── lab.json
├── pyproject.toml
├── requirements.txt
├── images/
│   ├── input/
│   └── output/
├── results/
├── src/pdi_lab/
│   ├── __init__.py
│   ├── __main__.py
│   └── analyze.py
└── tests/
```

## Ambiente

Requisitos: Python 3.10 ou superior, `opencv-python-headless==5.0.0.93` (binding Python `cv2`) e NumPy `>=1.26.0`.

```bash
cd lab_m2_2
```

Crie o ambiente virtual no Linux/macOS:

```bash
python3 -m venv .venv
```

Ou no Windows:

```powershell
py -3 -m venv .venv
```

Ative o ambiente no Linux/macOS:

```bash
source .venv/bin/activate
```

Ou no Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Com o ambiente ativado, instale as dependências:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
```

Os exemplos abaixo usam `python -m pdi_lab`, disponível nas plataformas em que Python está instalado. A instalação também disponibiliza o comando `pdi_lab`.

## Operação `segment` (M2.1)

A operação anterior continua disponível:

```bash
python -m pdi_lab --input images/input/cena_favoravel.png --output images/output/cena_favoravel_mask.png --operation segment --method fixed --threshold 120
python -m pdi_lab --input images/input/cena_dificil.png --output images/output/cena_dificil_mask.png --operation segment --method fixed --threshold 110
```

Também continuam disponíveis os métodos `otsu`, `adaptive` e `hsv`. Veja a ajuda para parâmetros:

```bash
python -m pdi_lab --help
```

## Operação `analyze` (M2.2)

`--input` recebe uma máscara PNG em escala de cinza, de um canal, com valores somente 0 e 255. `--output` é um prefixo e gera os estágios `*_initial.png`, `*_opened.png`, `*_final.png`, tabelas `*_initial.csv` e `*_final.csv`, uma visualização `*_labels.png` e `*_summary.json`.

```bash
python -m pdi_lab --input images/output/cena_favoravel_mask.png --output results/cena_favoravel_conn4 --operation analyze --connectivity 4 --min-area 10 --kernel-shape ellipse --kernel-size 3 --open-iterations 1 --close-iterations 1
python -m pdi_lab --input images/output/cena_favoravel_mask.png --output results/cena_favoravel_conn8 --operation analyze --connectivity 8 --min-area 10 --kernel-shape ellipse --kernel-size 3 --open-iterations 1 --close-iterations 1
python -m pdi_lab --input images/output/cena_dificil_mask.png --output results/cena_dificil_conn4 --operation analyze --connectivity 4 --min-area 10 --kernel-shape ellipse --kernel-size 3 --open-iterations 1 --close-iterations 1
python -m pdi_lab --input images/output/cena_dificil_mask.png --output results/cena_dificil_conn8 --operation analyze --connectivity 8 --min-area 10 --kernel-shape ellipse --kernel-size 3 --open-iterations 1 --close-iterations 1
```

A sequência é abertura seguida de fechamento. A abertura (`erosão` e depois `dilatação`) visa remover ruído pequeno; o fechamento (`dilatação` e depois `erosão`) visa preencher pequenos furos e interrupções. A forma do kernel aceita `rect`, `ellipse` ou `cross`; seu tamanho deve ser ímpar. A conectividade aceita 4 ou 8, com padrão 8. `--min-area` é opcional e indica a área mínima em pixels para preencher a coluna `kept` do CSV; o padrão é não filtrar. As contagens brutas permanecem registradas.

Em cada imagem, os dois comandos de análise usam a mesma máscara e diferem apenas na conectividade. Os prefixos de saída distintos preservam os resultados de cada execução.

Os CSVs não incluem o rótulo de fundo e contêm `label,area,x,y,width,height,cx,cy,kept`. O resumo JSON inclui parâmetros, estatísticas para conectividade 4 e 8 nos estágios, contagens brutas e filtradas e áreas de primeiro plano. A imagem de rótulos colore os componentes mantidos e desenha suas caixas delimitadoras.

Na segmentação por HSV, os limites aceitam H entre 0 e 179 e S/V entre 0 e 255. Faixas que cruzam 179/0 são divididas internamente em duas partes. As máscaras `segment` são gravadas sem perdas em PNG, BMP ou TIFF.

## Testes

```bash
python -m pytest -q
```

Os testes incluem o caso diagonal para conectividade 4/8, ruído isolado e furo pequeno para a sequência de abertura/fechamento, máscara vazia, objeto tocando a borda, filtragem por área, execução das duas cenas, conservação da soma das áreas no CSV e rejeição de máscaras ou parâmetros inválidos. Os testes do M2.1 também cobrem a segmentação fixa, Otsu, adaptativa e HSV.

## Resultados reproduzíveis

As máscaras usadas nas análises ficam em `images/output/`; as saídas por estágio, CSVs, visualizações e resumos estão em `results/`. Consulte o `REPORT.md` para a comparação e limitações observadas.
