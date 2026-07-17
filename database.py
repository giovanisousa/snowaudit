import sqlite3
import pandas as pd

def conectar():
    return sqlite3.connect("bancodedados.db", check_same_thread=False)

def criar_tabelas():
    conn = conectar()
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS contador (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        nome TEXT, crc TEXT)''')
    
    # NOVA ESTRUTURA: Armazena o nome real das colunas que vêm no arquivo do cliente
    cursor.execute('''CREATE TABLE IF NOT EXISTS empresa (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        cnpj TEXT, 
                        razao_social TEXT, 
                        cod_interno TEXT,
                        col_nota TEXT,
                        col_icms TEXT,
                        col_pis TEXT,
                        col_cofins TEXT)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS templates_regras (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        id_empresa INTEGER,
                        cfop_origem TEXT, 
                        tipo_valor TEXT, 
                        conta_destino TEXT)''')
    conn.commit()
    conn.close()

criar_tabelas()

def excluir_empresa(id_empresa):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM empresa WHERE id = ?", (id_empresa,))
    cursor.execute("DELETE FROM templates_regras WHERE id_empresa = ?", (id_empresa,))
    conn.commit()
    conn.close()

def excluir_regra(id_regra):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM templates_regras WHERE id = ?", (id_regra,))
    conn.commit()
    conn.close()

def atualizar_empresa(id_empresa, cnpj, razao_social, cod_interno, col_nota, col_icms, col_pis, col_cofins):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE empresa 
        SET cnpj = ?, razao_social = ?, cod_interno = ?, col_nota = ?, col_icms = ?, col_pis = ?, col_cofins = ?
        WHERE id = ?
    """, (cnpj, razao_social, cod_interno, col_nota, col_icms, col_pis, col_cofins, id_empresa))
    conn.commit()
    conn.close()

def atualizar_regra(id_regra, cfop, tipo_valor, conta):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE templates_regras 
        SET cfop_origem = ?, tipo_valor = ?, conta_destino = ? 
        WHERE id = ?
    """, (cfop, tipo_valor, conta, id_regra))
    conn.commit()
    conn.close()