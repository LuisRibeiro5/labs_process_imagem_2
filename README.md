# Labs de Processamento de Imagens — M2

Oi! Aqui estão meus trabalhos dos laboratórios M2.1 e M2.2, feitos em Python com OpenCV. No primeiro, comecei a testar formas de separar regiões de interesse do fundo usando máscaras binárias. No segundo, continuei o projeto para limpar essas máscaras e contar os componentes conectados.

## O que tem em cada pasta

- [`lab_m2_1/`](./lab_m2_1/) tem a primeira etapa: segmentação por limiar fixo, Otsu, método adaptativo e HSV, além dos testes e do relatório M2.1.
- [`lab_m2_2/`](./lab_m2_2/) dá continuidade à atividade. O mesmo módulo `pdi_lab` mantém a operação `segment` e acrescenta `analyze`, que aplica abertura e fechamento, mede componentes e salva CSVs e imagens dos estágios.

Cada pasta tem seus próprios arquivos de dependências, imagens de entrada e testes. Para rodar uma etapa, entre na pasta correspondente e prepare o ambiente:

```bash
cd lab_m2_1
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -e .
```

Para rodar o M2.2, faça o mesmo trocando o diretório:

```bash
cd lab_m2_2
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -e .
```

## Alguns comandos

Dentro de `lab_m2_1`, para gerar uma máscara com limiar fixo:

```bash
python -m pdi_lab --input images/input/cena_favoravel.png --output images/output/cena_favoravel_fixed.png --operation segment --method fixed --threshold 120
```

Dentro de `lab_m2_2`, posso gerar uma máscara e depois analisar seus componentes:

```bash
python -m pdi_lab --input images/input/cena_dificil.png --output images/output/cena_dificil_mask.png --operation segment --method fixed --threshold 110
python -m pdi_lab --input images/output/cena_dificil_mask.png --output results/cena_dificil --operation analyze --connectivity 8 --min-area 10
```

Os comandos com as duas configurações de segmentação e os parâmetros de análise estão nos READMEs de cada laboratório. Os relatórios também ficam nas respectivas pastas.

## Testes

Em cada pasta de laboratório, com o ambiente ativado, rode:

```bash
python -m pytest -q
```
