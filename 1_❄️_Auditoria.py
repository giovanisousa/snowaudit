import streamlit as st
import pandas as pd
from database import conectar
from fpdf import FPDF
import datetime
import tempfile
import os
import re
import unicodedata
import io
import logging
import traceback

st.set_page_config(page_title="SnowAudit", page_icon="❄️", layout="wide")

# --- IDENTIDADE VISUAL ---
if os.path.exists("logo_SnowAudit.png"):
    st.logo("logo_SnowAudit.png", icon_image="logo_SnowAudit.png")

st.title("❄️ SnowAudit: Auditoria Contábil e Fiscal")
st.caption("Desenvolvido para um fechamento limpo, rápido e blindado a erros. | Gerado por: SnowAudit Shield")

# --- CONFIGURAÇÃO DO SISTEMA DE LOGS CAIXA-PRETA ---
ARQUIVO_LOG = "snowaudit_erros.log"
logger = logging.getLogger("SnowAudit")
logger.setLevel(logging.ERROR)
if not logger.handlers:
    fh = logging.FileHandler(ARQUIVO_LOG, encoding='utf-8')
    formatter = logging.Formatter("\n" + "="*50 + "\nDATA: %(asctime)s \nERRO: %(message)s")
    fh.setFormatter(formatter)
    logger.addHandler(fh)

# --- CONEXÃO E SELEÇÃO DE EMPRESA ---
conn = conectar()
empresas = pd.read_sql("SELECT id, razao_social, cnpj, col_nota, col_icms, col_pis, col_cofins FROM empresa", conn)

if empresas.empty:
    st.info("👈 Cadastre uma empresa e seus layouts no menu lateral para começar.")
    conn.close()
    st.stop()

opcoes_empresa = dict(zip(empresas['razao_social'], empresas['id']))
empresa_alvo = st.selectbox("Selecione a Empresa para a Auditoria:", list(opcoes_empresa.keys()))

config_empresa = empresas[empresas['razao_social'] == empresa_alvo].iloc[0]
id_empresa = config_empresa['id']

df_regras = pd.read_sql(f"SELECT cfop_origem as CFOP, tipo_valor as Tipo_Valor, conta_destino as Conta_Destino FROM templates_regras WHERE id_empresa = {id_empresa}", conn)
conn.close()

st.divider()
st.subheader("📂 Upload dos Relatórios Originais do Sistema")
col_f, col_c = st.columns(2)

with col_f:
    arquivo_fiscal = st.file_uploader("Relatório Fiscal (ex: Total por natureza.xlsx/csv)", type=["csv", "xlsx"])
with col_c:
    arquivo_contabil = st.file_uploader("Balancete Contábil (ex: balancete.csv/xlsx)", type=["csv", "xlsx"])


# ==========================================
# MOTORES DE LIMPEZA E TRADUÇÃO DE DADOS
# ==========================================

def carregar_e_limpar_relatorio(arquivo, tipo_relatorio):
    """Lê arquivos bagunçados (.xlsx, .csv com ';' e .csv com ',') e reconstrói formatos corrompidos."""
    extensao = arquivo.name.split('.')[-1].lower()
    
    if extensao == 'xlsx':
        df_bruto = pd.read_excel(arquivo, header=None)
    else:
        conteudo_bytes = arquivo.read()
        arquivo.seek(0)
        
        try:
            conteudo_str = conteudo_bytes.decode('utf-8')
        except UnicodeDecodeError:
            conteudo_str = conteudo_bytes.decode('latin1')
            
        # Heurística SnowAudit: Descobre o separador olhando as primeiras linhas
        primeiras_linhas = '\n'.join(conteudo_str.split('\n')[:15])
        if ';' in primeiras_linhas:
            separador = ';'
            conteudo_final = conteudo_str
        else:
            separador = ','
            # MÁGICA SNOWAUDIT: RECONSTRUTOR DE CSV CORROMPIDO (Vírgula dupla)
            linhas_corrigidas = []
            for linha in conteudo_str.split('\n'):
                # 1. Remove pontos de milhar
                linha = re.sub(r'(\d)\.(\d{3})', r'\1\2', linha)
                linha = re.sub(r'(\d)\.(\d{3})', r'\1\2', linha) 
                # 2. Troca a vírgula decimal por ponto para proteger colunas
                linha = re.sub(r'(\d),(\d{1,2})([\)\]"\'\s]*)(?=[,\n\r]|$)', r'\1.\2\3', linha)
                linhas_corrigidas.append(linha)
            conteudo_final = '\n'.join(linhas_corrigidas)
            
        # O Pandas engole o arquivo consertado na memória
        df_bruto = pd.read_csv(io.StringIO(conteudo_final), sep=separador, header=None, names=range(100), engine='python')

    # Busca a linha onde o cabeçalho real começa
    linha_cabecalho = 0
    for i, linha in df_bruto.iterrows():
        texto_linha = str(linha.values).lower()
        if 'cfop' in texto_linha or 'conta' in texto_linha or 'saldo' in texto_linha or 'valor' in texto_linha:
            linha_cabecalho = i
            break
            
    df = df_bruto.iloc[linha_cabecalho+1:].copy()
    df.columns = df_bruto.iloc[linha_cabecalho].values
    df = df.reset_index(drop=True)
    
    df = df.loc[:, df.columns.notna()]
    df.columns = [str(c).strip() for c in df.columns]
    df = df.loc[:, [c for c in df.columns if c.lower() != 'nan']]
    
    if len(df.columns) > 0:
        primeira_coluna = df.columns[0]
        df = df[df[primeira_coluna].astype(str).str.strip() != str(primeira_coluna).strip()]
        df = df.dropna(subset=[primeira_coluna])
                
    return df

def limpar_valor_financeiro(val):
    if pd.isna(val): return 0.0
    val_str = str(val).strip()
    if not val_str or val_str.lower() in ['nan', 'none', 'null']: return 0.0
    
    is_negative = False
    if val_str.startswith('(') and val_str.endswith(')'):
        is_negative = True
        val_str = val_str[1:-1].strip()
        
    if ',' in val_str:
        val_str = val_str.replace('.', '').replace(',', '.')
        
    try:
        num = float(val_str)
        return -num if is_negative else num
    except ValueError:
        return 0.0

def gerar_chave_cruzamento(texto):
    if pd.isna(texto): return ""
    texto = str(texto).strip()
    match = re.match(r'^([\d\.\/\-]+)', texto)
    if match:
        codigo = match.group(1)
        codigo_limpo = re.sub(r'[^\d]', '', codigo)
        if len(codigo_limpo) >= 3: 
            return codigo_limpo
            
    texto = texto.lower()
    texto = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')
    texto = re.sub(r'[^a-z0-9]', '', texto) 
    return texto


# ==========================================
# EXECUÇÃO DA AUDITORIA (BLINDADA)
# ==========================================

if arquivo_fiscal and arquivo_contabil:
    if st.button("🚀 Executar Auditoria Direta", type="primary"):
        
        # --- CAIXA PRETA: TRATAMENTO DE ERROS ---
        try:
            with st.spinner("Limpando e processando arquivos brutos..."):
                
                df_fiscal_raw = carregar_e_limpar_relatorio(arquivo_fiscal, "fiscal")
                df_contabil_raw = carregar_e_limpar_relatorio(arquivo_contabil, "contabil")
                
                # --- 1. BALANCETE CONTÁBIL ---
                col_conta_ctb = next((c for c in df_contabil_raw.columns if 'conta' in str(c).lower()), None)
                col_saldo_ctb = next((c for c in df_contabil_raw.columns if any(palavra in str(c).lower() for palavra in ['saldo', 'atual', 'credor', 'devedor']) or re.search(r'\d{2}/\d{4}', str(c))), None)
                
                if not col_conta_ctb or not col_saldo_ctb:
                    st.error("❌ Não consegui identificar as colunas 'Conta' e 'Saldo' no Balancete. Verifique o arquivo.")
                    st.stop()
                    
                df_contabil_raw.rename(columns={col_conta_ctb: 'Conta_Contabil', col_saldo_ctb: 'Saldo_R$'}, inplace=True)
                df_contabil_raw['Saldo_R$'] = df_contabil_raw['Saldo_R$'].apply(limpar_valor_financeiro)


                # --- 2. RELATÓRIO FISCAL ---
                def resolver_coluna_por_posicao(config_val, df, default_pos=""):
                    val = str(config_val).strip().upper() if pd.notna(config_val) else ""
                    if not val or val == 'NAN' or val == 'NONE': val = default_pos.upper()
                    if not val: return ""
                    
                    if val.isdigit():
                        idx = int(val) - 1
                        if 0 <= idx < len(df.columns): return df.columns[idx]
                        return "" 
                    if len(val) == 1 and val.isalpha():
                        idx = ord(val) - 65 
                        if 0 <= idx < len(df.columns): return df.columns[idx]
                        return "" 
                    return str(config_val).strip()

                def limpar_nome_coluna(texto):
                    if not texto or pd.isna(texto): return ""
                    texto = str(texto).lower().strip()
                    texto = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')
                    return texto

                col_nota_real = resolver_coluna_por_posicao(config_empresa.get('col_nota', ''), df_fiscal_raw, default_pos='B')
                col_icms_real = resolver_coluna_por_posicao(config_empresa.get('col_icms', ''), df_fiscal_raw, default_pos='')
                col_pis_real = resolver_coluna_por_posicao(config_empresa.get('col_pis', ''), df_fiscal_raw, default_pos='')
                col_cofins_real = resolver_coluna_por_posicao(config_empresa.get('col_cofins', ''), df_fiscal_raw, default_pos='')

                traducao_config = {
                    limpar_nome_coluna(col_nota_real): 'Valor_Nota',
                    limpar_nome_coluna(col_icms_real): 'Valor_ICMS',
                    limpar_nome_coluna(col_pis_real): 'Valor_PIS',
                    limpar_nome_coluna(col_cofins_real): 'Valor_COFINS'
                }
                
                nova_nomenclatura = {}
                for col_real in df_fiscal_raw.columns:
                    col_norm = limpar_nome_coluna(col_real)
                    if col_norm in traducao_config and col_norm != "":
                        nova_nomenclatura[col_real] = traducao_config[col_norm]
                
                col_cfop_fiscal = next((c for c in df_fiscal_raw.columns if 'cfop' in str(c).lower()), None)
                if not col_cfop_fiscal:
                    col_cfop_fiscal = next((c for c in df_fiscal_raw.columns if 'natureza' in str(c).lower()), None)
                if not col_cfop_fiscal and len(df_fiscal_raw.columns) > 0:
                    col_cfop_fiscal = df_fiscal_raw.columns[0]
                    
                if col_cfop_fiscal in df_fiscal_raw.columns:
                    nova_nomenclatura[col_cfop_fiscal] = 'CFOP'
                
                df_fiscal_raw.rename(columns=nova_nomenclatura, inplace=True)
                
                if 'Nota_Fiscal' not in df_fiscal_raw.columns:
                    df_fiscal_raw['Nota_Fiscal'] = 'Resumo_' + df_fiscal_raw.index.astype(str)

                colunas_valores = [v for v in nova_nomenclatura.values() if v in ['Valor_Nota', 'Valor_ICMS', 'Valor_PIS', 'Valor_COFINS']]
                
                if not colunas_valores or 'CFOP' not in df_fiscal_raw.columns:
                    st.error("❌ O sistema não encontrou colunas de valores válidas no arquivo fiscal baseadas no layout (ou padrão).")
                    st.stop()

                df_fiscal_desdobrado = df_fiscal_raw.melt(id_vars=['Nota_Fiscal', 'CFOP'], value_vars=colunas_valores, var_name='Tipo_Valor', value_name='Valor_R$')
                df_fiscal_desdobrado['Valor_R$'] = df_fiscal_desdobrado['Valor_R$'].apply(limpar_valor_financeiro)
                
                df_fiscal_desdobrado = df_fiscal_desdobrado.dropna(subset=['CFOP'])
                df_fiscal_desdobrado = df_fiscal_desdobrado[df_fiscal_desdobrado['CFOP'].astype(str).str.lower().str.strip() != 'nan']
                termos_lixo = ['total', 'subtotal', 'resumo', 'período', 'periodo', 'saldo']
                padrao_lixo = '|'.join(termos_lixo)
                df_fiscal_desdobrado = df_fiscal_desdobrado[~df_fiscal_desdobrado['CFOP'].astype(str).str.lower().str.contains(padrao_lixo, regex=True)]
                df_fiscal_desdobrado = df_fiscal_desdobrado[df_fiscal_desdobrado['CFOP'].astype(str).str.contains(r'\d')]

                # --- 3. MERGE E VALIDAÇÃO ---
                df_regras['CFOP_Norm'] = df_regras['CFOP'].apply(gerar_chave_cruzamento)
                df_fiscal_desdobrado['CFOP_Norm'] = df_fiscal_desdobrado['CFOP'].apply(gerar_chave_cruzamento)
                df_regras['Conta_Destino_Norm'] = df_regras['Conta_Destino'].apply(gerar_chave_cruzamento)
                df_contabil_raw['Conta_Contabil_Norm'] = df_contabil_raw['Conta_Contabil'].apply(gerar_chave_cruzamento)

                df_validacao_regras = pd.merge(df_fiscal_desdobrado, df_regras.drop(columns=['CFOP']), on=['CFOP_Norm', 'Tipo_Valor'], how='left')
                regras_faltantes = df_validacao_regras[df_validacao_regras['Conta_Destino'].isna() & (df_validacao_regras['Valor_R$'] > 0)]
                
                if not regras_faltantes.empty:
                    st.error("❌ A auditoria foi bloqueada por falta de parametrização!")
                    st.warning("Os seguintes movimentos fiscais não possuem regras de destino configuradas:")
                    st.dataframe(regras_faltantes[['CFOP', 'Tipo_Valor']].drop_duplicates(), hide_index=True)
                    st.stop()
                    
                df_fiscal_mapeado = pd.merge(df_fiscal_desdobrado, df_regras.drop(columns=['CFOP']), on=['CFOP_Norm', 'Tipo_Valor'], how='inner')
                df_fiscal_agrupado = df_fiscal_mapeado.groupby('Conta_Destino_Norm').agg({'Valor_R$': 'sum', 'Conta_Destino': 'first'}).reset_index()
                df_fiscal_agrupado.rename(columns={'Valor_R$': 'Total_Apurado'}, inplace=True)
                
                df_contabil_deduplicado = df_contabil_raw.drop_duplicates(subset=['Conta_Contabil_Norm'])
                df_auditoria = pd.merge(df_fiscal_agrupado, df_contabil_deduplicado, left_on='Conta_Destino_Norm', right_on='Conta_Contabil_Norm', how='left').fillna(0)
                
                # --- 4. MATEMÁTICA FINAL ---
                df_auditoria['Saldo_R$'] = df_auditoria['Saldo_R$'].fillna(0)
                df_auditoria['Total_Apurado'] = df_auditoria['Total_Apurado'].fillna(0)
                
                df_auditoria['Diferenca'] = df_auditoria['Total_Apurado'].abs() - df_auditoria['Saldo_R$'].abs()
                df_auditoria['Status'] = df_auditoria['Diferenca'].apply(lambda x: '🟢 Bateu' if abs(round(x, 2)) < 0.05 else '🔴 Divergência')
                
                st.success("✅ Validação de integridade concluída direto dos arquivos brutos.")
                st.subheader("Painel Geral de Conformidade")
                st.dataframe(df_auditoria[['Conta_Destino', 'Total_Apurado', 'Saldo_R$', 'Diferenca', 'Status']], use_container_width=True, hide_index=True)

                # --- 5. GERAÇÃO DO PAPEL DE TRABALHO (PDF) ---
                qtd_erros = len(df_auditoria[df_auditoria['Status'] == '🔴 Divergência'])
                
                if qtd_erros == 0:
                    st.toast("Auditoria concluída: 100% de conformidade!", icon="✅")
                    st.success("✅ Fechamento 100% validado! Nenhuma divergência encontrada nos saldos parametrizados.")
                    
                    conn = conectar()
                    contador_db = pd.read_sql("SELECT * FROM contador LIMIT 1", conn)
                    conn.close()
                    
                    nome_contador = contador_db['nome'].iloc[0] if not contador_db.empty else "Fernando Neves Tapada"
                    crc_contador = contador_db['crc'].iloc[0] if not contador_db.empty else "Não Cadastrado"
                    data_atual = datetime.datetime.now().strftime('%d/%m/%Y às %H:%M')
                    
                    pdf = FPDF()
                    pdf.add_page()
                    
                    if os.path.exists("logo_SnowAudit.png"):
                        pdf.image("logo_SnowAudit.png", x=10, y=8, w=25)
                    
                    pdf.set_y(15) 
                    pdf.set_font("Arial", 'B', 14)
                    pdf.cell(0, 10, txt="TERMO DE CONCILIAÇÃO CONTÁBIL X FISCAL", ln=True, align='C')
                    
                    pdf.set_font("Arial", 'I', 8)
                    pdf.set_text_color(100, 100, 100) 
                    pdf.cell(0, 5, txt="Gerado por: SnowAudit Shield", ln=True, align='R')
                    pdf.set_text_color(0, 0, 0) 
                    
                    pdf.ln(20) 
                    
                    pdf.set_font("Arial", size=10)
                    pdf.cell(0, 8, txt=f"Escritório Responsável: {nome_contador} (CRC: {crc_contador})", ln=True)
                    pdf.cell(0, 8, txt=f"Empresa Auditada: {empresa_alvo} (CNPJ: {config_empresa['cnpj']})", ln=True)
                    pdf.cell(0, 8, txt=f"Data da Auditoria: {data_atual}", ln=True)
                    
                    posicao_y_linha = pdf.get_y() + 2
                    pdf.line(10, posicao_y_linha, 200, posicao_y_linha)
                    pdf.ln(10)
                    
                    pdf.set_font("Arial", 'B', 11)
                    pdf.cell(200, 8, txt="PARECER TÉCNICO: 100% CONCILIADO", ln=True)
                    pdf.set_font("Arial", size=10)
                    pdf.multi_cell(0, 8, txt="Declaro para os devidos fins que o cruzamento analítico entre os relatórios do módulo Fiscal e o Balancete Contábil referente ao período supracitado foi realizado com sucesso. Não foram encontradas divergências nos saldos das contas parametrizadas.")
                    pdf.ln(5)
                    pdf.set_font("Arial", 'B', 10)
                    pdf.cell(130, 8, txt="Conta Contábil", border=1)
                    pdf.cell(60, 8, txt="Saldo Auditado (R$)", border=1, ln=True, align='C')
                    
                    pdf.set_font("Arial", size=9)
                    for _, row in df_auditoria.iterrows():
                        pdf.cell(130, 8, txt=str(row['Conta_Destino']).encode('latin-1', 'replace').decode('latin-1'), border=1)
                        pdf.cell(60, 8, txt=f"{row['Total_Apurado']:,.2f}", border=1, ln=True, align='R')
                    
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                        pdf.output(tmp.name)
                        with open(tmp.name, "rb") as f:
                            pdf_bytes = f.read()
                    os.remove(tmp.name) 

                    st.download_button(
                        label="📄 Baixar Papel de Trabalho (PDF)",
                        data=pdf_bytes,
                        file_name=f"Auditoria_{config_empresa['cnpj']}.pdf",
                        mime="application/pdf",
                        type="primary"
                    )
                
                st.divider()
                st.subheader("🔎 Detalhamento por Conta Contábil")
                for _, row in df_auditoria.iterrows():
                    conta_nome = row['Conta_Destino']
                    conta_norm = row['Conta_Destino_Norm']
                    status = row['Status']
                    diferenca = row['Diferenca']
                    icone = "⚠️" if "Divergência" in status else "✅"
                    
                    with st.expander(f"{icone} Analisar conta: {conta_nome} | Diferença: R$ {diferenca:,.2f}"):
                        notas_da_conta = df_fiscal_mapeado[df_fiscal_mapeado['Conta_Destino_Norm'] == conta_norm]
                        col_a, col_b = st.columns(2)
                        with col_a:
                            st.markdown("**Subtotal por CFOP / Natureza**")
                            subtotal_cfop = notas_da_conta.groupby(['CFOP', 'Tipo_Valor'])['Valor_R$'].sum().reset_index()
                            st.dataframe(subtotal_cfop, use_container_width=True, hide_index=True)
                        with col_b:
                            st.markdown("**Lista de Notas Fiscais Processadas**")
                            st.dataframe(notas_da_conta[['Nota_Fiscal', 'CFOP', 'Tipo_Valor', 'Valor_R$']], use_container_width=True, hide_index=True)

        # Se o erro for de regras faltantes (que chamam st.stop()), o Streamlit gerencia silenciosamente.
        # Se for um erro crítico de quebra do código, ele cai no except abaixo:
        except Exception as e:
            msg_erro = f"{traceback.format_exc()}"
            logger.error(f"Falha ao processar auditoria:\n{msg_erro}")
            
            st.error("🚨 Ocorreu um erro estrutural inesperado ao ler os arquivos do cliente.")
            st.warning("O **SnowAudit** capturou os dados técnicos deste travamento. Por favor, faça o download do log abaixo e envie ao suporte/desenvolvedor para investigação.")
            
            # Lê o arquivo de log para disponibilizar no botão de download
            try:
                with open(ARQUIVO_LOG, "r", encoding="utf-8") as f:
                    log_data = f.read()
            except:
                log_data = "Não foi possível resgatar o arquivo de log fisicamente, mas o erro foi: " + str(e)
                
            st.download_button(
                label="⬇️ Baixar Log de Erro (Para o Desenvolvedor)",
                data=log_data,
                file_name=f"Log_SnowAudit_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                mime="text/plain",
                type="secondary"
            )