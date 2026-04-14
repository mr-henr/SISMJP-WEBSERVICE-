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
cd SISMJP-WEBSERVICE-
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

Com o ambiente virtual ativado, na raiz do projeto:

```bash
python main.py
```

A automação imprime o progresso no terminal e salva um log em `output/automacao_sismjp.log`.

### Testar antes de rodar em produção

Antes de processar todas as empresas, **sempre valide** a conexão com o webservice usando o script de teste mínimo. Ele consulta **uma única empresa** com data fixa e mostra em detalhe cada passo (certificado, WSDL, assinatura, envio, parsing).

```bash
# 1. Ative homologação no .env
echo "USE_HOMOLOG=true" >> .env

# 2. Exporte os dados de teste (uma empresa real com procuração ativa)
export TEST_IM=123456
export TEST_CNPJ=12345678000199
export TEST_MES=1
export TEST_ANO=2025

# Windows (PowerShell):
#   $env:TEST_IM="123456"; $env:TEST_CNPJ="12345678000199"

# 3. Rode o teste
python testar_webservice.py
```

Saída esperada (caminho feliz):

```
[1/7] Carregando certificado digital A1
   ✓ Certificado carregado: contador.pfx
[2/7] Conectando ao WSDL e inicializando cliente SOAP
   ✓ Cliente SOAP inicializado
[3/7] Operações SOAP expostas pelo serviço
     • CancelarNfse
     • ConsultarLoteRps
     • ConsultarNfseFaixa
     • ConsultarNfsePorRps
     • ConsultarNfseServicoPrestado
     • ConsultarNfseServicoTomado
     • RecepcionarLoteRps
     ✓ 7 operações disponíveis
[4/7] Montando XML ConsultarNfseServicoPrestado (01/2025)
[5/7] Assinando XML (XMLDSig RSA-SHA1)
[6/7] Enviando requisição ConsultarNfseServicoPrestado
[7/7] Parseando resposta e extraindo notas
   ✓ N nota(s) encontrada(s)
```

Códigos de saída:
| Código | Significado |
|--------|-------------|
| `0` | Sucesso (com ou sem notas no período) |
| `2` | Variáveis `TEST_IM` / `TEST_CNPJ` não definidas |
| `3` | Certificado não encontrado ou senha errada |
| `4` | Falha na conexão com WSDL (DNS, SSL ou timeout) |
| `5` | WSDL não expõe operações (corrompido) |
| `7` | Falha na assinatura XMLDSig |
| `8` | SOAP Fault na chamada |
| `9` | Resposta com erros de negócio |

---

## Checklist de validação antes de rodar em produção

Marque cada item antes do primeiro run mensal:

- [ ] `.env` preenchido com `CERT_PATH`, `CERT_PASSWORD`, `SIEG_API_KEY`, `NIBO_*`
- [ ] Certificado `.pfx` presente em `certs/` (ou caminho absoluto configurado)
- [ ] Certificado dentro da validade (verificar no gerenciador de certificados)
- [ ] Procurações eletrônicas das empresas ativas no portal da prefeitura
- [ ] Planilha `Auto_Prefeitura.xlsx` em `services/` com `PROCESSO=S` nas empresas ativas
- [ ] Célula K1 (pasta de saída) e H5 (competência MM/AAAA) preenchidas
- [ ] `python testar_webservice.py` concluiu com código `0` em homologação
- [ ] `USE_HOMOLOG=false` no `.env` para o run oficial
- [ ] Pasta de saída acessível e com espaço em disco

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

| Sintoma / Erro | Causa provável | Solução |
|----------------|----------------|---------|
| `FileNotFoundError: certs/contador.pfx` | Certificado não está na pasta | Copiar o `.pfx` para `certs/` ou ajustar `CERT_PATH` no `.env` |
| `ValueError: Falha ao carregar certificado` | Senha errada no `.env` | Verificar `CERT_PASSWORD` — senha é case-sensitive |
| `CERTIFICATE_VERIFY_FAILED` | CAs ICP-Brasil não instalados | Ver seção "Instalar os CAs da ICP-Brasil" |
| `getaddrinfo failed` / DNS | Sem internet ou servidor fora do ar | Verificar conectividade e rodar `ping receita.joaopessoa.pb.gov.br` |
| `ReadTimeout` / `ConnectionError` | Servidor lento ou instável | O sistema já retenta 3× com backoff 2s → 4s. Se persistir, tentar mais tarde |
| `FileNotFoundError: Auto_Prefeitura.xlsx` | Planilha não está na pasta | Copiar para `services/Auto_Prefeitura.xlsx` |
| `Nenhuma empresa ativa` | Coluna `PROCESSO` não tem `S` | Verificar a planilha |
| `zeep.exceptions.Fault` | Erro de protocolo SOAP | Ver `get_last_sent_xml()` para inspecionar o envelope — geralmente falta de assinatura ou campo obrigatório |
| `[E10] Nenhum registro` | Empresa sem NFS-e no período | Normal — a automação continua para a próxima empresa |
| `[E4] Assinatura inválida` | XML mal assinado | O certificado pode estar expirado ou a procuração foi revogada |
| `[E56] Procuração não encontrada` | Certificado sem procuração para a empresa | Contador precisa cadastrar a procuração eletrônica no SISMJP |
| `[E69] InscricaoMunicipal inválida` | IM errada na planilha | Verificar coluna `INSCRICAO_MUNICIPAL` — não use o `CODIGO` se forem diferentes |
| XML de resposta contém `<BODY>...</BODY>` HTML | Firewall/proxy interceptou a chamada | Verificar proxy corporativo, tentar fora da rede da empresa |

### Debug avançado

Se precisar ver o XML bruto que foi enviado / recebido durante uma falha, edite temporariamente `main.py` (ou seu script) para usar:

```python
from services.webservice_client import get_client
client = get_client()
# ... chamada que falhou ...
print(client.get_last_sent_xml())      # último envelope SOAP enviado
print(client.get_last_received_xml())  # último envelope SOAP recebido
```

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

## Endpoints do Webservice (SEREM)

Implantado em 02/06/2025 pela **Secretaria da Receita Municipal (SEREM)** de João Pessoa no padrão ABRASF 2.03.

| Ambiente | URL |
|----------|-----|
| Produção | `https://receita.joaopessoa.pb.gov.br/notafiscal-abrasfv203-ws/NotaFiscalSoap` |
| Homologação | `https://serem-hml.joaopessoa.pb.gov.br/notafiscal-abrasfv203-ws/NotaFiscalSoap` |
| WSDL (homologação) | `https://serem-hml.joaopessoa.pb.gov.br/notafiscal-abrasfv203-ws/NotaFiscalSoap?wsdl` |

Padrão: **ABRASF 2.03** · Protocolo: **SOAP** · Autenticação: **Certificado ICP-Brasil A1** · Assinatura: **XMLDSig RSA-SHA1** (obrigatória em todas as consultas)

### Operações implementadas

| Operação | Uso | Implementado |
|----------|-----|--------------|
| `ConsultarNfseServicoPrestado` | Consultar NFS-e emitidas | ✓ |
| `ConsultarNfseServicoTomado` | Consultar NFS-e recebidas | ✓ |
| `ConsultarNfseFaixa` | Consultar por faixa de número | ✓ (fallback) |
| `ConsultarNfsePorRps` | Consultar por RPS | ✓ (builder pronto) |
| `ConsultarLoteRps` | Consultar lote de RPS | ✗ (não necessário) |
| `RecepcionarLoteRps` | Emitir lote de RPS | ✗ (só consulta) |
| `CancelarNfse` | Cancelar NFS-e | ✗ (só consulta) |

> O projeto é **somente consulta** — não emite nem cancela notas. Toda a geração de NFS-e continua sendo feita pelas próprias empresas.
