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
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://doramedplay.com/',
    'Accept-Language': 'es-ES,es;q=0.9'
}

# Solo aceptamos el dominio requerido por ti
DOMINIO_VALIDO = r'(https://video\.doramedplay\.net/[^\s"\'<>]+?\.m3u8)'

def extraer_video_y_datos(url_episodio):
    """Entra a la página del episodio, saca el título real y busca el m3u8"""
    try:
        resp = requests.get(url_episodio, headers=HEADERS, timeout=10)
        if resp.status_code != 200: return None
        
        html = resp.text
        soup = BeautifulSoup(html, 'html.parser')

        # 1. EXTRAER TÍTULO (Grupo y Episodio)
        # Ejemplo: "<title>วิมานสีทอง: 1x3 - Doramed Play</title>"
        page_title = soup.title.string if soup.title else ""
        clean_title = page_title.replace('- Doramed Play', '').strip()
        
        grupo = "Doramed"
        episodio = "Episodio"
        
        # Separar por los formatos "Nombre: 1x3" o "Nombre 1x3"
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

        # 2. BUSCAR M3U8 EN EL CÓDIGO PRINCIPAL
        video_url = None
        match_m3u8 = re.search(DOMINIO_VALIDO, html)
        
        if match_m3u8:
            video_url = match_m3u8.group(1).replace('\\/', '/')
        else:
            # 3. SI NO ESTÁ, BUSCAR DENTRO DE LOS IFRAMES (Típico de Dooplay)
            iframes = soup.find_all('iframe')
            for iframe in iframes:
                src = iframe.get('src', '')
                if not src.startswith('http'):
                    continue # Ignorar iframes sin URL válida
                
                try:
                    # Entramos al iframe
                    resp_iframe = requests.get(src, headers=HEADERS, timeout=10)
                    html_iframe = resp_iframe.text
                    match_iframe = re.search(DOMINIO_VALIDO, html_iframe)
                    if match_iframe:
                        video_url = match_iframe.group(1).replace('\\/', '/')
                        break # Encontrado, salimos del bucle
                except:
                    continue

        if video_url:
            # Formato: #EXTINF:-1 tvg-logo="..." group-title="Grupo", Episodio
            return f'#EXTINF:-1 tvg-logo="{imagen}" group-title="{grupo}", {episodio}\n{video_url}\n'
        return None
    except Exception as e:
        return None

def obtener_urls_sitemap():
    """Descarga y parsea el XML para sacar todas las URLs"""
    print(f"📥 Descargando sitemap: {SITEMAP_URL}")
    try:
        resp = requests.get(SITEMAP_URL, headers=HEADERS, timeout=15)
        root = ET.fromstring(resp.content)
        # Buscar todas las etiquetas <loc> ignorando namespaces
        urls = [elem.text for elem in root.findall(".//{*}loc")]
        return urls
    except Exception as e:
        print(f"❌ Error leyendo sitemap: {e}")
        return []

def main():
    # 1. Obtener parámetros del Workflow (Por defecto 0 a 100)
    start_index = int(os.getenv('START_INDEX', 0))
    end_index = int(os.getenv('END_INDEX', 100))

    if not os.path.exists(CARPETA_SALIDA):
        os.makedirs(CARPETA_SALIDA)

    urls_totales = obtener_urls_sitemap()
    if not urls_totales:
        sys.exit(1)

    total_disponible = len(urls_totales)
    print(f"📊 Se encontraron {total_disponible} episodios en total.")
    
    # Ajustar el límite final si nos pasamos
    if end_index > total_disponible:
        end_index = total_disponible

    # Recortar la lista al lote solicitado
    urls_lote = urls_totales[start_index:end_index]
    
    archivo_destino = os.path.join(CARPETA_SALIDA, f"doramed_{start_index}_a_{end_index}.m3u")
    print(f"--- RANGO: {start_index} a {end_index} ({len(urls_lote)} URLs) ---")
    print(f"💾 Guardando en: {archivo_destino}")

    with open(archivo_destino, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        
        for i, url in enumerate(urls_lote):
            idx_real = start_index + i + 1
            print(f"   [{idx_real}/{end_index}] Procesando... ", end="")
            
            linea = extraer_video_y_datos(url)
            
            if linea:
                print("✅ Encontrado")
                f.write(linea)
                f.flush()
            else:
                print("❌ Sin video válido")
            
            # Pausa humana (1 a 2 segundos)
            time.sleep(random.uniform(1.0, 2.0))

if __name__ == "__main__":
    main()
