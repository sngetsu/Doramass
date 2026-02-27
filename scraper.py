import requests
import re
import time
import random
import sys
import os
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

# --- CONFIGURACIÓN ---
SITEMAP_URL = "https://doramedplay.com/episodes-sitemap1.xml"
CARPETA_SALIDA = "playlists"
ARCHIVO_VALIDOS = os.path.join(CARPETA_SALIDA, "doramed_validos.m3u")
ARCHIVO_OTROS = os.path.join(CARPETA_SALIDA, "doramed_expirables.m3u")

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://doramedplay.com/',
    'Accept-Language': 'es-ES,es;q=0.9'
}

DOMINIO_OBJETIVO = "video.doramedplay.net"

# Regex: Se detiene en espacios, comillas, llaves JSON, comas, etc.
CUALQUIER_M3U8 = r'(https?://[^\s"\'<>\\,;{}[\]]+?\.m3u8[^\s"\'<>\\,;{}[\]]*)'


def encontrar_m3u8_en_html(html_texto):
    """Limpia el código de escapes JSON y extrae el mejor m3u8"""
    if not html_texto: return None

    # 1. TRUCO CLAVE: Quitar escapes de JSON ( \/ pasa a ser / )
    html_limpio = html_texto.replace('\\/', '/').replace('\\u0026', '&')
    
    # 2. Buscar todas las coincidencias
    matches = re.findall(CUALQUIER_M3U8, html_limpio)
    
    if not matches:
        return None
        
    # 3. Priorizar siempre el dominio objetivo (PeerTube)
    for url in matches:
        if DOMINIO_OBJETIVO in url:
            return url
            
    # 4. Si no hay del objetivo, devolver el primero encontrado (ej: OK.ru)
    return matches[0]


def extraer_video_y_datos(url_episodio):
    """Entra a la página del episodio, saca el título real y busca cualquier m3u8"""
    try:
        resp = requests.get(url_episodio, headers=HEADERS, timeout=10)
        if resp.status_code != 200: return None, False
        
        html = resp.text
        soup = BeautifulSoup(html, 'html.parser')

        # --- EXTRAER TÍTULO ---
        page_title = soup.title.string if soup.title else ""
        clean_title = page_title.replace('- Doramed Play', '').strip()
        
        grupo = "Doramed"
        episodio = "Episodio"
        
        match_title = re.search(r'^(.*?)\s*[:\-]?\s*(\d+x\d+)', clean_title)
        if match_title:
            grupo = match_title.group(1).strip()
            episodio = match_title.group(2).strip()
        else:
            grupo = clean_title

        imagen = ""
        meta_img = soup.find('meta', property='og:image')
        if meta_img:
            imagen = meta_img['content']

        # --- BUSCAR VIDEO EN HTML PRINCIPAL ---
        video_url = encontrar_m3u8_en_html(html)

        # --- BUSCAR EN IFRAMES (Si no encontramos el objetivo aún) ---
        if not video_url or DOMINIO_OBJETIVO not in video_url:
            iframes = soup.find_all('iframe')
            for iframe in iframes:
                src = iframe.get('src', '')
                if not src.startswith('http'): continue
                
                try:
                    resp_iframe = requests.get(src, headers=HEADERS, timeout=10)
                    url_iframe = encontrar_m3u8_en_html(resp_iframe.text)
                    
                    if url_iframe:
                        # Si es del dominio objetivo, lo coronamos y salimos
                        if DOMINIO_OBJETIVO in url_iframe:
                            video_url = url_iframe
                            break
                        # Si no teníamos nada, guardamos este alternativo
                        elif not video_url:
                            video_url = url_iframe
                except:
                    continue

        # --- RETORNAR RESULTADO ---
        if video_url:
            es_valido = DOMINIO_OBJETIVO in video_url
            linea = f'#EXTINF:-1 tvg-logo="{imagen}" group-title="{grupo}", {episodio}\n{video_url}\n'
            return linea, es_valido
            
        return None, False
    except Exception as e:
        return None, False

def inicializar_archivo(ruta):
    """Crea el archivo con la cabecera M3U si no existe"""
    if not os.path.exists(ruta):
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")

def obtener_urls_sitemap():
    print(f"📥 Descargando sitemap: {SITEMAP_URL}")
    try:
        resp = requests.get(SITEMAP_URL, headers=HEADERS, timeout=15)
        root = ET.fromstring(resp.content)
        return [elem.text for elem in root.findall(".//{*}loc")]
    except Exception as e:
        print(f"❌ Error leyendo sitemap: {e}")
        return []

def main():
    start_index = int(os.getenv('START_INDEX', 0))
    end_index = int(os.getenv('END_INDEX', 100))

    if not os.path.exists(CARPETA_SALIDA):
        os.makedirs(CARPETA_SALIDA)

    inicializar_archivo(ARCHIVO_VALIDOS)
    inicializar_archivo(ARCHIVO_OTROS)

    urls_totales = obtener_urls_sitemap()
    if not urls_totales:
        sys.exit(1)

    total_disponible = len(urls_totales)
    print(f"📊 Se encontraron {total_disponible} episodios en total.")
    
    if end_index > total_disponible:
        end_index = total_disponible

    urls_lote = urls_totales[start_index:end_index]
    print(f"--- RANGO: {start_index} a {end_index} ({len(urls_lote)} URLs) ---")

    with open(ARCHIVO_VALIDOS, "a", encoding="utf-8") as f_validos, \
         open(ARCHIVO_OTROS, "a", encoding="utf-8") as f_otros:
        
        for i, url in enumerate(urls_lote):
            idx_real = start_index + i + 1
            print(f"   [{idx_real}/{end_index}] Procesando... ", end="")
            
            linea, es_valido = extraer_video_y_datos(url)
            
            if linea:
                if es_valido:
                    print("✅ (Dominio OK)")
                    f_validos.write(linea)
                    f_validos.flush()
                else:
                    print("⚠️ (Otro dominio)")
                    f_otros.write(linea)
                    f_otros.flush()
            else:
                print("❌ Sin video")
            
            time.sleep(random.uniform(1.0, 2.0))

if __name__ == "__main__":
    main()
