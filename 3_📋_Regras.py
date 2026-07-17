import streamlit as st
import pandas as pd
from database import conectar, excluir_regra, atualizar_regra

st.set_page_config(page_title="Parametrização", layout="wide")
st.logo("logo_SnowAudit.png", icon_image="logo_SnowAudit.png")
st.title("⚙️ Regras De/Para por Empresa")

conn = conectar()
empresas = pd.read_sql("SELECT id, razao_social FROM empresa", conn)

if empresas.empty:
    st.warning("Cadastre uma empresa primeiro.")
    conn.close()
else:
    opcoes_empresa = dict(zip(empresas['razao_social'], empresas['id']))
    empresa_selecionada = st.selectbox("Selecione a Empresa:", list(opcoes_empresa.keys()))
    id_empresa = opcoes_empresa[empresa_selecionada]

    tab_manual, tab_lote = st.tabs(["➕ Cadastro Manual", "📂 Importação em Lote"])

    # --- ABA 1: CADASTRO MANUAL ---
    with tab_manual:
        with st.form("form_nova_regra", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            cfop = col1.text_input("Natureza / CFOP Origem")
            tipo_valor = col2.selectbox("Mapear qual indicador?", ["Valor_Nota", "Valor_ICMS", "Valor_PIS", "Valor_COFINS"])
            conta = col3.text_input("Conta Contábil Destino")
            
            if st.form_submit_button("Adicionar Regra") and cfop and conta:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO templates_regras (id_empresa, cfop_origem, tipo_valor, conta_destino) VALUES (?, ?, ?, ?)", 
                               (id_empresa, cfop, tipo_valor, conta))
                conn.commit()
                st.success("Regra vinculada!")
                st.rerun()

    # --- ABA 2: IMPORTAÇÃO EM LOTE ---
    with tab_lote:
        st.info("💡 Faça o upload de uma planilha (CSV ou Excel) contendo as regras. O arquivo precisa ter as colunas: **CFOP** (ou Natureza), **Conta** e (opcionalmente) **Indicador**.")
        arquivo_regras = st.file_uploader("Upload da Planilha de Regras", type=['csv', 'xlsx'])
        
        if arquivo_regras:
            if st.button("Processar e Salvar Lote", type="primary"):
                ext = arquivo_regras.name.split('.')[-1].lower()
                try:
                    if ext == 'xlsx':
                        df_import = pd.read_excel(arquivo_regras)
                    else:
                        df_import = pd.read_csv(arquivo_regras, sep=None, engine='python')
                    
                    cols_lower = {c.lower(): c for c in df_import.columns}
                    # Aceita colunas com 'cfop' ou 'natureza' no nome para facilitar
                    col_cfop = next((cols_lower[c] for c in cols_lower if 'cfop' in c or 'natureza' in c), None)
                    col_conta = next((cols_lower[c] for c in cols_lower if 'conta' in c or 'ctb' in c), None)
                    col_ind = next((cols_lower[c] for c in cols_lower if 'indicador' in c or 'tipo' in c), None)

                    if not col_cfop or not col_conta:
                        st.error("❌ Não consegui identificar as colunas de Origem e Conta no arquivo. Verifique o cabeçalho.")
                    else:
                        sucessos = 0
                        cursor = conn.cursor()
                        for _, row in df_import.iterrows():
                            val_cfop = str(row[col_cfop]).strip()
                            val_conta = str(row[col_conta]).strip()
                            val_ind = str(row[col_ind]).strip() if col_ind else "Valor_Nota"
                            
                            if val_cfop and val_cfop != 'nan' and val_conta and val_conta != 'nan':
                                cursor.execute("INSERT INTO templates_regras (id_empresa, cfop_origem, tipo_valor, conta_destino) VALUES (?, ?, ?, ?)", 
                                               (id_empresa, val_cfop, val_ind, val_conta))
                                sucessos += 1
                                
                        conn.commit()
                        st.success(f"✅ {sucessos} regras importadas com sucesso!")
                        st.rerun()
                except Exception as e:
                    st.error(f"Erro ao processar arquivo: {e}")

    st.divider()

    # --- GRID VERTICAL DE REGRAS (COM SELEÇÃO CORRIGIDA) ---
    st.subheader("📋 Regras Operacionais")
    df_regras = pd.read_sql(f"SELECT id, cfop_origem, tipo_valor, conta_destino FROM templates_regras WHERE id_empresa = {id_empresa}", conn)
    conn.close()

    if df_regras.empty:
        st.info("Nenhuma regra configurada.")
    else:
        # 1. Callback (Função) que altera a memória interna de todos os checkboxes
        def alternar_todos():
            estado_mestre = st.session_state[f"sel_all_{id_empresa}"]
            for id_r in df_regras['id']:
                st.session_state[f"chk_{id_r}"] = estado_mestre

        # 2. Controles Superiores
        col_sel, col_btn = st.columns([3, 7])
        with col_sel:
            st.checkbox("☑️ Selecionar Todas as Regras", key=f"sel_all_{id_empresa}", on_change=alternar_todos)
        
        placeholder_botao = col_btn.empty() 

        # 3. Cabeçalho da Grid
        h_chk, h_cfop, h_tipo, h_conta, h_edit = st.columns([0.5, 3, 2, 3.5, 1])
        h_chk.markdown("**Sel.**")
        h_cfop.markdown("**Natureza / CFOP Origem**")
        h_tipo.markdown("**Indicador**")
        h_conta.markdown("**Conta Contábil Destino**")
        h_edit.markdown("**Editar**")
        st.markdown("---")

        regras_selecionadas = []

        # 4. Laço de Repetição (Linhas)
        for _, row in df_regras.iterrows():
            id_regra = row['id']
            r_chk, r_cfop, r_tipo, r_conta, r_edit = st.columns([0.5, 3, 2, 3.5, 1])
            
            marcado = r_chk.checkbox("Selecionar", key=f"chk_{id_regra}", label_visibility="collapsed")
            
            if marcado:
                regras_selecionadas.append(id_regra)
            
            r_cfop.text(row['cfop_origem'])
            r_tipo.text(row['tipo_valor'])
            r_conta.text(row['conta_destino'])
            
            btn_edit_reg = r_edit.button("✏️", key=f"btn_edit_reg_{id_regra}")
            
            if btn_edit_reg:
                st.session_state[f"editando_reg_{id_regra}"] = True
                
            if st.session_state.get(f"editando_reg_{id_regra}", False):
                with st.form(key=f"form_edicao_reg_{id_regra}"):
                    st.markdown(f"**✏️ Editando Regra**")
                    e1, e2, e3 = st.columns(3)
                    n_cfop = e1.text_input("Natureza / CFOP", value=row['cfop_origem'])
                    n_tipo = e2.selectbox("Indicador", ["Valor_Nota", "Valor_ICMS", "Valor_PIS", "Valor_COFINS"], 
                                          index=["Valor_Nota", "Valor_ICMS", "Valor_PIS", "Valor_COFINS"].index(row['tipo_valor']))
                    n_conta = e3.text_input("Conta Destino", value=row['conta_destino'])
                    
                    b_salvar, b_cancelar = st.columns([2, 8])
                    if b_salvar.form_submit_button("Atualizar", type="primary"):
                        atualizar_regra(id_regra, n_cfop, n_tipo, n_conta)
                        st.session_state[f"editando_reg_{id_regra}"] = False
                        st.rerun()
                    if b_cancelar.form_submit_button("Cancelar"):
                        st.session_state[f"editando_reg_{id_regra}"] = False
                        st.rerun()
            st.markdown("<hr style='margin:0; padding:0; opacity:0.1;'>", unsafe_allow_html=True)
        
        # 5. Injeta o Botão Dinâmico
        if regras_selecionadas:
            with placeholder_botao:
                if st.button(f"🗑️ Excluir {len(regras_selecionadas)} Regras Selecionadas", type="primary"):
                    for id_r in regras_selecionadas:
                        excluir_regra(id_r) 
                    st.rerun()