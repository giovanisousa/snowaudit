import streamlit as st
import pandas as pd
from database import conectar

st.set_page_config(page_title="Gestão de Empresas", layout="wide")
st.logo("logo_SnowAudit.png", icon_image="logo_SnowAudit.png")
st.title("🏢 Gestão de Empresas")

# --- NOVA EMPRESA ---
with st.form("form_nova_empresa", clear_on_submit=True):
    st.subheader("Cadastrar Nova Empresa")
    col1, col2 = st.columns([2, 1])
    razao_social = col1.text_input("Razão Social *")
    cnpj = col2.text_input("CNPJ")
    
    st.markdown("**Mapeamento de Colunas do Relatório Fiscal (Opcional)**")
    st.caption("💡 Deixe em branco para o sistema utilizar o padrão inteligente (Coluna A = CFOP, Coluna B = Valor Total, Ignora Impostos).")
    
    c1, c2, c3, c4 = st.columns(4)
    # Aplicação do conceito de Placeholder (Dica visual que some ao digitar)
    col_nota = c1.text_input("Coluna Valor Nota", value="", placeholder="Ex: B, 2 ou Vlr Contábil")
    col_icms = c2.text_input("Coluna Valor ICMS", value="", placeholder="Ex: C, 3 ou Vlr ICMS")
    col_pis = c3.text_input("Coluna Valor PIS", value="", placeholder="Ex: D, 4 ou Vlr PIS")
    col_cofins = c4.text_input("Coluna Valor COFINS", value="", placeholder="Ex: E, 5 ou Vlr COFINS")
    
    if st.form_submit_button("Cadastrar Empresa", type="primary"):
        if razao_social:
            conn = conectar()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO empresa (razao_social, cnpj, col_nota, col_icms, col_pis, col_cofins) 
                VALUES (?, ?, ?, ?, ?, ?)
            """, (razao_social, cnpj, col_nota, col_icms, col_pis, col_cofins))
            conn.commit()
            conn.close()
            st.success("✅ Empresa cadastrada com sucesso!")
            st.rerun()
        else:
            st.error("❌ O campo Razão Social é obrigatório para o cadastro.")

st.divider()

# --- LISTAGEM E EDIÇÃO DAS EMPRESAS ---
st.subheader("📋 Empresas Cadastradas")
conn = conectar()
df_empresas = pd.read_sql("SELECT * FROM empresa", conn)

if df_empresas.empty:
    st.info("Nenhuma empresa cadastrada no momento.")
else:
    for _, row in df_empresas.iterrows():
        id_emp = row['id']
        with st.expander(f"⚙️ {row['razao_social']} (CNPJ: {row.get('cnpj', 'Não informado')})"):
            with st.form(key=f"form_edit_{id_emp}"):
                e_c1, e_c2 = st.columns([2, 1])
                n_razao = e_c1.text_input("Razão Social", value=row['razao_social'])
                n_cnpj = e_c2.text_input("CNPJ", value=row.get('cnpj', '') if pd.notna(row.get('cnpj')) else "")
                
                st.markdown("**Editar Mapeamento de Colunas**")
                m1, m2, m3, m4 = st.columns(4)
                
                # Prepara os valores atuais. Se no banco estiver Null/NaN, transforma em string vazia para o placeholder aparecer.
                val_nota = str(row['col_nota']) if pd.notna(row['col_nota']) and str(row['col_nota']).strip() != "" else ""
                val_icms = str(row['col_icms']) if pd.notna(row['col_icms']) and str(row['col_icms']).strip() != "" else ""
                val_pis = str(row['col_pis']) if pd.notna(row['col_pis']) and str(row['col_pis']).strip() != "" else ""
                val_cofins = str(row['col_cofins']) if pd.notna(row['col_cofins']) and str(row['col_cofins']).strip() != "" else ""
                
                n_nota = m1.text_input("Valor Nota", value=val_nota, placeholder="Ex: B, 2 ou Vlr Contábil")
                n_icms = m2.text_input("Valor ICMS", value=val_icms, placeholder="Ex: C, 3 ou Vlr ICMS")
                n_pis = m3.text_input("Valor PIS", value=val_pis, placeholder="Ex: D, 4 ou Vlr PIS")
                n_cofins = m4.text_input("Valor COFINS", value=val_cofins, placeholder="Ex: E, 5 ou Vlr COFINS")
                
                col_btn_salvar, col_btn_vazio, col_btn_excluir = st.columns([3, 5, 2])
                
                if col_btn_salvar.form_submit_button("💾 Atualizar Dados", type="primary"):
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE empresa 
                        SET razao_social = ?, cnpj = ?, col_nota = ?, col_icms = ?, col_pis = ?, col_cofins = ?
                        WHERE id = ?
                    """, (n_razao, n_cnpj, n_nota, n_icms, n_pis, n_cofins, id_emp))
                    conn.commit()
                    st.success("Dados atualizados com sucesso!")
                    st.rerun()
                    
                if col_btn_excluir.form_submit_button("🗑️ Excluir Empresa"):
                    cursor = conn.cursor()
                    # Segurança: Limpa as regras amarradas a essa empresa antes de excluí-la
                    cursor.execute("DELETE FROM templates_regras WHERE id_empresa = ?", (id_emp,))
                    cursor.execute("DELETE FROM empresa WHERE id = ?", (id_emp,))
                    conn.commit()
                    st.success("Empresa removida do sistema.")
                    st.rerun()

conn.close()