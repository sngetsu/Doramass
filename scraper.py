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

# Regex corregido: Se detiene si ve espacios, comillas, barras invertidas, comas o llaves de JSON
CUALQUIER_M3U8 = r'(https?://[^\s"\'<>\\,;{}[\]]+?\.m3u8[^\s"\'<>\\,;{}[\]]*)'

def extraer_video_y_datos(url_episodio):
    """Entra a la página del episodio, saca el título real y busca cualquier m3u8"""
    try:
        resp = requests.get(url_episodio, headers=HEADERS, timeout=10)
        if resp.status_code != 200: return None, False
        
        html = resp.text
        soup = BeautifulSoup(html, 'html.parser')

        # 1. EXTRAER TÍTULO (Grupo y Episodio)
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

        # 2. BUSCAR CUALQUIER M3U8 EN EL HTML
        video_url = None
        match_m3u8 = re.search(CUALQUIER_M3U8, html)
        
        if match_m3u8:
            # Limpiamos barras escapadas de JSON y comillas HTML por si acaso
            video_url = match_m3u8.group(1).replace('\\/', '/').replace('&quot;', '')
        else:
            # 3. SI NO ESTÁ, BUSCAR DENTRO DE LOS IFRAMES
            iframes = soup.find_all('iframe')
            for iframe in iframes:
                src = iframe.get('src', '')
                if not src.startswith('http'): continue
                
                try:
                    resp_iframe = requests.get(src, headers=HEADERS, timeout=10)
                    match_iframe = re.search(CUALQUIER_M3U8, resp_iframe.text)
                    if match_iframe:
                        video_url = match_iframe.group(1).replace('\\/', '/').replace('&quot;', '')
                        break
                except:
                    continue

        if video_url:
            # Comprobamos si es del dominio que queremos
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

    # Asegurarnos de que los archivos maestros existan antes de escribir
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

    # Abrimos AMBOS archivos en modo "a" (Append / Añadir al final)
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
