# Dashboard — Monografia 1

Frontend para visualização dos resultados gerados pelo projeto de análise de indicadores macroeconômicos e títulos do Tesouro Direto.

O projeto mantém a separação entre:

```text
coleta dos dados → análise → resultados CSV → dashboard
```

O frontend **não refaz os cálculos da análise**. Ele lê os arquivos gerados por `analise_dados.py`.

---

## 1. Estrutura do projeto

A estrutura esperada é:

```text
monografia1_projeto/
│
├── consulta_dados/
│   ├── bcdata.sgs.432.csv
│   ├── bcdata.sgs.433.csv
│   ├── bcdata.sgs.24363.csv
│   ├── bcdata.sgs.24369.csv
│   ├── extracao_dados.py
│   └── PrecoTaxaTesouroDireto.csv
│
├── resultados/
│   ├── painel_mensal.csv
│   ├── correlacoes_defasagens.csv
│   └── estudo_caso_selic.csv
│
├── frontend/
│   ├── index.html
│   └── style.css
│
├── analise_dados.py
└── consultas_merc_financeiro.sql
```

### Responsabilidade de cada parte

| Pasta/arquivo | Função |
|---|---|
| `consulta_dados/` | Arquivos de dados e script de extração |
| `extracao_dados.py` | Carrega/organiza os dados e alimenta o banco |
| `analise_dados.py` | Executa os cálculos e gera os resultados da pesquisa |
| `resultados/` | Armazena os CSVs produzidos pela análise |
| `frontend/` | Interface visual do dashboard |
| `consultas_merc_financeiro.sql` | Consultas/estrutura SQL utilizadas no projeto |

---

# 2. Pré-requisitos

Antes de executar o projeto, tenha instalado:

- **Python 3**
- **MySQL**, caso vá executar novamente a etapa de extração/análise que depende do banco
- **Visual Studio Code** (opcional, mas recomendado)
- Um navegador atualizado, como Chrome, Edge ou Firefox

Para conferir se o Python está instalado:

### Windows

```powershell
py --version
```

Se esse comando não funcionar:

```powershell
python --version
```

### macOS

```bash
python3 --version
```

### Linux

```bash
python3 --version
```

---

# 3. Windows

## 3.1 Abrir o projeto

No Visual Studio Code:

1. Abra o VS Code.
2. Selecione **File > Open Folder**.
3. Escolha a pasta:

```text
monografia1_projeto
```

A pasta aberta deve ser a pasta principal do projeto, e não apenas `frontend`.

---

## 3.2 Abrir o terminal

No VS Code:

```text
Terminal → New Terminal
```

Confirme que o terminal está localizado na pasta principal:

```text
monografia1_projeto
```

Você pode verificar com:

```powershell
dir
```

Deve aparecer algo semelhante a:

```text
consulta_dados
resultados
frontend
analise_dados.py
consultas_merc_financeiro.sql
```

---

## 3.3 Executar a análise

Para gerar/atualizar os arquivos da pasta `resultados`, execute:

```powershell
py analise_dados.py
```

Os arquivos esperados são:

```text
resultados/
├── painel_mensal.csv
├── correlacoes_defasagens.csv
└── estudo_caso_selic.csv
```

> Se o seu ambiente exigir `python` em vez de `py`, utilize:
>
> ```powershell
> python analise_dados.py
> ```

---

## 3.4 Iniciar o servidor do frontend

Ainda no terminal, na pasta principal do projeto:

```powershell
py -m http.server 8000
```

Ou:

```powershell
python -m http.server 8000
```

O terminal deverá mostrar uma mensagem indicando que o servidor está utilizando a porta `8000`.

---

## 3.5 Abrir o dashboard

Abra o navegador e acesse:

```text
http://localhost:8000/frontend/
```

Alternativamente:

```text
http://127.0.0.1:8000/frontend/
```

---

# 4. macOS

## 4.1 Abrir o projeto

Abra o projeto no VS Code ou pelo Terminal.

Entre na pasta:

```bash
cd /caminho/para/monografia1_projeto
```

Por exemplo:

```bash
cd ~/Documentos/monografia1_projeto
```

Verifique os arquivos:

```bash
ls
```

---

## 4.2 Executar a análise

Utilize:

```bash
python3 analise_dados.py
```

Depois confirme se os resultados foram gerados:

```bash
ls resultados
```

Devem aparecer:

```text
painel_mensal.csv
correlacoes_defasagens.csv
estudo_caso_selic.csv
```

---

## 4.3 Iniciar o servidor

Execute:

```bash
python3 -m http.server 8000
```

---

## 4.4 Abrir o dashboard

No navegador:

```text
http://localhost:8000/frontend/
```

ou:

```text
http://127.0.0.1:8000/frontend/
```

Para interromper o servidor:

```text
Ctrl + C
```

---

# 5. Linux

## 5.1 Abrir o projeto

No terminal:

```bash
cd /caminho/para/monografia1_projeto
```

Confira:

```bash
ls
```

A pasta deve conter:

```text
consulta_dados
resultados
frontend
analise_dados.py
consultas_merc_financeiro.sql
```

---

## 5.2 Executar a análise

Execute:

```bash
python3 analise_dados.py
```

Confira os resultados:

```bash
ls resultados
```

---

## 5.3 Iniciar o servidor

Execute:

```bash
python3 -m http.server 8000
```

---

## 5.4 Abrir o dashboard

Acesse:

```text
http://localhost:8000/frontend/
```

ou:

```text
http://127.0.0.1:8000/frontend/
```

Para parar o servidor:

```text
Ctrl + C
```

---

# 6. Fluxo completo de execução

Sempre que quiser atualizar o dashboard depois de modificar ou atualizar os dados, siga esta sequência:

```text
1. Atualizar/obter os dados
           ↓
2. extracao_dados.py
           ↓
3. Banco de dados
           ↓
4. analise_dados.py
           ↓
5. resultados/*.csv
           ↓
6. servidor HTTP
           ↓
7. frontend/index.html
           ↓
8. Dashboard
```

Na prática, quando os dados já estiverem disponíveis e a análise puder ser executada, o procedimento é:

```bash
python analise_dados.py
```

Depois:

```bash
python -m http.server 8000
```

E abrir:

```text
http://localhost:8000/frontend/
```

No Windows, você também pode usar `py`:

```powershell
py analise_dados.py
py -m http.server 8000
```

---

# 7. O frontend depende de quais arquivos?

O dashboard utiliza os CSVs da pasta `resultados`:

### `painel_mensal.csv`

Alimenta principalmente:

- cards de indicadores;
- gráfico macroeconômico;
- gráficos individuais dos títulos;
- comparação entre títulos;
- tabela de dados mensais.

### `correlacoes_defasagens.csv`

Alimenta:

- heatmap;
- ranking das maiores correlações;
- tabela de correlações;
- filtros de lag.

### `estudo_caso_selic.csv`

Alimenta:

- estudo de caso das decisões da Selic;
- gráfico de variação do PU;
- tabela de taxa antes/depois;
- variação da taxa;
- variação do preço unitário.

---

# 8. Não abra o HTML diretamente

Evite executar o arquivo com duplo clique:

```text
frontend/index.html
```

Isso pode fazer o navegador bloquear o carregamento dos arquivos CSV por causa das regras de segurança de arquivos locais.

Use sempre um servidor local:

```bash
python -m http.server 8000
```

E depois:

```text
http://localhost:8000/frontend/
```

---

# 9. Problemas comuns

## Erro: `py` ou `python` não é reconhecido — Windows

Tente:

```powershell
python --version
```

Se nenhum funcionar, instale o Python e habilite a opção de adicionar o Python ao `PATH`.

Depois feche e abra novamente o VS Code.

---

## Erro: `python3: command not found` — macOS/Linux

Verifique se o Python está instalado:

```bash
python3 --version
```

Caso não esteja, instale o Python 3 pelo gerenciador de pacotes ou pelo site oficial do Python.

---

## O dashboard abre, mas aparece "Não foi possível carregar os resultados"

Primeiro confira se existem:

```text
resultados/painel_mensal.csv
resultados/correlacoes_defasagens.csv
resultados/estudo_caso_selic.csv
```

Se não existirem, execute:

```bash
python analise_dados.py
```

No Windows:

```powershell
py analise_dados.py
```

---

## O dashboard está sem dados depois de executar `analise_dados.py`

Confira se você iniciou o servidor na **pasta principal**:

```text
monografia1_projeto/
```

e não dentro de:

```text
monografia1_projeto/frontend/
```

O comando correto deve ser executado na raiz:

```bash
python -m http.server 8000
```

Depois:

```text
http://localhost:8000/frontend/
```

---

## Porta 8000 já está sendo utilizada

Escolha outra porta, por exemplo:

```bash
python -m http.server 8080
```

Então abra:

```text
http://localhost:8080/frontend/
```

No Windows:

```powershell
py -m http.server 8080
```

---

# 10. Encerrar o servidor

No terminal onde o servidor está rodando:

```text
Ctrl + C
```

O servidor será encerrado.

---

# 11. Ordem recomendada para apresentação do TCC

Para uma apresentação ou demonstração, recomenda-se:

### Etapa 1 — Preparação

Executar:

```bash
python analise_dados.py
```

### Etapa 2 — Dashboard

Executar:

```bash
python -m http.server 8000
```

### Etapa 3 — Navegador

Abrir:

```text
http://localhost:8000/frontend/
```

### Etapa 4 — Apresentação

Mostrar, nesta ordem:

1. **Visão geral**
2. **Evolução dos títulos**
3. **Comparação entre os títulos**
4. **Correlações e defasagens**
5. **Estudo de caso das decisões da Selic**
6. **Tabela dos dados**

Essa ordem acompanha a lógica da análise e facilita relacionar o dashboard aos resultados apresentados no TCC.

---

# 12. Observação importante sobre o banco de dados

O frontend **não acessa diretamente o MySQL**.

A divisão do projeto é:

```text
MySQL
  ↓
analise_dados.py
  ↓
arquivos CSV em resultados/
  ↓
frontend
```

Isso significa que o dashboard funciona como uma camada de **apresentação dos resultados da análise**.

Portanto, alterações na lógica dos cálculos devem ser feitas no `analise_dados.py`, e não no JavaScript do frontend.

---

# 13. Resumo rápido

### Windows

```powershell
cd caminho\para\monografia1_projeto
py analise_dados.py
py -m http.server 8000
```

Abrir:

```text
http://localhost:8000/frontend/
```

### macOS

```bash
cd /caminho/para/monografia1_projeto
python3 analise_dados.py
python3 -m http.server 8000
```

Abrir:

```text
http://localhost:8000/frontend/
```

### Linux

```bash
cd /caminho/para/monografia1_projeto
python3 analise_dados.py
python3 -m http.server 8000
```

Abrir:

```text
http://localhost:8000/frontend/
```

---

## 14. Dependências

O servidor do frontend utiliza apenas recursos nativos do Python:

```text
http.server
```

O frontend utiliza:

```text
HTML
CSS
JavaScript
Canvas
```

Não é necessário instalar Node.js, npm ou um framework JavaScript para executar o dashboard.

As dependências específicas utilizadas pelo `analise_dados.py` continuam sendo as do ambiente Python do projeto.
