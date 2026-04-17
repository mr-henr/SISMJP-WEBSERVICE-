/**
 * api.js - Cliente HTTP para comunicação com o backend FastAPI.
 * Centraliza todas as chamadas de API com tratamento de erros consistente.
 */

const API_BASE = window.location.origin;

/**
 * Retorna os headers padrão para todas as requisições.
 * Inclui o CNPJ da empresa ativa, se selecionada.
 */
function getHeaders(extra = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...extra
  };

  const cnpj = window.empresaAtivaCnpj;
  if (cnpj) {
    headers['X-Empresa-CNPJ'] = cnpj;
  }

  return headers;
}

/**
 * Wrapper genérico para fetch com tratamento de erro padronizado.
 * @param {string} endpoint - Caminho relativo (ex: '/api/empresas')
 * @param {object} options - Opções do fetch
 * @returns {Promise<any>} Dados da resposta ou objeto de erro
 */
async function apiFetch(endpoint, options = {}) {
  try {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers: getHeaders(options.headers || {})
    });

    const contentType = response.headers.get('content-type') || '';
    let data;

    if (contentType.includes('application/json')) {
      data = await response.json();
    } else {
      data = { raw: await response.text() };
    }

    if (!response.ok) {
      const mensagem = data?.detail || data?.message || `Erro HTTP ${response.status}`;
      throw new ApiError(mensagem, response.status, data);
    }

    return data;

  } catch (err) {
    if (err instanceof ApiError) throw err;
    // Erro de rede (sem conexão, CORS, etc)
    throw new ApiError(
      `Não foi possível conectar ao servidor. Verifique se o backend está rodando.`,
      0,
      null
    );
  }
}

/** Classe de erro da API com status HTTP e dados originais. */
class ApiError extends Error {
  constructor(message, status, data) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

// ─── Empresas ─────────────────────────────────────────────────────────────────

const EmpresasAPI = {
  listar: () => apiFetch('/api/empresas/'),

  criar: (dados) => apiFetch('/api/empresas/', {
    method: 'POST',
    body: JSON.stringify(dados)
  }),

  atualizar: (cnpj, dados) => apiFetch(`/api/empresas/${cnpj}`, {
    method: 'PUT',
    body: JSON.stringify(dados)
  }),

  deletar: (cnpj) => apiFetch(`/api/empresas/${cnpj}`, {
    method: 'DELETE'
  }),

  buscar: (cnpj) => apiFetch(`/api/empresas/${cnpj}`),

  uploadCertificado: async (formData) => {
    const response = await fetch(`${API_BASE}/api/empresas/upload-certificado`, {
      method: 'POST',
      body: formData
    });
    const data = await response.json();
    if (!response.ok) throw new ApiError(data?.detail || `Erro HTTP ${response.status}`, response.status, data);
    return data;
  }
};

// ─── NFS-e ────────────────────────────────────────────────────────────────────

const NfseAPI = {
  /** RecepcionarLoteRpsSincrono */
  loteSincrono: (dados) => apiFetch('/api/nfse/lote-sincrono', {
    method: 'POST',
    body: JSON.stringify(dados)
  }),

  /** RecepcionarLoteRps (assíncrono) */
  loteAssincrono: (dados) => apiFetch('/api/nfse/lote-assincrono', {
    method: 'POST',
    body: JSON.stringify(dados)
  }),

  /** ConsultarLoteRps */
  consultarLote: (dados) => apiFetch('/api/nfse/consultar-lote', {
    method: 'POST',
    body: JSON.stringify(dados)
  }),

  /** ConsultarNfsePorRps */
  consultarPorRps: (dados) => apiFetch('/api/nfse/consultar-por-rps', {
    method: 'POST',
    body: JSON.stringify(dados)
  }),

  /** ConsultarNfseFaixa */
  consultarFaixa: (dados) => apiFetch('/api/nfse/consultar-faixa', {
    method: 'POST',
    body: JSON.stringify(dados)
  }),

  /** CancelarNfse */
  cancelar: (dados) => apiFetch('/api/nfse/cancelar', {
    method: 'POST',
    body: JSON.stringify(dados)
  }),

  /** GerarNfse */
  gerar: (dados) => apiFetch('/api/nfse/gerar', {
    method: 'POST',
    body: JSON.stringify(dados)
  }),

  /** ConsultarNfseServicoPrestado (por competência) */
  consultarServicoPrestado: (dados) => apiFetch('/api/nfse/consultar-servico-prestado', {
    method: 'POST',
    body: JSON.stringify(dados)
  }),

  /** Consulta Retroativa — notas emitidas no mês selecionado com competência em meses anteriores */
  consultaRetroativa: (dados) => apiFetch('/api/nfse/consultar-retroativo', {
    method: 'POST',
    body: JSON.stringify(dados)
  }),

  /** Health check */
  health: () => apiFetch('/api/health')
};
