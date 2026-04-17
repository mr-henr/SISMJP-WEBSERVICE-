/**
 * app.js - Lógica principal da SPA: navegação, empresa ativa, utilitários.
 */

// ─── Estado Global ────────────────────────────────────────────────────────────

window.empresaAtivaCnpj = null;
window.empresas = [];

// ─── Inicialização ────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
  // Pré-preencher ano e mês atual nos formulários de automação e competência
  const hoje = new Date();
  const anoAtual = hoje.getFullYear();
  const mesAtual = hoje.getMonth() + 1;
  ['auto-ano'].forEach(id => {
    const el = document.getElementById(id);
    if (el && !el.value) el.value = anoAtual;
  });
  ['auto-mes'].forEach(id => {
    const el = document.getElementById(id);
    if (el && !el.value) el.value = mesAtual;
  });

  await carregarAmbiente();
  await carregarEmpresas();
  inicializarNavegacao();
  navigate('automacao');
});

async function carregarAmbiente() {
  try {
    const health = await NfseAPI.health();
    const badge = document.getElementById('ambiente-badge');
    if (badge) {
      badge.textContent = health.ambiente === 'producao' ? '🟢 Produção' : '🟡 Homologação';
      badge.className = `ambiente-badge ${health.ambiente}`;
    }
    if (!health.secret_key_configurada) {
      showToast('SECRET_KEY não configurada no .env! Configure antes de usar.', 'error', 8000);
    }
  } catch (e) {
    showToast('Backend não disponível. Verifique se o servidor está rodando.', 'error', 8000);
  }
}

// ─── Seletor de Empresa ───────────────────────────────────────────────────────

async function carregarEmpresas() {
  try {
    window.empresas = await EmpresasAPI.listar();
    preencherSeletorEmpresa();
    preencherInscricaoMunicipal();
    renderizarTabelaEmpresas();
    atualizarDashboard();
    document.dispatchEvent(new Event('empresas-carregadas'));
  } catch (e) {
    console.error('Erro ao carregar empresas:', e);
  }
}

function preencherSeletorEmpresa() {
  const select = document.getElementById('empresa-select');
  if (!select) return;

  const valorAtual = select.value;
  select.innerHTML = '<option value="">— Selecione a empresa —</option>';

  window.empresas.forEach(emp => {
    const opt = document.createElement('option');
    opt.value = emp.cnpj;
    opt.textContent = emp.razao_social;
    select.appendChild(opt);
  });

  // Restaurar seleção anterior ou selecionar a primeira
  if (valorAtual && window.empresas.find(e => e.cnpj === valorAtual)) {
    select.value = valorAtual;
    window.empresaAtivaCnpj = valorAtual;
  } else if (window.empresas.length > 0) {
    select.value = window.empresas[0].cnpj;
    window.empresaAtivaCnpj = window.empresas[0].cnpj;
  }
}

document.getElementById('empresa-select')?.addEventListener('change', (e) => {
  window.empresaAtivaCnpj = e.target.value || null;
  const nome = e.target.options[e.target.selectedIndex]?.text;
  if (window.empresaAtivaCnpj) {
    showToast(`Empresa ativa: ${nome}`, 'info', 2500);
  }
});

// ─── Navegação ────────────────────────────────────────────────────────────────

function inicializarNavegacao() {
  document.querySelectorAll('.nav-item[data-page]').forEach(item => {
    item.addEventListener('click', () => navigate(item.dataset.page));
  });
}

function navigate(pageId) {
  // Desativar todas as páginas e itens de nav
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

  // Ativar página e nav item
  const page = document.getElementById(`page-${pageId}`);
  if (page) page.classList.add('active');

  const navItem = document.querySelector(`.nav-item[data-page="${pageId}"]`);
  if (navItem) navItem.classList.add('active');
}

// ─── Dashboard ────────────────────────────────────────────────────────────────

function atualizarDashboard() {
  const elTotal = document.getElementById('stat-empresas');
  if (elTotal) elTotal.textContent = window.empresas.length;
  const elAtivas = document.getElementById('stat-ativas');
  if (elAtivas) elAtivas.textContent = window.empresas.filter(e => e.ativo_automacao !== false).length;
}

// ─── Funções de UI: Toast ─────────────────────────────────────────────────────

/**
 * Exibe uma notificação toast temporária.
 * @param {string} msg - Mensagem a exibir
 * @param {'success'|'error'|'info'} type - Tipo visual
 * @param {number} duration - Duração em ms (padrão 3500)
 */
function showToast(msg, type = 'info', duration = 3500) {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const icons = {
    success: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 6L9 17l-5-5"/></svg>`,
    error: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`,
    info: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`
  };

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `${icons[type] || ''}<span>${msg}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(20px)';
    toast.style.transition = '0.25s ease';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

// ─── Funções de UI: Loading ───────────────────────────────────────────────────

function setLoading(btnEl, overlayEl, isLoading) {
  if (btnEl) {
    btnEl.disabled = isLoading;
    if (isLoading) {
      btnEl.dataset.originalText = btnEl.innerHTML;
      btnEl.innerHTML = `<div class="spinner" style="width:14px;height:14px;margin:0"></div> Enviando...`;
    } else if (btnEl.dataset.originalText) {
      btnEl.innerHTML = btnEl.dataset.originalText;
    }
  }
  if (overlayEl) {
    overlayEl.classList.toggle('visible', isLoading);
  }
}

// ─── Funções de UI: Resultado ─────────────────────────────────────────────────

/**
 * Detecta se o XML de resposta contém mensagens de erro de negócio
 * (ListaMensagemRetorno com erros, sem ListaNfse/CompNfse).
 * Retorna { temErro: bool, mensagens: [{codigo, texto}] }
 */
function analisarRespostaXml(xmlStr) {
  if (!xmlStr || typeof xmlStr !== 'string') return { temErro: false, mensagens: [] };
  try {
    const parser = new DOMParser();
    const doc = parser.parseFromString(xmlStr, 'application/xml');
    const erroParser = doc.querySelector('parsererror');
    if (erroParser) return { temErro: false, mensagens: [] };

    const msgs = doc.querySelectorAll('MensagemRetorno');
    const mensagens = Array.from(msgs).map(m => ({
      codigo: m.querySelector('Codigo')?.textContent?.trim() || '',
      texto: m.querySelector('Mensagem')?.textContent?.trim() || '',
    }));

    // Considera erro de negócio se há mensagens e não há notas na resposta
    const temNfse = doc.querySelector('CompNfse, Nfse, ListaNfse') !== null;
    const temErro = mensagens.length > 0 && !temNfse;

    return { temErro, mensagens };
  } catch (e) {
    return { temErro: false, mensagens: [] };
  }
}

/**
 * Exibe o resultado de uma operação NFS-e.
 * @param {string} resultAreaId - ID do elemento .result-area
 * @param {object} resultado - Resposta do backend
 * @param {boolean} sucesso - Se a operação foi bem-sucedida (nível HTTP)
 */
function exibirResultado(resultAreaId, resultado, sucesso) {
  const area = document.getElementById(resultAreaId);
  if (!area) return;

  area.classList.add('visible');

  const conteudo = resultado?.xml_resposta || resultado?.raw || JSON.stringify(resultado, null, 2);

  const xmlBox = area.querySelector('.xml-result-content');
  if (xmlBox) {
    xmlBox.textContent = formatarXml(conteudo);
  }

  // Verificar erros de negócio no XML mesmo quando HTTP foi 200
  const { temErro, mensagens } = sucesso ? analisarRespostaXml(conteudo) : { temErro: true, mensagens: [] };
  const sucessoReal = sucesso && !temErro;

  const statusBadge = area.querySelector('.result-status');
  if (statusBadge) {
    statusBadge.className = `badge ${sucessoReal ? 'badge-success' : 'badge-error'}`;
    statusBadge.textContent = sucessoReal ? '✓ Sucesso' : '✗ Erro';
  }

  const xmlEnviadoBox = area.querySelector('.xml-enviado-content');
  if (xmlEnviadoBox && resultado?.xml_enviado) {
    xmlEnviadoBox.textContent = formatarXml(resultado.xml_enviado);
  }

  // Scroll suave até o resultado
  area.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

  if (sucessoReal) {
    showToast('Operação realizada com sucesso!', 'success');
  } else if (temErro && mensagens.length > 0) {
    const resumo = mensagens.map(m => `${m.codigo}: ${m.texto}`).join(' | ');
    showToast(`Erro da prefeitura: ${resumo}`, 'error', 6000);
  } else {
    showToast(resultado?.erro || 'Operação retornou erro. Veja o XML de resposta.', 'error');
  }
}

function limparResultado(resultAreaId) {
  const area = document.getElementById(resultAreaId);
  if (!area) return;
  area.classList.remove('visible');
  area.querySelectorAll('pre').forEach(p => p.textContent = '');
}

// ─── Formatação e utilitários ─────────────────────────────────────────────────

/** Formata XML adicionando indentação para melhor legibilidade. */
function formatarXml(xmlStr) {
  if (!xmlStr || typeof xmlStr !== 'string') return String(xmlStr);
  try {
    let formatted = '';
    let indent = 0;
    const lines = xmlStr
      .replace(/></g, '>\n<')
      .replace(/>\s*\n\s*</g, '>\n<')
      .split('\n');

    lines.forEach(line => {
      line = line.trim();
      if (!line) return;
      if (line.match(/^<\/\w/)) indent--;
      formatted += '  '.repeat(Math.max(0, indent)) + line + '\n';
      if (line.match(/^<\w[^/]*[^/]>$/) && !line.match(/^<\?/)) indent++;
    });
    return formatted.trim();
  } catch (e) {
    return xmlStr;
  }
}

/** Copia texto para clipboard e exibe feedback. */
function copiarTexto(texto) {
  navigator.clipboard.writeText(texto).then(() => {
    showToast('Copiado para a área de transferência!', 'success', 2000);
  }).catch(() => {
    showToast('Não foi possível copiar.', 'error', 2000);
  });
}

/** Faz download de um conteúdo como arquivo. */
function baixarArquivo(conteudo, nomeArquivo, tipo = 'application/xml') {
  const blob = new Blob([conteudo], { type: tipo });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = nomeArquivo;
  a.click();
  URL.revokeObjectURL(url);
}

/** Formata CNPJ: 00.000.000/0000-00 */
function formatarCnpj(cnpj) {
  const n = cnpj.replace(/\D/g, '');
  return n.replace(/(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})/, '$1.$2.$3/$4-$5');
}

/** Verifica se empresa ativa está selecionada, mostra erro se não. */
function verificarEmpresaAtiva() {
  if (!window.empresaAtivaCnpj) {
    showToast('Selecione uma empresa no topo da tela antes de continuar.', 'error');
    return false;
  }
  return true;
}

/** Obtém inscrição municipal da empresa ativa. */
function getInscricaoMunicipalAtiva() {
  const emp = window.empresas.find(e => e.cnpj === window.empresaAtivaCnpj);
  return emp?.inscricao_municipal || '';
}

function preencherInscricaoMunicipal() {
  const im = getInscricaoMunicipalAtiva();
  const campos = [
    'ls-inscricao-municipal', 'la-inscricao-municipal',
    'cl-inscricao-municipal', 'cr-inscricao-municipal',
    'cf-inscricao-municipal', 'can-inscricao-municipal',
    'gn-inscricao-municipal'
  ];
  campos.forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    if (im) {
      el.value = im;
      el.readOnly = true;
      el.style.background = 'var(--bg)';
      el.style.color = 'var(--text-muted)';
      el.style.cursor = 'default';
    } else {
      el.readOnly = false;
      el.style.background = '';
      el.style.color = '';
      el.style.cursor = '';
    }
  });
}
