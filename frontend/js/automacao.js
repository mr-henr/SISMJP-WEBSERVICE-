/**
 * automacao.js - Lógica da página de Automação de Coleta NFS-e.
 */

// ─── Renderização da lista de empresas ───────────────────────────────────────

function renderizarListaEmpresasAutomacao() {
  const lista = document.getElementById('auto-empresas-lista');
  if (!lista) return;

  if (!window.empresas || window.empresas.length === 0) {
    lista.innerHTML = '<div style="color:var(--text-muted);font-size:13px;padding:12px 0">Nenhuma empresa cadastrada. Acesse "Empresas" para cadastrar.</div>';
    return;
  }

  lista.innerHTML = window.empresas.map(emp => {
    const label = emp.codigo
      ? `<code style="font-size:11px;color:var(--text-muted);margin-right:6px">${escapeHtml(emp.codigo)}</code>${escapeHtml(emp.razao_social)}`
      : escapeHtml(emp.razao_social);
    return `
      <label style="display:flex;align-items:center;gap:10px;padding:8px 12px;border:1px solid var(--border);border-radius:6px;cursor:pointer;background:var(--bg-card)">
        <input type="checkbox" name="auto-empresa" value="${emp.cnpj}"
          ${emp.ativo_automacao !== false ? 'checked' : ''}
          style="width:15px;height:15px;cursor:pointer;flex-shrink:0">
        <span style="font-size:13px;flex:1">${label}</span>
        <span style="font-size:11px;color:var(--text-muted);font-family:monospace">${formatarCnpj(emp.cnpj)}</span>
      </label>`;
  }).join('');
}

function toggleTodasEmpresas(marcar) {
  document.querySelectorAll('input[name="auto-empresa"]').forEach(cb => { cb.checked = marcar; });
}

// Atualizar lista toda vez que as empresas forem recarregadas
const _carregarEmpresasOriginal = typeof carregarEmpresas === 'function' ? carregarEmpresas : null;

// Hook: re-renderiza lista ao carregar empresas (via MutationObserver na lista)
document.addEventListener('empresas-carregadas', renderizarListaEmpresasAutomacao);

// Preencher ao navegar para a página de automação
document.querySelectorAll('.nav-item[data-page="automacao"]').forEach(item => {
  item.addEventListener('click', renderizarListaEmpresasAutomacao);
});

// ─── Formulário de Automação ─────────────────────────────────────────────────

document.getElementById('form-automacao')?.addEventListener('submit', async (e) => {
  e.preventDefault();

  const mes = parseInt(document.getElementById('auto-mes')?.value || '1', 10);
  const ano = parseInt(document.getElementById('auto-ano')?.value || '0', 10);

  if (!ano || ano < 2000) {
    showToast('Informe um ano válido.', 'error');
    return;
  }

  const cnpjsSelecionados = Array.from(
    document.querySelectorAll('input[name="auto-empresa"]:checked')
  ).map(cb => cb.value);

  if (cnpjsSelecionados.length === 0) {
    showToast('Selecione ao menos uma empresa para processar.', 'error');
    return;
  }

  const btn = document.getElementById('btn-executar-automacao');
  const loading = document.getElementById('loading-automacao');
  const resultado = document.getElementById('auto-resultado');

  // Ocultar resultado anterior
  resultado.style.display = 'none';
  document.getElementById('auto-download-link').style.display = 'none';
  document.getElementById('auto-erros-wrap').style.display = 'none';

  // Mostrar loading
  if (btn) {
    btn.disabled = true;
    btn.dataset.originalText = btn.innerHTML;
    btn.innerHTML = '<div class="spinner" style="width:14px;height:14px;margin:0"></div> Processando...';
  }
  if (loading) loading.classList.add('visible');

  const MESES_PT = ['', 'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
                    'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'];

  try {
    const { blob, filename } = await AutomacaoAPI.executar({
      competencia_mes: mes,
      competencia_ano: ano,
      cnpjs: cnpjsSelecionados,
    });

    // Criar URL para download
    const url = URL.createObjectURL(blob);
    const link = document.getElementById('auto-download-link');
    link.href = url;
    link.download = filename;
    link.style.display = 'inline-block';

    document.getElementById('auto-status-badge').className = 'badge badge-success';
    document.getElementById('auto-status-badge').textContent = 'Concluído';
    document.getElementById('auto-resumo').textContent =
      `Processadas ${cnpjsSelecionados.length} empresa(s) — competência ${MESES_PT[mes]}/${ano}. Arquivo: ${filename}`;

    resultado.style.display = '';
    resultado.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    showToast('Automação concluída! Clique em "Baixar ZIP" para salvar.', 'success', 5000);

    // Verificar se há arquivo ERROS.txt no zip (heurística: tamanho pequeno = possível erro)
    // Não conseguimos inspecionar o ZIP no browser sem lib, então apenas mostramos o tamanho
    const kb = (blob.size / 1024).toFixed(1);
    document.getElementById('auto-resumo').textContent +=
      ` (${kb} KB)`;

  } catch (err) {
    document.getElementById('auto-status-badge').className = 'badge badge-error';
    document.getElementById('auto-status-badge').textContent = 'Erro';
    document.getElementById('auto-resumo').textContent = err.message;
    document.getElementById('auto-erros-wrap').style.display = '';
    document.getElementById('auto-erros').textContent = err.message;
    resultado.style.display = '';
    showToast(err.message, 'error', 6000);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = btn.dataset.originalText || 'Executar Automação';
    }
    if (loading) loading.classList.remove('visible');
  }
});
