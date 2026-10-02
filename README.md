# Simulador de Redes de Filas - Anthony A., Frederico N., Gabriel K. e Leonardo W.

Simulador de redes de filas desenvolvido em Python. Os parâmetros de cada modelo são definidos em arquivos `.yml`, permitindo executar diferentes cenários sem alterar o código-fonte do simulador.

## Requisitos

* Python 3.x
* Biblioteca `PyYAML`

Para instalar o `PyYAML`, execute:

```bash
pip install pyyaml
```

## Organização dos arquivos

A organização do projeto é como segue:

```
trabalho1_sma/
├── simulador.py
├── modelos/
│   ├── trab1.yml
│   ├── cenario1_gg1_5.yml
│   ├── cenario2_gg2_5.yml
│   ├── cenario3_tandem.yml
│   └── cenario4_rede.yml
└── README.md
```

Os arquivos `.yml` contêm a configuração das filas, distribuições de chegada e atendimento, capacidades, servidores, probabilidades de roteamento e parâmetros da simulação.

## Executando um modelo

Para executar um arquivo `.yml` específico, abra o terminal na pasta do projeto e utilize:

```bash
python simulador.py modelos/trab1.yml
```

No Windows, também pode ser utilizado:

```bash
py simulador.py modelos/trab1.yml
```

O caminho do arquivo `.yml` pode ser alterado conforme o modelo que deseja executar.

Por exemplo:

```bash
python simulador.py modelos/cenario1_gg1_5.yml
```

ou:

```bash
python simulador.py modelos/cenario2_gg2_5.yml
```

## Executando vários modelos

Também é possível passar mais de um arquivo `.yml` na mesma execução:

```bash
python simulador.py modelos/cenario1_gg1_5.yml modelos/cenario2_gg2_5.yml
```

Os modelos serão executados individualmente e os resultados serão apresentados no terminal.

## Executando sem informar um modelo

Caso o simulador seja executado sem argumentos:

```bash
python simulador.py
```

ele procura arquivos `.yml` dentro da pasta `modelos` localizada no mesmo diretório do programa e executa os modelos encontrados.

## Saída

Ao executar um modelo, o simulador apresenta os resultados de cada fila, incluindo:

* estados possíveis da fila;
* tempo acumulado em cada estado;
* probabilidade de permanência em cada estado;
* quantidade de perdas da fila;
* tempo global da simulação.

Um exemplo simplificado da saída é:

```text
==============================================================
  F1
==============================================================
  Estado    Tempo Acumulado    Probabilidade
  --------------------------------------------------
       0          13175.6234        0.3211
       1          21677.2877        0.5284
       2           5683.4951        0.1385
       ...
  
  Perdas: 0

==============================================================
  Tempo global da simulação: 41056.9050 s
==============================================================
```

## Observação importante

O arquivo `.yml` deve ser informado como argumento quando se deseja executar um modelo específico.

Por exemplo, estando na pasta:

```
trabalho1_sma/
```

e possuindo:

```
trabalho1_sma/
├── simulador.py
└── modelos/
    └── trab1.yml
```

o comando correto é:

```bash
python simulador.py modelos/trab1.yml
```

O simulador utiliza as configurações presentes no arquivo `.yml` para construir e executar a rede de filas, portanto não é necessário alterar o código Python para cada cenário.
