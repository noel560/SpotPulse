import json
import os
import subprocess
import shutil
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich.align import Align
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
import requests
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
import time
from datetime import datetime
import platform
import re

console = Console()

APP_NAME = "SpotPulse"
DEFAULT_DATA = {
    "playlist": "",
    "download_path": ""
}

def get_app_dir():
    home = os.path.expanduser("~")
    system = platform.system()
    
    if system == "Windows":
        return os.path.join(os.getenv("LOCALAPPDATA", os.path.join(home, "AppData", "Local")), APP_NAME)
    elif system == "Darwin":
        return os.path.join(home, "Library", "Application Support", APP_NAME)
    else:
        return os.path.join(home, ".local", "share", APP_NAME.lower())

def ensure_binaries():
    app_dir = get_app_dir()
    system = platform.system()
    
    yt_name = "yt-dlp.exe" if system == "Windows" else "yt-dlp"
    ff_name = "ffmpeg.exe" if system == "Windows" else "ffmpeg"
    
    yt_path = os.path.join(app_dir, yt_name)
    ff_path = os.path.join(app_dir, ff_name)

    if os.path.exists(yt_path) and os.path.exists(ff_path):
        return yt_path, ff_path

    urls = {
        "Windows": {
            "yt": "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe",
            "ff": "https://github.com/ffbinaries/ffbinaries-prebuilt/releases/download/v4.4.1/ffmpeg-4.4.1-win-64.zip"
        },
        "Linux": {
            "yt": "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp",
            "ff": "https://github.com/ffbinaries/ffbinaries-prebuilt/releases/download/v4.4.1/ffmpeg-4.4.1-linux-64.zip"
        }
    }

    current_urls = urls.get(system, urls["Windows"])

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=50, complete_style="#1DB954", finished_style="#1ed760", pulse_style="#1DB954"),
        TextColumn("{task.percentage:>3.0f}%"),
        console=console
    ) as progress:

        if not os.path.exists(yt_path):
            task1 = progress.add_task("Downloading yt-dlp...", total=100)
            r = requests.get(current_urls["yt"], stream=True)
            with open(yt_path, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
                    progress.update(task1, advance=(len(chunk)/int(r.headers.get('content-length', 1))*100))
            if system != "Windows": os.chmod(yt_path, 0o755)

        if not os.path.exists(ff_path):
            task2 = progress.add_task("Downloading ffmpeg...", total=100)
            zip_path = ff_path + ".zip"
            r = requests.get(current_urls["ff"], stream=True)
            with open(zip_path, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
                    progress.update(task2, advance=(len(chunk)/int(r.headers.get('content-length', 1))*100))
            
            import zipfile
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extract(ff_name, app_dir)
            os.remove(zip_path)
            if system != "Windows": os.chmod(ff_path, 0o755)

    return yt_path, ff_path

def get_data_path():
    app_dir = get_app_dir()
    os.makedirs(app_dir, exist_ok=True)
    return os.path.join(app_dir, "data.json")

def get_downloads_path():
    data = load_data(get_data_path())
    custom_path = data.get("download_path", "")
    
    if custom_path and os.path.isdir(custom_path):
        os.makedirs(custom_path, exist_ok=True)
        return custom_path
    
    # Fallback
    app_dir = get_app_dir()
    downloads_dir = os.path.join(app_dir, "downloads")
    os.makedirs(downloads_dir, exist_ok=True)
    return downloads_dir

def get_logs_path():
    app_dir = get_app_dir()
    logs_dir = os.path.join(app_dir, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    return logs_dir

def get_latest_log_path():
    """Megkeresi a logs mappában a legutóbbi .json fájlt dátum szerint"""
    logs_dir = get_logs_path()
    json_files = [f for f in os.listdir(logs_dir) if f.endswith('.json')]
    if not json_files:
        return None
    latest_file = max(json_files, key=lambda f: os.path.getmtime(os.path.join(logs_dir, f)))
    return os.path.join(logs_dir, latest_file)

def load_data(path):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_DATA, f, indent=4)
        return DEFAULT_DATA.copy()

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def change_download_folder():
    current_path = get_downloads_path()
    console.print(f"[#a0d8ff]Current download folder:[/#a0d8ff]")
    console.print(f"[#e0e0e0]{current_path}[/#e0e0e0]\n")
    
    console.print("[#a0d8ff]Enter new download folder path (absolute path, e.g. D:\\Music or /home/user/Music):[/#a0d8ff]")
    console.print("[dim]Or enter 'RESET' to set it back to the default path.[/dim]")
    new_path = Prompt.ask("[#f0f0f0]New path[/#f0f0f0]").strip()
    
    if not new_path:
        console.print("[#ff4d4d]No path entered. No changes made.[/#ff4d4d]")
        return
    
    if new_path == "RESET":
        data_path = get_data_path()
        data = load_data(data_path)
        data["download_path"] = ""
        save_data(data_path, data)

        console.print("[bold #2ecc71]Download folder has been changed back to default.[/bold #2ecc71]")
        return
    
    # Ellenőrizzük és létrehozzuk, ha kell
    try:
        os.makedirs(new_path, exist_ok=True)
        # Teszt írás (hogy biztosan írható legyen)
        test_file = os.path.join(new_path, ".test_write")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        
        # Mentsük a data.json-ba
        data_path = get_data_path()
        data = load_data(data_path)
        data["download_path"] = new_path
        save_data(data_path, data)
        
        console.print(f"\n[bold #2ecc71]Download folder changed to:[/bold #2ecc71]")
        console.print(f"[#2ecc71]{new_path}[/#2ecc71]")
    except Exception as e:
        console.print(f"[bold #ff4d4d]Invalid or inaccessible path:[/bold #ff4d4d] {e}")
        console.print("[dim]Make sure the path exists and you have write permission.[/dim]")

def prompt_playlist(current=""):
    data_path = get_data_path()

    while True:
        os.system('cls' if os.name == 'nt' else 'clear')

        header = Align.center(
            "[bold #4da6ff]🎵 Spotify Playlist Setup[/bold #4da6ff]",
            vertical="middle"
        )

        console.print(
            Panel(
                header,
                border_style="#0078d4",
                padding=(1, 4),
                expand=False
            )
        )

        if current:
            console.print(f"[#a0d8ff]Current playlist:[/#a0d8ff]")
            console.print(f"[dim #e0e0e0]{current}[/dim #e0e0e0]\n")

        console.print("[#a0d8ff]Example:[/#a0d8ff]")
        console.print(
            "[dim #e0e0e0]https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M[/dim #e0e0e0]\n"
        )

        new_playlist = Prompt.ask(
            "[#f0f0f0]🔗 Paste Spotify playlist URL[/#f0f0f0]"
        ).strip()

        if new_playlist.startswith("https://open.spotify.com/"):
            return new_playlist

        console.print("\n[bold #ff4d4d]❌ Invalid Spotify URL[/bold #ff4d4d]")
        console.print("[dim]Press Enter to try again...[/dim]")
        input()

def extract_tracks_from_playlist(playlist_url):
    console.print("[bold #4da6ff]Launching headless browser...[/bold #4da6ff]")

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1280,1200")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    tracks = []
    seen = set()
    expected_total = 0
    prev_row_count = 0

    try:
        driver.get(playlist_url)
        time.sleep(6)

        # Cookies
        try:
            accept_btn = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'ELFOGADOM') or contains(text(), 'Accept') or @id='onetrust-accept-btn-handler']"))
            )
            accept_btn.click()
            time.sleep(3)
        except:
            pass

        WebDriverWait(driver, 40).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-testid="tracklist-row"]'))
        )
        console.print("[green]Songs loaded[/green]")

        # Sidebar hide
        try:
            driver.execute_script("var s = document.querySelector('#Desktop_LeftSidebar_Id'); if (s) s.style.display = 'none';")
        except:
            pass

        time.sleep(3)

        try:
            header_selectors = [
                'h1[data-testid="entityTitle"]',
                'p[data-testid="playlist-subtitle"]',
                'div[data-testid="playlist-header-description"] span',
                'div[data-testid="playlist-header"] p'
            ]
            header_text = ""
            for sel in header_selectors:
                try:
                    header_text = driver.find_element(By.CSS_SELECTOR, sel).text
                    break
                except:
                    continue
            match = re.search(r'(\d+)', header_text.replace(',', ''))
            if match:
                expected_total = int(match.group(1))
        except:
            pass

        no_new_added = 0
        max_no_new = 15
        pause_time = 7.0
        total_songs = None

        try:
            elements = driver.find_elements(By.CSS_SELECTOR, 'span[data-encore-id="text"]')
            
            for el in elements:
                text = el.text.lower().strip()
                match = re.search(r'(\d+)\s*(dal|song|track|szám)', text)
                if match:
                    total_songs = int(match.group(1))
                    console.print(f"[dim]Detected playlist size: {total_songs} songs[/dim]")
                    break
            
            if not total_songs:
                xpath_selector = "//span[contains(text(), 'dal') or contains(text(), 'song') or contains(text(), 'track')]"
                el = driver.find_element(By.XPATH, xpath_selector)
                match = re.search(r'(\d+)', el.text)
                if match:
                    total_songs = int(match.group(1))
                    console.print(f"[dim]Detected playlist size (via XPath): {total_songs} songs[/dim]")
        except Exception as e:
            console.print(f"[dim]Playlist size detection fallback: {str(e)}[/dim]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=50, complete_style="#1DB954", finished_style="#1ed760", pulse_style="#1DB954"),
            TextColumn("{task.completed}/{task.total}"),
            transient=True,
            console=console
        ) as progress:
            
            task = progress.add_task("Extracting songs", total=total_songs or None)

            while True:
                rows = driver.find_elements(By.CSS_SELECTOR, 'div[data-testid="tracklist-row"]')
                current_count = len(rows)
                new_added_this_round = 0

                for row in rows:
                    try:
                        title = row.find_element(By.CSS_SELECTOR, 'a[data-testid="internal-track-link"] div[dir="auto"]').text.strip()
                        artists = ', '.join(a.text.strip() for a in row.find_elements(By.CSS_SELECTOR, 'div[role="gridcell"][aria-colindex="2"] a[href^="/artist/"]') if a.text.strip())
                        key = (title, artists)
                        if title and artists and key not in seen:
                            seen.add(key)
                            tracks.append({'title': title, 'artists': artists})
                            new_added_this_round += 1
                            progress.advance(task, 1)
                    except:
                        pass

                if new_added_this_round == 0:
                    no_new_added += 1
                else:
                    no_new_added = 0

                remaining = None
                if total_songs:
                    remaining = total_songs - len(tracks)

                if new_added_this_round == 0:
                    console.print("[dim]No new songs added this round → stopping[/dim]")
                    break

                if total_songs and len(tracks) >= total_songs:
                    console.print("[bold #2ecc71]All songs extracted[/bold #2ecc71]")
                    break

                if remaining is not None and new_added_this_round < remaining and no_new_added >= 3:
                    console.print("[dim]Playlist end reached (partial add)[/dim]")
                    break


                # Scroll
                driver.execute_script("""
                    var c = document.querySelector('.main-view-container__scroll-node-child, div[data-testid="playlist-tracklist"], main') || document.body;
                    c.scrollTop = c.scrollHeight;
                """)
                time.sleep(0.5)
                if rows:
                    rows[-1].location_once_scrolled_into_view
                time.sleep(0.5)
                driver.execute_script("window.scrollBy(0, -500); window.scrollBy(0, 500);")
                body = driver.find_element(By.TAG_NAME, 'body')
                body.send_keys(Keys.END * 3)

                time.sleep(pause_time)

        return tracks

    except Exception as e:
        console.print(f"[bold #ff4d4d]Error: {str(e)}[/bold #ff4d4d]")
        return []
    finally:
        driver.quit()

def download_track(original_query, track_info):
    download_dir = get_downloads_path()

    app_dir = get_app_dir()
    system = platform.system()
    yt_dlp_bin = os.path.join(app_dir, "yt-dlp.exe" if system == "Windows" else "yt-dlp")

    os.makedirs(download_dir, exist_ok=True)

    before_files = set(os.listdir(download_dir))

    query_variations = [
        f"ytsearch:{original_query} official audio",
        f"ytsearch5:{original_query} song",
        f"ytsearch:{original_query.replace('Remix', '').strip()}",
    ]

    success = False

    for idx, query in enumerate(query_variations, 1):
        cmd = [
            yt_dlp_bin,
            '--ffmpeg-location', app_dir,
            '--extract-audio',
            '--audio-format', 'mp3',
            '--audio-quality', '0',
            '--format', 'bestaudio/best',
            '--embed-thumbnail',
            '--add-metadata',
            '--no-playlist',
            '--playlist-end', '1',
            '--match-filter', 'duration < 600',
            '--no-overwrites',
            '--output', os.path.join(download_dir, '%(artist)s - %(title)s.%(ext)s'),
            '--restrict-filenames',
            query
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            success = True
            break
        except subprocess.CalledProcessError:
            continue

    if not success:
        console.print(f"[bold #ff4d4d]Failed after retries: {track_info['title']} - {track_info['artists']}[/bold #ff4d4d]")
        return False

    time.sleep(3)
    after_files = set(os.listdir(download_dir))
    new_files = after_files - before_files

    if not new_files:
        console.print(f"[#ff4d4d]Warning: No new file detected for {track_info['title']}[/#ff4d4d]")
        return True

    downloaded_file = list(new_files)[0]
    old_path = os.path.join(download_dir, downloaded_file)

    safe_artists = track_info['artists'].replace('/', ',').strip()
    safe_title = track_info['title'].replace('/', '-').strip()
    new_filename = f"{safe_artists} - {safe_title}.mp3"
    new_path = os.path.join(download_dir, new_filename)

    counter = 1
    while os.path.exists(new_path):
        new_filename = f"{safe_artists} - {safe_title} ({counter}).mp3"
        new_path = os.path.join(download_dir, new_filename)
        counter += 1

    try:
        os.rename(old_path, new_path)
        console.print(f"[#2ecc71]Downloaded: {track_info['artists']} - {track_info['title']}[/#2ecc71]")
    except Exception as e:
        pass

    return success

def show_main_menu():
    data_path = get_data_path()
    data = load_data(data_path)
    playlist = data.get("playlist", "")

    while True:
        os.system('cls' if os.name == 'nt' else 'clear')

        header = Align.center(
            "[bold #4da6ff]🎧 SpotPulse[/bold #4da6ff]",
            vertical="middle"
        )

        console.print(
            Panel(
                header,
                border_style="#0078d4",
                padding=(1, 4),
                expand=False
            )
        )

        console.print("[#a0d8ff]Current playlist:[/#a0d8ff]")
        if playlist:
            console.print(f"[#e0e0e0]{playlist}[/#e0e0e0]\n")
        else:
            console.print("[#ff4d4d]No playlist set yet[/bold #ff4d4d]\n")

        console.print("[#f0f0f0]What would you like to do?[/ #f0f0f0]")
        console.print("  [bold #4da6ff]1[/bold #4da6ff]  Download all songs from playlist")
        console.print("  [bold #4da6ff]2[/bold #4da6ff]  Download new songs from playlist")
        console.print("  [bold #4da6ff]3[/bold #4da6ff]  Change playlist")
        console.print("  [bold #4da6ff]4[/bold #4da6ff]  Change download folder")
        console.print("  [bold #4da6ff]5[/bold #4da6ff]  Exit\n")

        choice = Prompt.ask(
            "[#f0f0f0]Enter your choice (1-5)[/#f0f0f0]",
            choices=["1", "2", "3", "4", "5"],
            default="1"
        )

        if choice == "1" or choice == "2":
            if not playlist:
                console.print("\n[bold #ff4d4d]No playlist set! Please set one first.[/bold #ff4d4d]")
                console.print("[dim]Press Enter...[/dim]")
                input()
                continue
            
            console.print("\n[bold #4da6ff]Extracting tracks from playlist...[/bold #4da6ff]")
            tracks = extract_tracks_from_playlist(playlist)
            
            if not tracks:
                console.print("[bold #ff4d4d]No tracks found or error scraping.[/bold #ff4d4d]")
                console.print("[dim]Press Enter...[/dim]")
                input()
                continue
            
            console.print(f"[#a0d8ff]Found {len(tracks)} tracks in playlist:[/#a0d8ff]")
            for i, track in enumerate(tracks, 1):
                console.print(f"  {i}. [#e0e0e0]{track['title']} - {track['artists']}[/#e0e0e0]")

            # Ha "new songs" mód (choice 2), szűrjük a már ismert trackeket
            to_download = tracks
            if choice == "2":
                latest_log = get_latest_log_path()
                if latest_log:
                    try:
                        with open(latest_log, "r", encoding="utf-8") as f:
                            previous = json.load(f)
                        previous_titles = set(previous.keys())
                        to_download = [t for t in tracks if t['title'] not in previous_titles]
                        console.print(f"[#a0d8ff]Found {len(to_download)} new tracks (not in last log).[/ #a0d8ff]")
                    except Exception as e:
                        console.print(f"[#ff4d4d]Could not load previous log: {e}. Downloading all.[/#ff4d4d]")
                else:
                    console.print("[#a0d8ff]No previous log found. Downloading all.[/#a0d8ff]")

            if not to_download:
                console.print("[#2ecc71]No new songs to download![/#2ecc71]")
                console.print("[dim]Press Enter...[/dim]")
                input()
                continue

            confirm = Prompt.ask(f"\n[#f0f0f0]Download {len(to_download)} song(s)? (y/n)[/#f0f0f0]", default="y")
            if confirm.lower() != "y":
                continue
            
            success_count = 0
            download_dir = get_downloads_path()

            # Mappa ürítés
            for item in os.listdir(download_dir):
                item_path = os.path.join(download_dir, item)
                try:
                    if os.path.isfile(item_path):
                        os.remove(item_path)
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                except:
                    pass
            
            music_list = {}
            for track in to_download:
                search_query = f"{track['artists']} {track['title']}"  # jobb sorrend
                console.print(f"[#4da6ff]Downloading: {track['artists']} - {track['title']}[/#4da6ff]")

                music_list[track["title"]] = {
                    "artist": track["artists"],
                    "downloaded": False
                }
                
                if download_track(search_query, track):
                    success_count += 1
                    music_list[track["title"]]["downloaded"] = True
                else:
                    console.print("[#ff4d4d]Failed to download this track.[/#ff4d4d]")

            # Log mentés (csak a most feldolgozottakat)
            if music_list:
                logs_dir = get_logs_path()
                timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
                log_file = os.path.join(logs_dir, f"export_{timestamp}.json")
                with open(log_file, "w", encoding="utf-8") as f:
                    json.dump(music_list, f, ensure_ascii=False, indent=4)
                #console.print(f"[dim]Log saved: export_{timestamp}.json[/dim]")

            # Nem .mp3 törlése
            for file in os.listdir(download_dir):
                file_path = os.path.join(download_dir, file)
                if os.path.isfile(file_path) and not file.lower().endswith('.mp3'):
                    try:
                        os.remove(file_path)
                    except:
                        pass

            console.print(f"\n[bold #2ecc71]Downloaded {success_count}/{len(to_download)} new track(s) successfully![/bold #2ecc71]")
            console.print("[dim]Press Enter to continue...[/dim]")
            input()

        elif choice == "3":
            new_url = prompt_playlist(current=playlist)
            data["playlist"] = new_url
            save_data(data_path, data)
            playlist = new_url
            console.print("\n[bold #2ecc71]✔ Playlist updated successfully![/bold #2ecc71]")
            console.print("[dim]Press Enter...[/dim]")
            input()

        elif choice == "4":
            change_download_folder()
            console.print("[dim]Press Enter to continue...[/dim]")
            input()

        elif choice == "5":
            console.print("\n[bold #a0d8ff]Goodbye! 👋[/bold #a0d8ff]")
            break

def main():
    ensure_binaries()
    data_path = get_data_path()
    data = load_data(data_path)
    playlist = data.get("playlist", "")

    if not playlist:
        console.print("[#ff4d4d]No playlist configured yet.[/#ff4d4d]")
        new_url = prompt_playlist()
        data["playlist"] = new_url
        save_data(data_path, data)

    show_main_menu()

if __name__ == "__main__":
    main()