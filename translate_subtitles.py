#!/usr/bin/env python3
import os
import re
import subprocess
import json
import logging
import requests
import time
import shutil
import html
from pathlib import Path
from tqdm import tqdm

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("/app/subtitle_translator.log"),
        logging.StreamHandler()
    ]
)

# Configurações
MOVIES_DIR = "/movies"
TV_DIR = "/tv"
SUP_LOG_FILE = "/temp/legendassup.txt"
TEMP_DIR = "/app/temp"
TRANSLATE_API_URL = os.environ.get("TRANSLATE_API_URL", "http://192.168.2.46:5000/translate")

# Criar diretório temporário
os.makedirs(TEMP_DIR, exist_ok=True)

def get_all_mkv_files():
    """Encontra todos os arquivos .mkv nas pastas de filmes e TV"""
    mkv_files = []
    
    logging.info("Buscando arquivos .mkv em %s", MOVIES_DIR)
    for root, _, files in os.walk(MOVIES_DIR):
        for file in files:
            if file.endswith(".mkv"):
                mkv_files.append(os.path.join(root, file))
    
    logging.info("Buscando arquivos .mkv em %s", TV_DIR)
    for root, _, files in os.walk(TV_DIR):
        for file in files:
            if file.endswith(".mkv"):
                mkv_files.append(os.path.join(root, file))
    
    logging.info("Total de arquivos .mkv encontrados: %d", len(mkv_files))
    return mkv_files

def get_subtitle_tracks(mkv_file):
    """Extrai informações sobre as faixas de legendas em um arquivo .mkv"""
    try:
        result = subprocess.run(
            ["mkvmerge", "-J", mkv_file],
            capture_output=True,
            text=True,
            check=True
        )
        
        info = json.loads(result.stdout)
        subtitle_tracks = []
        
        for track in info.get("tracks", []):
            if track.get("type") == "subtitles":
                subtitle_tracks.append({
                    "id": track.get("id"),
                    "codec": track.get("codec"),
                    "language": track.get("properties", {}).get("language"),
                    "track_name": track.get("properties", {}).get("track_name")
                })
        
        return subtitle_tracks
    except subprocess.CalledProcessError as e:
        logging.error("Erro ao obter informações do arquivo %s: %s", mkv_file, e)
        logging.error("Saída de erro: %s", e.stderr)
        return []
    except json.JSONDecodeError:
        logging.error("Erro ao decodificar informações do arquivo %s", mkv_file)
        return []

def extract_subtitle(mkv_file, track_id, output_file):
    """Extrai uma faixa de legenda de um arquivo .mkv usando um arquivo temporário"""
    try:
        # Criar um nome de arquivo temporário único
        temp_subtitle = os.path.join(TEMP_DIR, f"temp_subtitle_{os.path.basename(mkv_file)}_{track_id}.srt")
        
        logging.info(f"Extraindo para arquivo temporário: {temp_subtitle}")
        
        # Extrair para o arquivo temporário
        cmd = f'mkvextract tracks "{mkv_file}" {track_id}:"{temp_subtitle}"'
        logging.info(f"Executando comando: {cmd}")
        
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            logging.error(f"Falha ao extrair legenda. Código de saída: {process.returncode}")
            logging.error(f"Erro: {stderr.decode('utf-8', errors='replace')}")
            return False
        
        # Criar diretório de saída se não existir
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        # Mover o arquivo temporário para o destino final
        shutil.move(temp_subtitle, output_file)
        
        # Verificar se o arquivo foi criado
        if os.path.exists(output_file):
            logging.info(f"Legenda extraída com sucesso: {output_file}")
            return True
        else:
            logging.warning(f"Arquivo de saída não encontrado após a extração: {output_file}")
            return False
            
    except Exception as e:
        logging.error(f"Erro ao extrair legenda: {str(e)}")
        return False

def preprocess_text(text):
    """Pré-processa o texto para tradução, preservando tags"""
    # Armazenar tags HTML para reinseri-las após tradução
    tags = {}
    tag_counter = 0
    
    # Função para substituir tags HTML por placeholders
    def replace_tag(match):
        nonlocal tag_counter
        tag = match.group(0)
        # Usar um placeholder mais único para evitar problemas
        placeholder = f"[[[TAG{tag_counter}]]]"
        tags[placeholder] = tag
        tag_counter += 1
        return placeholder
    
    # Substituir todas as tags HTML por placeholders
    processed_text = re.sub(r'<[^>]+>', replace_tag, text)
    
    return processed_text, tags

def postprocess_text(text, tags):
    """Restaura as tags HTML no texto traduzido e limpa placeholders remanescentes"""
    processed_text = text
    
    # Primeiro substituir os placeholders exatos
    for placeholder, tag in tags.items():
        processed_text = processed_text.replace(placeholder, tag)
    
    # Em seguida, procurar por variações dos placeholders que possam ter sido alteradas
    # durante a tradução e removê-las
    processed_text = re.sub(r'[\[\]_]*TAG\d+[\[\]_]*', '', processed_text)
    
    return processed_text

def get_supported_languages():
    """Obtém a lista de idiomas suportados pela API"""
    try:
        response = requests.get(f"{TRANSLATE_API_URL.replace('/translate', '/languages')}")
        if response.status_code == 200:
            languages = response.json()
            logging.info(f"Idiomas suportados: {languages}")
            return languages
        else:
            logging.warning(f"Não foi possível obter a lista de idiomas. Status: {response.status_code}")
            return []
    except Exception as e:
        logging.error(f"Erro ao obter idiomas suportados: {e}")
        return []

def translate_text(text):
    """Traduz um texto único usando a API LibreTranslate"""
    try:
        # Pré-processamento para lidar com tags HTML
        processed_text, tags = preprocess_text(text)
        
        # Formatação da requisição para o LibreTranslate
        payload = {
            "q": processed_text,
            "source": "en",
	    "target": "pt-BR"  # ← AGORA COM pt-BR
        }
        
        # Adicionar cabeçalhos apropriados para API REST
        headers = {
            "Content-Type": "application/json"
        }
        
        # Fazer a requisição
        response = requests.post(
            TRANSLATE_API_URL,
            data=json.dumps(payload),
            headers=headers
        )
        
        # Verificar se a resposta foi bem-sucedida
        if response.status_code == 200:
            try:
                result = response.json()
                translated_text = result.get("translatedText", processed_text)
                
                # Restaurar as tags HTML no texto traduzido
                final_text = postprocess_text(translated_text, tags)
                return final_text
            except Exception as e:
                logging.error(f"Erro ao processar resposta da API: {e}")
                logging.error(f"Resposta recebida: {response.text}")
                return text
        else:
            logging.warning(f"Falha na tradução, status {response.status_code}: {processed_text}")
            logging.warning(f"Resposta: {response.text}")
            return text
            
    except Exception as e:
        logging.error(f"Erro ao traduzir texto: {e}")
        return text

def translate_subtitle(input_file, output_file):
    """Traduz uma legenda de inglês para português brasileiro"""
    try:
        # Verificar se o arquivo existe
        if not os.path.exists(input_file):
            logging.error(f"Arquivo de legenda não existe: {input_file}")
            return False
            
        # Verificar se podemos ler o arquivo
        try:
            with open(input_file, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
        except Exception as e:
            logging.error(f"Erro ao ler o arquivo {input_file}: {e}")
            return False
        
        # Separar o conteúdo em blocos (numeração, timestamp, texto)
        blocks = re.split(r'\n\s*\n', content)
        translated_blocks = []
        
        for block in blocks:
            if not block.strip():
                continue
            
            lines = block.strip().split('\n')
            if len(lines) < 3:  # Um bloco válido tem pelo menos 3 linhas
                translated_blocks.append(block)
                continue
            
            # Identificar o número e o timestamp
            number = lines[0]
            timestamp = lines[1]
            
            # Juntar o texto para tradução
            text_to_translate = '\n'.join(lines[2:])
            
            # Traduzir o texto
            translated_text = translate_text(text_to_translate)
            
            # Reconstruir o bloco com o texto traduzido
            translated_block = f"{number}\n{timestamp}\n{translated_text}"
            translated_blocks.append(translated_block)
            
            # Pequeno delay para não sobrecarregar a API
            time.sleep(0.1)
        
        # Escrever a legenda traduzida
        try:
            # Garantir que o diretório de saída existe
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write('\n\n'.join(translated_blocks))
            
            logging.info(f"Legenda traduzida salva em: {output_file}")
            return True
        except Exception as e:
            logging.error(f"Erro ao salvar legenda traduzida {output_file}: {e}")
            return False
            
    except Exception as e:
        logging.error("Erro ao traduzir legenda %s: %s", input_file, e)
        return False

def process_file(mkv_file):
    """Processa um arquivo .mkv"""
    logging.info(f"Processando arquivo: {mkv_file}")
    
    base_path = os.path.splitext(mkv_file)[0]
    en_subtitle = f"{base_path}.en.srt"
    pt_br_subtitle = f"{base_path}.pt-BR.srt"
    
    # Verificar se a legenda em português já existe
    if os.path.exists(pt_br_subtitle):
        logging.info("Legenda em PT-BR já existe: %s", pt_br_subtitle)
        return
    
    # Verificar se a legenda em inglês já existe
    if not os.path.exists(en_subtitle):
        # Obter informações das faixas de legenda
        subtitle_tracks = get_subtitle_tracks(mkv_file)
        
        if not subtitle_tracks:
            logging.warning(f"Nenhuma faixa de legenda encontrada em {mkv_file}")
            return
            
        logging.info(f"Faixas de legenda encontradas: {subtitle_tracks}")
        
        # Verificar se há legendas em português
        has_portuguese = any(
            track.get("language") in ["por", "pt", "pt-BR", "pt-br", "portuguese", "portugues"] 
            for track in subtitle_tracks
        )
        
        if has_portuguese:
            logging.info("Arquivo já possui legenda em português: %s", mkv_file)
            return
        
        # Encontrar a primeira faixa de legendas em inglês de texto
        english_text_track = None
        sup_tracks = []
        
        for track in subtitle_tracks:
            language = track.get("language")
            codec = track.get("codec", "").lower()
            
            logging.info(f"Avaliando faixa: ID={track.get('id')}, Idioma={language}, Codec={codec}")
            
            if language in ["eng", "en", "english"]:
                if "sup" in codec or "hdmv" in codec or "pgs" in codec:
                    sup_tracks.append(track)
                else:
                    english_text_track = track
                    break
        
        # Se só houver faixas SUP em inglês, registrar e pular
        if not english_text_track and sup_tracks:
            with open(SUP_LOG_FILE, "a") as log:
                log.write(f"{mkv_file}\n")
            logging.info("Arquivo com legendas SUP: %s", mkv_file)
            return
        
        # Se não houver faixas em inglês, pular
        if not english_text_track:
            logging.info("Nenhuma legenda em inglês encontrada: %s", mkv_file)
            return
        
        # Extrair a legenda em inglês
        logging.info("Extraindo legenda em inglês: %s (Faixa ID: %s)", mkv_file, english_text_track["id"])
        if not extract_subtitle(mkv_file, english_text_track["id"], en_subtitle):
            logging.error("Falha ao extrair legenda em inglês: %s", mkv_file)
            return
    else:
        logging.info("Legenda em inglês já extraída: %s", en_subtitle)
    
    # Traduzir a legenda
    logging.info("Traduzindo legenda: %s", en_subtitle)
    if translate_subtitle(en_subtitle, pt_br_subtitle):
        logging.info("Legenda traduzida com sucesso: %s", pt_br_subtitle)
    else:
        logging.error("Falha ao traduzir legenda: %s", en_subtitle)

def main():
    """Função principal"""
    logging.info("Iniciando o processo de tradução de legendas")
    
    # Certificar-se de que os diretórios existem
    os.makedirs(os.path.dirname(SUP_LOG_FILE), exist_ok=True)
    
    # Obter e logar idiomas suportados
    supported_languages = get_supported_languages()
    
    # Testar a conexão com a API de tradução
    try:
        test_response = requests.post(
            TRANSLATE_API_URL,
            data=json.dumps({"q": "Hello", "source": "en", "target": "pt-BR"}),
            headers={"Content-Type": "application/json"}
        )
        logging.info(f"Teste de conexão com a API de tradução: {test_response.status_code}")
        logging.info(f"Resposta do teste: {test_response.text}")
    except Exception as e:
        logging.error(f"Erro ao testar conexão com a API: {e}")
    
    # Obter todos os arquivos .mkv
    mkv_files = get_all_mkv_files()
    
    # Processar cada arquivo
    for mkv_file in tqdm(mkv_files, desc="Processando arquivos"):
        process_file(mkv_file)
    
    logging.info("Processo de tradução de legendas concluído")

if __name__ == "__main__":
    main()
