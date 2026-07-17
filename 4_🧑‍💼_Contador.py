import streamlit as st
import pandas as pd
from database import conectar

st.set_page_config(page_title="Perfil do Contador", layout="centered")
st.logo("logo_SnowAudit.png", icon_image="logo_SnowAudit.png")
st.title("👨‍💼 Perfil do Escritório")

conn = conectar()
contador_atual = pd.read_sql("SELECT * FROM contador LIMIT 1", conn)

# Se já existe cadastro e NÃO estamos no modo de edição
if not contador_atual.empty and not st.session_state.get('editando_contador', False):
    st.success(f"**Escritório Ativo:** {contador_atual['nome'].iloc[0]}")
    st.info(f"**CRC:** {contador_atual['crc'].iloc[0]}")
    
    if st.button("🔄 Alterar Dados do Perfil"):
        st.session_state['editando_contador'] = True
        st.rerun()
else:
    # Modo de Criação ou Edição
    with st.form("form_contador"):
        st.subheader("Cadastro / Edição de Perfil")
        
        # Preenche com os dados existentes, se houver
        nome_padrao = contador_atual['nome'].iloc[0] if not contador_atual.empty else ""
        crc_padrao = contador_atual['crc'].iloc[0] if not contador_atual.empty else ""
        
        nome = st.text_input("Nome do Contador Responsável ou Escritório", value=nome_padrao)
        crc = st.text_input("Número do CRC", value=crc_padrao)
        
        col1, col2 = st.columns([1, 4])
        salvar = col1.form_submit_button("Salvar")
        
        # O botão Cancelar só aparece se já houver um perfil salvo para voltar
        cancelar = col2.form_submit_button("Cancelar") if not contador_atual.empty else False

        if salvar and nome and crc:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM contador") # Limpa o antigo
            cursor.execute("INSERT INTO contador (nome, crc) VALUES (?, ?)", (nome, crc))
            conn.commit()
            st.session_state['editando_contador'] = False
            st.success("Perfil salvo com sucesso!")
            st.rerun()
            
        if cancelar:
            st.session_state['editando_contador'] = False
            st.rerun()
conn.close()