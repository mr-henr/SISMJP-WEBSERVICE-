# SISMJP — Automação via Webservice ABRASF 2.03
### Prefeitura de João Pessoa - PB

Automação para captura de NFS-e (Notas Fiscais de Serviço Eletrônicas) da Prefeitura de João Pessoa via webservice SOAP padrão ABRASF 2.03. Substitui a antiga automação com Playwright (browser).

---

## Como funciona

Para cada empresa na planilha, a automação:

1. Consulta NFS-e **emitidas** (Serviço Prestado) via webservice
2. Consulta NFS-e **recebidas** (Serviço Tomado) via webservice
3. Gera **Livro Fiscal Prestador** em Excel (substitui o PDF da prefeitura)
4. Gera **Livro Fiscal Tomador** em Excel (substitui o PDF da prefeitura)
5. Salva os **XMLs** das notas em disco
6. Realiza **consulta retroativa** dos 6 meses anteriores
7. Faz upload de tudo para o **SIEG** (manifesto SHA256 evita reenvio)
8. Faz upload de tudo para o **NIBO**

> **Certificado:** Um único certificado A1 do **contador** (com procuração eletrônica das empresas) é suficiente. Não é necessário certificado individual de cada empresa.

---

## Pré-requisitos

- **Python 3.11+** instalado
- **Certificado digital A1** do contador em formato `.pfx` ou `.p12`
  - O certificado deve ter a procuração eletrônica das empresas cadastrada na prefeitura de João Pessoa
- **Planilha** `Auto_Prefeitura.xlsx` preenchida (ver seção abaixo)
- Acesso à internet (para chamar o webservice e APIs SIEG/NIBO)

---

## Instalação passo a passo

### 1. Clonar o repositório

```bash
git clone <url-do-repositorio>
cd SISMJP-WEBSERVICE-/sismjp-webservice
```

### 2. Criar e ativar ambiente virtual Python

**Windows (CMD ou PowerShell):**
```bash
python -m venv .venv
.venv\Scripts\activate
```

**Linux/Mac:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Instalar dependências

```bash
pip install -r requirements.txt
```

### 4. Copiar e preencher o arquivo de configuração

```bash
copy .env.example .env        # Windows
cp .env.example .env          # Linux/Mac
```

Abra o arquivo `.env` em qualquer editor de texto e preencha os valores:

```env
# Caminho para o .pfx do contador (relativo à pasta sismjp-webservice/)
CERT_PATH=certs/contador.pfx
CERT_PASSWORD=senha_do_seu_certificado

# "true" para testar no ambiente de homologação, "false" para produção
USE_HOMOLOG=false

# Pasta onde os arquivos serão salvos (relativo ou absoluto)
# Relativo: output  →  salva em sismjp-webservice/output/
# Absoluto: Z:/Contattus/Automacao/Prefeitura
OUTPUT_BASE_PATH=output

# Chave da API do SIEG (cofre fiscal)
SIEG_API_KEY=sua_chave_sieg

# Credenciais do NIBO (sistema contábil)
NIBO_API_KEY=sua_chave_nibo
NIBO_ACCOUNTING_FIRM_ID=id_da_firma
NIBO_USER_ID=seu_user_id
```

> **Nota:** O arquivo `.env` nunca é commitado no repositório (está no `.gitignore`). Ele existe apenas localmente na sua máquina.

### 5. Adicionar o certificado digital

Coloque o arquivo `.pfx` do contador dentro da pasta `certs/`:

```
sismjp-webservice/
└── certs/
    └── contador.pfx     ← coloque aqui
```

> O arquivo de certificado **nunca é commitado** no repositório (está no `.gitignore` por segurança). Você deve adicioná-lo manualmente em cada máquina onde rodar a automação.

Se preferir guardar o certificado em outro lugar (ex: pasta do Windows ou drive de rede), use o caminho completo no `.env`:

```env
CERT_PATH=C:/Users/SeuUsuario/certificados/contador.pfx
```

### 6. Instalar os CAs da ICP-Brasil (se necessário)

O webservice da prefeitura usa um certificado SSL assinado pela cadeia ICP-Brasil. Se ao rodar aparecer erro de SSL (`CERTIFICATE_VERIFY_FAILED`), você precisa instalar os certificados raiz da ICP-Brasil.

**Opção A — Instalar no Windows:**
1. Baixe a cadeia em: https://www.iti.gov.br/icp-brasil/certificados
2. Instale os certificados raiz (`AC Raiz`) no repositório "Autoridades de Certificação Raiz Confiáveis" do Windows

**Opção B — Apontar o bundle manualmente:**
Baixe o arquivo PEM com a cadeia ICP-Brasil e adicione ao `.env`:
```env
# Caminho relativo ao sismjp-webservice/
SSL_CA_BUNDLE=certs/icp-brasil-chain.pem
```
E em `config/settings.py`, adicione `session.verify = SSL_CA_BUNDLE` (ou altere a linha `session.verify = True` em `utils/cert_utils.py`).

---

## Configurar a planilha Auto_Prefeitura.xlsx

A planilha deve estar em `sismjp-webservice/services/Auto_Prefeitura.xlsx`.

### Colunas obrigatórias (aba principal)

| Coluna | O que colocar |
|--------|---------------|
| `PROCESSO` | `S` para empresa ativa, qualquer outro valor para ignorar |
| `CODIGO` | Código da empresa (usado como InscricaoMunicipal se não houver coluna IM) |
| `CLIENTE` | Nome da empresa |
| `CNPJ / CPF` | CNPJ (14 dígitos) ou CPF (11 dígitos) da empresa |
| `INSCRICAO_MUNICIPAL` | *(nova, opcional)* Inscrição Municipal no SISMJP — se vazio, usa `CODIGO` |

### Células de configuração (posições fixas)

| Posição | O que colocar | Exemplo |
|---------|---------------|---------|
| Linha 1, Coluna 11 (K1) | Pasta raiz de saída | `Z:\Contattus\Automacao\Prefeitura` |
| Linha 5, Coluna 8 (H5) | Competência de referência | `04/2025` (MM/AAAA) |

> **Dica sobre INSCRICAO_MUNICIPAL:** Se o `CODIGO` já é a Inscrição Municipal da empresa no SISMJP, não precisa adicionar a coluna nova. A automação usa `CODIGO` como fallback automaticamente.

---

## Executar a automação

Com o ambiente virtual ativado, na pasta `sismjp-webservice/`:

```bash
python main.py
```

A automação vai imprimir o progresso no terminal e salvar um log em `output/automacao_sismjp.log`.

### Testar antes de rodar em produção

Para testar sem dados reais, ative o ambiente de homologação no `.env`:

```env
USE_HOMOLOG=true
```

---

## Estrutura de arquivos gerados

Após a execução, os arquivos ficam organizados assim dentro de `OUTPUT_BASE_PATH`:

```
output/                                     (ou pasta configurada no .env)
├── Prestador/
│   └── {codigo}-{nome}/
│       └── {MMAAAA}/
│           ├── XML_Emitidas-{codigo}-{nome}.xml    ← notas emitidas
│           └── {codigo}-{nome}.xlsx                 ← Livro Fiscal Prestador
├── Tomador/
│   └── {codigo}-{nome}/
│       └── {MMAAAA}/
│           ├── XML_Recebidas-{codigo}-{nome}.xml   ← notas recebidas
│           └── {codigo}-{nome}.xlsx                 ← Livro Fiscal Tomador
├── Consulta Retroativa/
│   └── {codigo}-{nome}/
│       └── {MMAAAA}/                               ← um por cada mês retroativo
│           ├── XML_Emitidas-{codigo}-{nome}.xml
│           └── XML_Recebidas-{codigo}-{nome}.xml
├── .sieg_upload_manifest.json                       ← controle de uploads SIEG
└── automacao_sismjp.log                             ← log de execução
```

---

## Estrutura do projeto

```
sismjp-webservice/
├── main.py                          # Ponto de entrada — orquestração geral
├── requirements.txt                 # Dependências Python
├── .env.example                     # Template de configuração (copiar para .env)
├── .env                             # ← VOCÊ CRIA — não commitado
├── .gitignore
│
├── certs/
│   └── contador.pfx                 # ← VOCÊ COLOCA — não commitado
│
├── services/
│   ├── Auto_Prefeitura.xlsx         # ← VOCÊ COLOCA — planilha de empresas
│   ├── webservice_client.py         # Cliente SOAP (zeep + certificado)
│   ├── nfse_service.py              # Consulta NFSe Prestado/Tomado + retroativa
│   ├── fiscal_book_service.py       # Gera Livro Fiscal Excel
│   ├── info_service.py              # Lê a planilha de empresas
│   ├── sieg_service.py              # Upload para o SIEG
│   ├── nibo_service.py              # Upload para o NIBO
│   └── logging_service.py           # Log de execução
│
├── models/
│   └── nfse_model.py                # Dataclass NfseData (campos da NFS-e)
│
├── utils/
│   ├── cert_utils.py                # Carrega .pfx e configura mTLS
│   ├── xml_utils.py                 # Monta e faz parse de XML ABRASF 2.03
│   └── file_utils.py                # Salva arquivos em disco
│
├── config/
│   └── settings.py                  # Configurações centralizadas
│
└── output/                          # Criado automaticamente ao rodar
```

---

## Solução de problemas comuns

| Erro | Causa provável | Solução |
|------|---------------|---------|
| `FileNotFoundError: certs/contador.pfx` | Certificado não está na pasta | Copiar o `.pfx` para `sismjp-webservice/certs/` |
| `ValueError: Falha ao carregar certificado` | Senha errada no `.env` | Verificar `CERT_PASSWORD` |
| `CERTIFICATE_VERIFY_FAILED` | CAs ICP-Brasil não instalados | Ver seção "Instalar os CAs da ICP-Brasil" |
| `FileNotFoundError: Auto_Prefeitura.xlsx` | Planilha não está na pasta | Copiar para `sismjp-webservice/services/` |
| `Nenhuma empresa ativa` | Coluna `PROCESSO` não tem `S` | Verificar a planilha |
| `zeep.exceptions.Fault` | Erro de protocolo SOAP | Verificar se `USE_HOMOLOG` está correto e se o certificado tem procuração |
| `[E10] Nenhum registro` | Empresa sem NFS-e no período | Normal — a automação continua para a próxima empresa |

---

## Dependências e seus papéis

| Pacote | Para que serve |
|--------|---------------|
| `zeep` | Cliente SOAP — faz as chamadas ao webservice da prefeitura |
| `lxml` | Monta e faz parse dos XMLs ABRASF 2.03 |
| `cryptography` | Carrega o certificado `.pfx` (ICP-Brasil A1) |
| `pyOpenSSL` | Suporte SSL para autenticação mútua (mTLS) |
| `requests` | HTTP para SIEG e NIBO |
| `pandas` | Lê a planilha `Auto_Prefeitura.xlsx` |
| `openpyxl` | Gera o Livro Fiscal em Excel |
| `python-dotenv` | Carrega o arquivo `.env` |

---

## Endpoints do Webservice

| Ambiente | URL |
|----------|-----|
| Produção | `https://sispmjp.joaopessoa.pb.gov.br:8443/sispmjp/NfseWSService` |
| Homologação | `https://nfsehomolog.joaopessoa.pb.gov.br:8443/sispmjp/NfseWSService` |
| WSDL (produção) | `https://sispmjp.joaopessoa.pb.gov.br:8443/sispmjp/NfseWSService?wsdl` |

Padrão: **ABRASF 2.03** · Protocolo: **SOAP** · Autenticação: **Certificado ICP-Brasil A1**
