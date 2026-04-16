# NFS-e JP Manager

Sistema completo para emissão, consulta e cancelamento de NFS-e para a **Prefeitura de João Pessoa** (plataforma GissOnline, padrão **ABRASF 2.04**).

Suporte multi-empresa com certificados digitais A1 independentes por empresa.

---

## Stack Tecnológica

| Componente | Tecnologia |
|---|---|
| Backend | Python 3.11+ · FastAPI · SQLAlchemy |
| Banco de dados | SQLite (substituível por PostgreSQL) |
| Certificado digital | `cryptography` (PFX/PKCS12) |
| Assinatura XML | `signxml` + `lxml` |
| Comunicação SOAP | `requests` com mTLS |
| Criptografia senhas | `cryptography.fernet` |
| Frontend | HTML5 · CSS3 · JavaScript Vanilla |

---

## Estrutura de Pastas

```
nfse-jp-manager/
├── backend/
│   ├── main.py               # Ponto de entrada FastAPI
│   ├── database.py           # Configuração SQLAlchemy + SQLite
│   ├── models.py             # Modelo ORM: Empresa
│   ├── schemas.py            # Schemas Pydantic de validação
│   ├── crypto.py             # Criptografia Fernet para senhas
│   ├── certificado.py        # Carregamento e validação do .pfx
│   ├── xml_builder.py        # Construção dos XMLs ABRASF 2.04
│   ├── xml_signer.py         # Assinatura digital XMLDSig
│   ├── soap_client.py        # Cliente SOAP/HTTPS com mTLS
│   ├── routers/
│   │   ├── empresas.py       # CRUD de empresas (API REST)
│   │   └── nfse.py           # 7 operações NFS-e (API REST)
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── index.html            # SPA principal
│   ├── css/style.css         # Estilos
│   └── js/
│       ├── api.js            # Cliente HTTP
│       ├── app.js            # Navegação e utilitários
│       ├── empresas.js       # Gerenciamento de empresas
│       └── nfse.js           # Formulários das 7 operações
└── README.md
```

---

## Instalação e Configuração

### Pré-requisitos

- Python 3.11 ou superior
- pip
- Certificado digital A1 no formato `.pfx` (`.p12`)

### 1. Clonar / Descompactar o projeto

```bash
cd nfse-jp-manager
```

### 2. Criar ambiente virtual Python

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 3. Instalar dependências

```bash
cd backend
pip install -r requirements.txt
```

> **Nota Windows:** Se houver erro ao instalar `lxml` ou `cryptography`, certifique-se de ter o Microsoft C++ Build Tools instalado, ou use: `pip install --only-binary=:all: -r requirements.txt`

### 4. Configurar variáveis de ambiente

```bash
# Copiar o arquivo de exemplo
cp .env.example .env
```

Editar `.env`:

```env
# Ambiente de execução
AMBIENTE=homologacao   # ou: producao

# Gerar a SECRET_KEY com o comando abaixo e colar aqui
SECRET_KEY=sua-chave-fernet-aqui
```

**Gerar a SECRET_KEY:**

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Cole o resultado no campo `SECRET_KEY` do `.env`.

> **IMPORTANTE:** Guarde a `SECRET_KEY` em local seguro. Se perdida, as senhas dos certificados no banco **não poderão ser recuperadas** e precisarão ser recadastradas.

### 5. Iniciar o servidor

```bash
# Dentro do diretório backend/
python main.py
```

O servidor iniciará em `http://localhost:8080`.

Acesse a interface em: **http://localhost:8080**

A documentação automática da API está em: **http://localhost:8080/api/docs**

---

## Operações implementadas

| # | Método WebService | Descrição |
|---|---|---|
| 1 | `RecepcionarLoteRpsSincrono` | Envia lote e aguarda NFS-e imediatamente |
| 2 | `RecepcionarLoteRps` | Envia para fila, retorna protocolo |
| 3 | `ConsultarLoteRps` | Consulta lote pelo protocolo |
| 4 | `ConsultarNfsePorRps` | Busca NFS-e pelo RPS de origem |
| 5 | `ConsultarNfseFaixa` | Lista NFS-e por faixa de número |
| 6 | `CancelarNfse` | Cancela NFS-e existente |
| 7 | `GerarNfse` | Emissão direta (sem lote) |

---

## Como Cadastrar uma Empresa

1. Clique no botão **+** ao lado do seletor de empresa no cabeçalho.
2. Preencha:
   - **CNPJ**: apenas números (14 dígitos)
   - **Razão Social**: nome completo da empresa
   - **Inscrição Municipal**: código na prefeitura de João Pessoa
   - **Caminho do Certificado**: caminho absoluto do arquivo `.pfx` no servidor (ex: `C:\certificados\empresa.pfx`)
   - **Senha do Certificado**: senha do arquivo `.pfx`
3. Clique em **Salvar**.

A senha é criptografada com Fernet antes de ser gravada no banco de dados.

---

## Certificados Digitais A1

### Onde colocar o arquivo .pfx

O arquivo `.pfx` deve estar acessível **no servidor onde o backend roda**. Recomenda-se criar uma pasta dedicada:

```
C:\certificados\
    empresa1.pfx
    empresa2.pfx
```

### Tipo de certificado suportado

- Certificado **e-CNPJ A1** ou **e-CPF A1** (RSA)
- Arquivos `.pfx` ou `.p12`
- Emitidos por qualquer AC credenciada pela ICP-Brasil
- **Não** suporta certificados A3 (tokens/smartcards) diretamente — necessitaria de adaptação

---

## Segurança

- As senhas dos certificados são **sempre criptografadas** com `cryptography.fernet` antes do armazenamento.
- A `SECRET_KEY` deve ser mantida em segredo. Use variáveis de ambiente ou cofres de segredo.
- Os arquivos temporários de PEM são criados e deletados imediatamente após cada chamada SOAP.
- Em produção, restrinja `CORS_ORIGINS` para o domínio real da aplicação.
- Use HTTPS para servir a aplicação em produção (nginx + Let's Encrypt ou certificado corporativo).

---

## Troubleshooting

| Problema | Solução |
|---|---|
| `SECRET_KEY não configurada` | Copie `.env.example` para `.env` e gere uma chave Fernet |
| `Arquivo .pfx não encontrado` | Verifique o caminho absoluto cadastrado. No Windows, use barras duplas: `C:\\certs\\empresa.pfx` |
| `Não foi possível abrir o certificado` | Senha incorreta ou arquivo corrompido |
| `Certificado expirado` | Renove o certificado A1 junto à AC emissora |
| `Timeout 60s` | WebService lento ou indisponível. Verifique conexão com a internet e status do serviço |
| `Erro SSL` | O certificado pode não ser aceito pelo servidor. Verifique se é um certificado RSA válido ICP-Brasil |
| `Backend não disponível` | Execute `python main.py` no diretório `backend/` |

---

## Migração para PostgreSQL

Quando quiser migrar de SQLite para PostgreSQL, altere no `.env`:

```env
DATABASE_URL=postgresql://usuario:senha@localhost:5432/nfse_jp
```

E instale o driver:

```bash
pip install psycopg2-binary
```

---

## Código IBGE de João Pessoa

Para o campo **Código do Município**: `2507507`

---

## Licença

Uso interno — escritório de contabilidade.
