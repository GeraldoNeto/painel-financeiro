# 📊 Painel Financeiro Pessoal

Dashboard interativo para análise e visualização de dados financeiros pessoais, com integração ao Google Sheets e interface construída com Streamlit.

## 🖥️ Demonstração

> Conecte sua planilha do Google Sheets e tenha uma visão completa das suas finanças em tempo real.

## ✨ Funcionalidades

- **KPIs em tempo real** — total de entradas, saldo projetado, valores a vencer e gastos no cartão com comparativo do mês anterior
- **Alertas automáticos** — banner de destaque para contas vencidas e próximas do vencimento
- **Filtros interativos** — seleção de período, status (pendente/pago) e categorias de despesa via sidebar
- **Visualizações gráficas:**
  - Histórico mensal comparativo (entradas vs. gastos)
  - Distribuição de despesas por categoria (pizza)
  - Análise de entradas por responsável
  - Evolução mensal do saldo
- **Tabelas detalhadas** — pendências, contas pagas e entradas registradas
- **Layout responsivo** — adaptado para desktop e mobile

## 🛠️ Tecnologias

| Tecnologia | Versão | Uso |
|---|---|---|
| [Streamlit](https://streamlit.io/) | ≥ 1.35.0 | Interface web interativa |
| [Pandas](https://pandas.pydata.org/) | ≥ 2.0.0 | Manipulação e análise de dados |
| [Plotly](https://plotly.com/) | ≥ 5.20.0 | Gráficos interativos |
| [gspread](https://gspread.readthedocs.io/) | ≥ 6.0.0 | Integração com Google Sheets |
| [google-auth](https://google-auth.readthedocs.io/) | ≥ 2.29.0 | Autenticação com a API do Google |

## ⚙️ Como Usar

### Pré-requisitos

- Python 3.10+
- Conta Google com acesso ao Google Sheets
- Credenciais de uma conta de serviço do Google Cloud

### 1. Clone o repositório

```bash
git clone https://github.com/GeraldoNeto/painel-financeiro.git
cd painel-financeiro
```

### 2. Instale as dependências

```bash
pip install -r requirements.txt
```

### 3. Configure as credenciais

Copie o arquivo de exemplo e preencha com suas credenciais:

```bash
cp secrets.toml.example .streamlit/secrets.toml
```

Edite `.streamlit/secrets.toml` com os dados da sua conta de serviço do Google e o ID da sua planilha.

### 4. Execute a aplicação

```bash
streamlit run app.py
```

Acesse `http://localhost:8501` no navegador.

## 📁 Estrutura do Projeto

```
painel-financeiro/
├── app.py                  # Aplicação principal
├── requirements.txt        # Dependências Python
├── secrets.toml.example    # Exemplo de configuração de credenciais
└── .streamlit/
    └── secrets.toml        # Credenciais (não versionado)
```

## 🔐 Configuração do Google Sheets

1. Acesse o [Google Cloud Console](https://console.cloud.google.com/)
2. Crie um projeto e ative a **Google Sheets API** e a **Google Drive API**
3. Crie uma **Conta de Serviço** e baixe o arquivo JSON de credenciais
4. Compartilhe sua planilha com o e-mail da conta de serviço
5. Preencha o `secrets.toml` com as informações do JSON

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.
