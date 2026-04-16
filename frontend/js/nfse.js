/**
 * nfse.js - Lógica dos formulários para as 7 operações NFS-e ABRASF 2.04.
 *
 * Cada seção corresponde a um método do WebService:
 * 1. RecepcionarLoteRpsSincrono
 * 2. RecepcionarLoteRps (assíncrono)
 * 3. ConsultarLoteRps
 * 4. ConsultarNfsePorRps
 * 5. ConsultarNfseFaixa
 * 6. CancelarNfse
 * 7. GerarNfse
 */

// ─── Helpers comuns ───────────────────────────────────────────────────────────

/** Lê dados do tomador dos campos de formulário com um prefixo de ID. */
function lerDadosTomador(prefix) {
  const cpf = getVal(`${prefix}-tomador-cpf`).replace(/\D/g, '');
  const cnpj = getVal(`${prefix}-tomador-cnpj`).replace(/\D/g, '');

  const tomador = {
    razao_social: getVal(`${prefix}-tomador-razao`),
    email: getVal(`${prefix}-tomador-email`) || undefined,
  };

  if (cnpj) tomador.cnpj = cnpj;
  else if (cpf) tomador.cpf = cpf;

  const logradouro = getVal(`${prefix}-tomador-logradouro`);
  if (logradouro) {
    tomador.endereco = {
      logradouro,
      numero: getVal(`${prefix}-tomador-numero`),
      complemento: getVal(`${prefix}-tomador-complemento`) || undefined,
      bairro: getVal(`${prefix}-tomador-bairro`),
      codigo_municipio: getVal(`${prefix}-tomador-municipio`),
      uf: getVal(`${prefix}-tomador-uf`),
      cep: getVal(`${prefix}-tomador-cep`).replace(/\D/g, ''),
    };
  }

  return tomador;
}

/** Lê dados do RPS dos campos de formulário com prefixo. */
function lerDadosRps(prefix) {
  return {
    numero: getVal(`${prefix}-rps-numero`),
    serie: getVal(`${prefix}-rps-serie`),
    tipo: getVal(`${prefix}-rps-tipo`) || '1',
    data_emissao: getVal(`${prefix}-rps-data`),
    status: '1',
    competencia: getVal(`${prefix}-rps-competencia`),
    valor_servicos: getVal(`${prefix}-rps-valor`),
    iss_retido: getVal(`${prefix}-rps-iss-retido`) || '2',
    item_lista_servico: getVal(`${prefix}-rps-item-servico`),
    codigo_cnae: getVal(`${prefix}-rps-cnae`) || undefined,
    discriminacao: getVal(`${prefix}-rps-discriminacao`),
    codigo_municipio: getVal(`${prefix}-rps-municipio`),
    exigibilidade_iss: getVal(`${prefix}-rps-exigibilidade`) || '1',
    municipio_incidencia: getVal(`${prefix}-rps-municipio-incidencia`),
    optante_simples: getVal(`${prefix}-rps-simples`) || '2',
    incentivo_fiscal: getVal(`${prefix}-rps-incentivo`) || '2',
    tomador: lerDadosTomador(prefix),
  };
}

function getVal(id) {
  return (document.getElementById(id)?.value || '').trim();
}

/** Pipeline completo: chama API, exibe resultado, trata erros. */
async function executarOperacao(apiFn, resultAreaId, btnId, loadingId) {
  if (!verificarEmpresaAtiva()) return;

  const btn = document.getElementById(btnId);
  const loading = document.getElementById(loadingId);
  setLoading(btn, loading, true);
  limparResultado(resultAreaId);

  try {
    const resultado = await apiFn();
    exibirResultado(resultAreaId, resultado, resultado.sucesso !== false);
  } catch (err) {
    exibirResultado(resultAreaId, { xml_resposta: err.message, erro: err.message }, false);
  } finally {
    setLoading(btn, loading, false);
  }
}

// ─── 1. Lote Síncrono ─────────────────────────────────────────────────────────

document.getElementById('form-lote-sincrono')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const im = getVal('ls-inscricao-municipal') || getInscricaoMunicipalAtiva();
  const dados = {
    numero_lote: getVal('ls-numero-lote'),
    inscricao_municipal: im,
    lista_rps: [lerDadosRps('ls')],
  };
  await executarOperacao(
    () => NfseAPI.loteSincrono(dados),
    'result-lote-sincrono', 'btn-lote-sincrono', 'loading-lote-sincrono'
  );
});

// ─── 2. Lote Assíncrono ───────────────────────────────────────────────────────

document.getElementById('form-lote-assincrono')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const im = getVal('la-inscricao-municipal') || getInscricaoMunicipalAtiva();
  const dados = {
    numero_lote: getVal('la-numero-lote'),
    inscricao_municipal: im,
    lista_rps: [lerDadosRps('la')],
  };
  await executarOperacao(
    () => NfseAPI.loteAssincrono(dados),
    'result-lote-assincrono', 'btn-lote-assincrono', 'loading-lote-assincrono'
  );
});

// ─── 3. Consultar Lote ────────────────────────────────────────────────────────

document.getElementById('form-consultar-lote')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const dados = {
    protocolo: getVal('cl-protocolo'),
    inscricao_municipal: getVal('cl-inscricao-municipal') || getInscricaoMunicipalAtiva(),
  };
  await executarOperacao(
    () => NfseAPI.consultarLote(dados),
    'result-consultar-lote', 'btn-consultar-lote', 'loading-consultar-lote'
  );
});

// ─── 4. Consultar por RPS ─────────────────────────────────────────────────────

document.getElementById('form-consultar-rps')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const dados = {
    numero: getVal('cr-numero'),
    serie: getVal('cr-serie'),
    tipo: getVal('cr-tipo') || '1',
    inscricao_municipal: getVal('cr-inscricao-municipal') || getInscricaoMunicipalAtiva(),
  };
  await executarOperacao(
    () => NfseAPI.consultarPorRps(dados),
    'result-consultar-rps', 'btn-consultar-rps', 'loading-consultar-rps'
  );
});

// ─── 5. Consultar por Faixa ───────────────────────────────────────────────────

document.getElementById('form-consultar-faixa')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const dados = {
    numero_inicial: getVal('cf-numero-inicial'),
    numero_final: getVal('cf-numero-final'),
    pagina: parseInt(getVal('cf-pagina') || '1', 10),
    inscricao_municipal: getVal('cf-inscricao-municipal') || getInscricaoMunicipalAtiva(),
  };
  await executarOperacao(
    () => NfseAPI.consultarFaixa(dados),
    'result-consultar-faixa', 'btn-consultar-faixa', 'loading-consultar-faixa'
  );
});

// ─── 6. Cancelar NFS-e ────────────────────────────────────────────────────────

document.getElementById('form-cancelar')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const numero = getVal('can-numero-nfse');
  if (!confirm(`Confirmar cancelamento da NFS-e nº ${numero}?\n\nEsta ação não pode ser desfeita.`)) return;

  const dados = {
    numero_nfse: numero,
    codigo_cancelamento: getVal('can-codigo-cancelamento') || '1',
    inscricao_municipal: getVal('can-inscricao-municipal') || getInscricaoMunicipalAtiva(),
    codigo_municipio: getVal('can-codigo-municipio'),
  };
  await executarOperacao(
    () => NfseAPI.cancelar(dados),
    'result-cancelar', 'btn-cancelar', 'loading-cancelar'
  );
});

// ─── 7. Gerar NFS-e ───────────────────────────────────────────────────────────

document.getElementById('form-gerar')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const im = getVal('gn-inscricao-municipal') || getInscricaoMunicipalAtiva();
  const dados = {
    inscricao_municipal: im,
    rps: lerDadosRps('gn'),
  };
  await executarOperacao(
    () => NfseAPI.gerar(dados),
    'result-gerar', 'btn-gerar', 'loading-gerar'
  );
});

// ─── Botões de Copiar/Baixar ──────────────────────────────────────────────────

document.querySelectorAll('[data-copy-from]').forEach(btn => {
  btn.addEventListener('click', () => {
    const targetId = btn.dataset.copyFrom;
    const conteudo = document.getElementById(targetId)?.textContent || '';
    copiarTexto(conteudo);
  });
});

document.querySelectorAll('[data-download-from]').forEach(btn => {
  btn.addEventListener('click', () => {
    const targetId = btn.dataset.downloadFrom;
    const conteudo = document.getElementById(targetId)?.textContent || '';
    const nome = btn.dataset.filename || 'nfse-resultado.xml';
    baixarArquivo(conteudo, nome);
  });
});

// ─── Relatório Fiscal ────────────────────────────────────────────────────────

// Guarda contexto do último resultado de competência para uso no relatório
let _relatorioAtual = null;

document.getElementById('btn-relatorio-fiscal')?.addEventListener('click', async () => {
  if (!_relatorioAtual) return;
  if (!verificarEmpresaAtiva()) return;

  const btn = document.getElementById('btn-relatorio-fiscal');
  const textoOriginal = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = `<div class="spinner" style="width:12px;height:12px;margin:0 4px 0 0;display:inline-block"></div> Gerando PDF...`;

  try {
    const response = await fetch('/api/nfse/relatorio-fiscal', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Empresa-CNPJ': window.empresaAtivaCnpj || '',
      },
      body: JSON.stringify(_relatorioAtual),
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `Erro HTTP ${response.status}`);
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const mesStr = String(_relatorioAtual.competencia_mes).padStart(2, '0');
    a.download = `relatorio-fiscal-${mesStr}-${_relatorioAtual.competencia_ano}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
    showToast('Relatório fiscal gerado com sucesso!', 'success');
  } catch (err) {
    showToast(`Erro ao gerar relatório: ${err.message}`, 'error', 6000);
  } finally {
    btn.disabled = false;
    btn.innerHTML = textoOriginal;
  }
});

// ─── Preenchimento automático de Inscrição Municipal ─────────────────────────

// Atualizar inscrição municipal quando a empresa mudar
document.getElementById('empresa-select')?.addEventListener('change', preencherInscricaoMunicipal);

// Mostrar/esconder campo de página conforme modo selecionado
document.getElementById('cc-modo')?.addEventListener('change', (e) => {
  const row = document.getElementById('cc-pagina-row');
  if (row) row.style.display = e.target.value === 'pagina' ? '' : 'none';
});

// ─── 8. Consultar por Competência ────────────────────────────────────────────

document.getElementById('form-consultar-competencia')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const ano = parseInt(getVal('cc-ano'), 10);
  const mes = parseInt(document.getElementById('cc-mes')?.value || '1', 10);
  const tipo = document.getElementById('cc-tipo')?.value || 'prestado';
  const modo = document.getElementById('cc-modo')?.value || 'todas';
  const buscarTodas = modo === 'todas';
  if (!ano || ano < 2000) {
    showToast('Informe um ano válido.', 'error');
    return;
  }
  const dados = {
    competencia_mes: mes,
    competencia_ano: ano,
    pagina: buscarTodas ? 1 : parseInt(getVal('cc-pagina') || '1', 10),
    tipo,
    buscar_todas: buscarTodas,
  };

  if (!verificarEmpresaAtiva()) return;
  const btn = document.getElementById('btn-consultar-competencia');
  const loading = document.getElementById('loading-consultar-competencia');
  setLoading(btn, loading, true);
  limparResultado('result-consultar-competencia');
  document.getElementById('cc-tabela-wrap').style.display = 'none';
  document.getElementById('cc-contador').textContent = '';
  document.getElementById('cc-tipo-badge').textContent = '';

  // Esconder botão de relatório até ter um resultado válido
  const btnRel = document.getElementById('btn-relatorio-fiscal');
  if (btnRel) btnRel.style.display = 'none';
  _relatorioAtual = null;

  try {
    const resultado = await NfseAPI.consultarServicoPrestado(dados);
    exibirResultado('result-consultar-competencia', resultado, resultado.sucesso !== false);
    if (resultado.xml_resposta) {
      _renderizarTabelaCompetencia(resultado.xml_resposta, tipo);
      // Habilitar relatório apenas se a consulta trouxe notas
      if (resultado.sucesso !== false) {
        _relatorioAtual = {
          xml_notas: resultado.xml_resposta,
          tipo,
          competencia_mes: mes,
          competencia_ano: ano,
        };
        if (btnRel) btnRel.style.display = '';
      }
    }
  } catch (err) {
    exibirResultado('result-consultar-competencia', { xml_resposta: err.message, erro: err.message }, false);
  } finally {
    setLoading(btn, loading, false);
  }
});

function _renderizarTabelaCompetencia(xmlStr, tipo = 'prestado') {
  try {
    const parser = new DOMParser();
    const doc = parser.parseFromString(xmlStr, 'application/xml');
    const notas = doc.querySelectorAll('CompNfse Nfse InfNfse, InfNfse');
    if (!notas.length) return;

    const tbody = document.getElementById('cc-tabela-body');
    const wrap = document.getElementById('cc-tabela-wrap');
    if (!tbody || !wrap) return;

    // Ajustar cabeçalho e badge conforme tipo
    const isPrestado = tipo === 'prestado';
    const col = document.getElementById('cc-col-contraparte');
    if (col) col.textContent = isPrestado ? 'Tomador' : 'Prestador';

    const badge = document.getElementById('cc-tipo-badge');
    if (badge) {
      badge.textContent = isPrestado ? 'PRESTADOR' : 'TOMADOR';
      badge.style.background = isPrestado ? 'var(--success-bg, #d1fae5)' : 'var(--info-bg, #dbeafe)';
      badge.style.color = isPrestado ? 'var(--success, #065f46)' : 'var(--info, #1e40af)';
    }

    tbody.innerHTML = '';
    let ativas = 0, canceladas = 0;

    notas.forEach(inf => {
      // Filtrar notas canceladas: Situacao=2 ou presença de NfseCancelamento
      const situacao = inf.querySelector('Situacao')?.textContent?.trim();
      const compNfse = inf.closest('CompNfse') ?? inf.parentElement?.parentElement?.parentElement;
      const estaCancelada = situacao === '2' || !!(compNfse?.querySelector('NfseCancelamento'));
      if (estaCancelada) { canceladas++; return; }
      ativas++;

      const get = (tag) => inf.querySelector(tag)?.textContent?.trim() || '—';
      const numero = get('Numero');
      const emissao = get('DataEmissao').replace('T', ' ').substring(0, 16);

      // Se prestado: mostrar tomador. Se tomado: mostrar prestador.
      let contraparte;
      if (isPrestado) {
        contraparte = inf.querySelector('TomadorServico RazaoSocial')?.textContent?.trim()
                   || inf.querySelector('Tomador RazaoSocial')?.textContent?.trim() || '—';
      } else {
        contraparte = inf.querySelector('PrestadorServico RazaoSocial')?.textContent?.trim()
                   || inf.querySelector('Prestador RazaoSocial')?.textContent?.trim() || '—';
      }

      const valorServicos = parseFloat(get('ValorServicos') || '0').toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
      const valorLiquido = parseFloat(get('ValorLiquidoNfse') || '0').toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
      const codigo = get('CodigoVerificacao');

      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${numero}</td><td>${emissao}</td><td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${contraparte}">${contraparte}</td><td>${valorServicos}</td><td>${valorLiquido}</td><td style="font-family:monospace;font-size:11px">${codigo}</td>`;
      tbody.appendChild(tr);
    });

    wrap.style.display = 'block';
    const totalBruto = ativas + canceladas;
    const canceladasInfo = canceladas > 0 ? ` (${canceladas} cancelada(s) ocultada(s))` : '';
    document.getElementById('cc-contador').textContent = `— ${ativas} nota(s) ativa(s) de ${totalBruto} total${canceladasInfo}`;
  } catch (e) {
    // silencioso: tabela é opcional, XML já está exibido
  }
}
