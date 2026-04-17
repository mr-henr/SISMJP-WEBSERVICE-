/**
 * empresas.js - Gerenciamento de empresas: listagem, cadastro, edição e remoção.
 */

// ─── Tabela de Empresas ───────────────────────────────────────────────────────

function renderizarTabelaEmpresas() {
  const tbody = document.getElementById('empresas-tbody');
  if (!tbody) return;

  if (!window.empresas || window.empresas.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="5">
          <div class="empty-state">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16M3 21h18M9 7h1M9 11h1M9 15h1M14 7h1M14 11h1M14 15h1"/>
            </svg>
            <h3>Nenhuma empresa cadastrada</h3>
            <p>Clique em "Nova Empresa" para cadastrar uma empresa com seu certificado A1.</p>
          </div>
        </td>
      </tr>`;
    return;
  }

  tbody.innerHTML = window.empresas.map(emp => `
    <tr>
      <td class="cnpj-cell">${formatarCnpj(emp.cnpj)}</td>
      <td><strong>${escapeHtml(emp.razao_social)}</strong></td>
      <td>${escapeHtml(emp.inscricao_municipal || '—')}</td>
      <td>
        <span title="${escapeHtml(emp.caminho_certificado)}" style="font-family:monospace;font-size:11px;color:var(--text-muted)">
          ${escapeHtml(truncarTexto(emp.caminho_certificado, 40))}
        </span>
      </td>
      <td class="actions-cell">
        <button class="btn btn-sm btn-secondary" onclick="abrirModalEdicao('${emp.cnpj}')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
          Editar
        </button>
        <button class="btn btn-sm btn-danger" onclick="confirmarDelecao('${emp.cnpj}', '${escapeHtml(emp.razao_social)}')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/><path d="M10 11v6M14 11v6"/></svg>
          Excluir
        </button>
      </td>
    </tr>
  `).join('');
}

// ─── Modal Nova Empresa ───────────────────────────────────────────────────────

function selecionarCertificado() {
  document.getElementById('campo-cert-file').click();
}

document.getElementById('campo-cert-file')?.addEventListener('change', async (e) => {
  const file = e.target.files[0];
  if (!file) return;

  const nomeEl = document.getElementById('cert-nome');
  const btn = document.getElementById('btn-selecionar-cert');

  nomeEl.textContent = 'Enviando...';
  nomeEl.className = 'cert-nome';
  setLoading(btn, null, true);

  try {
    const formData = new FormData();
    formData.append('arquivo', file);
    const result = await EmpresasAPI.uploadCertificado(formData);
    document.getElementById('campo-caminho-cert').value = result.caminho;
    nomeEl.textContent = result.nome;
    nomeEl.className = 'cert-nome cert-ok';
  } catch (err) {
    nomeEl.textContent = 'Erro ao enviar arquivo';
    nomeEl.className = 'cert-nome cert-erro';
    showToast(err.message, 'error');
  } finally {
    setLoading(btn, null, false);
  }
});

function abrirModalNovaEmpresa() {
  document.getElementById('modal-empresa-title').textContent = 'Nova Empresa';
  document.getElementById('form-empresa').reset();
  document.getElementById('campo-cnpj').disabled = false;
  document.getElementById('campo-senha-label').textContent = 'Senha do Certificado *';
  document.getElementById('campo-senha').required = true;
  document.getElementById('campo-cert-file').value = '';
  document.getElementById('campo-caminho-cert').value = '';
  document.getElementById('cert-nome').textContent = 'Nenhum arquivo selecionado';
  document.getElementById('cert-nome').className = 'cert-nome';
  document.getElementById('modal-empresa').classList.add('open');
}

function abrirModalEdicao(cnpj) {
  const emp = window.empresas.find(e => e.cnpj === cnpj);
  if (!emp) return;

  document.getElementById('modal-empresa-title').textContent = 'Editar Empresa';
  document.getElementById('campo-cnpj').value = emp.cnpj;
  document.getElementById('campo-cnpj').disabled = true;
  document.getElementById('campo-razao-social').value = emp.razao_social;
  document.getElementById('campo-inscricao-municipal').value = emp.inscricao_municipal || '';
  document.getElementById('campo-caminho-cert').value = emp.caminho_certificado;
  document.getElementById('campo-cert-file').value = '';
  const nomeAtual = emp.caminho_certificado.split(/[\\/]/).pop();
  document.getElementById('cert-nome').textContent = nomeAtual;
  document.getElementById('cert-nome').className = 'cert-nome cert-ok';
  document.getElementById('campo-senha').value = '';
  document.getElementById('campo-senha').required = false;
  document.getElementById('campo-senha-label').textContent = 'Senha do Certificado (deixe em branco para manter)';
  document.getElementById('modal-empresa').classList.add('open');
}

function fecharModalEmpresa() {
  document.getElementById('modal-empresa').classList.remove('open');
}

// ─── Salvar Empresa ───────────────────────────────────────────────────────────

document.getElementById('form-empresa')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const btn = document.getElementById('btn-salvar-empresa');
  setLoading(btn, null, true);

  const cnpj = document.getElementById('campo-cnpj').value.replace(/\D/g, '');
  const isCriacao = !document.getElementById('campo-cnpj').disabled === false;
  // Se o campo CNPJ está desabilitado, é edição; senão, é criação
  const ehEdicao = document.getElementById('campo-cnpj').disabled;

  const caminhoCert = document.getElementById('campo-caminho-cert').value.trim();
  if (!caminhoCert) {
    showToast('Selecione o arquivo de certificado .pfx.', 'error');
    setLoading(btn, null, false);
    return;
  }

  const dados = {
    razao_social: document.getElementById('campo-razao-social').value.trim(),
    inscricao_municipal: document.getElementById('campo-inscricao-municipal').value.trim() || null,
    caminho_certificado: caminhoCert,
  };

  const senha = document.getElementById('campo-senha').value;
  if (senha) dados.senha_certificado = senha;

  try {
    if (ehEdicao) {
      await EmpresasAPI.atualizar(cnpj, dados);
      showToast('Empresa atualizada com sucesso!', 'success');
    } else {
      dados.cnpj = cnpj;
      if (!senha) {
        showToast('A senha do certificado é obrigatória no cadastro.', 'error');
        return;
      }
      await EmpresasAPI.criar(dados);
      showToast('Empresa cadastrada com sucesso!', 'success');
    }

    fecharModalEmpresa();
    await carregarEmpresas();

  } catch (err) {
    showToast(err.message, 'error', 5000);
  } finally {
    setLoading(btn, null, false);
  }
});

// ─── Deletar Empresa ──────────────────────────────────────────────────────────

function confirmarDelecao(cnpj, nome) {
  if (!confirm(`Deseja realmente excluir a empresa:\n\n${nome} (${formatarCnpj(cnpj)})\n\nEsta ação não pode ser desfeita.`)) return;
  deletarEmpresa(cnpj, nome);
}

async function deletarEmpresa(cnpj, nome) {
  try {
    await EmpresasAPI.deletar(cnpj);
    showToast(`Empresa ${nome} removida.`, 'success');
    await carregarEmpresas();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function truncarTexto(texto, max) {
  if (!texto || texto.length <= max) return texto;
  return '...' + texto.slice(-(max - 3));
}
