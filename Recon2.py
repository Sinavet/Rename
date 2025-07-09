import streamlit as st
import os
import zipfile
import tempfile
from pathlib import Path
from PIL import Image
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIF_SUPPORT = True
except ImportError:
    HEIF_SUPPORT = False
    st.warning("Для поддержки HEIC/HEIF установите пакет pillow-heif: pip install pillow-heif")
import shutil
from io import BytesIO
import requests
import uuid
from rename import process_rename_mode
from convers import process_convert_mode
from water import process_watermark_mode
from utils import filter_large_files, SUPPORTED_EXTS, MAX_SIZE_MB

# Универсальный ресемплинг для предпросмотра
from PIL import Image
RESAMPLING = getattr(getattr(Image, 'Resampling', Image), 'LANCZOS', getattr(Image, 'LANCZOS', getattr(Image, 'NEAREST', 0)))

st.set_page_config(page_title="PhotoFlow: Умная обработка изображений", page_icon="📸")
st.markdown("""
<style>
    body, .stApp {
        background-color: #181c24 !important;
        color: #f3f6fa !important;
    }
    .big-title {
        font-size:2.2em; font-weight:700; color:#f3f6fa; margin-bottom:0.2em;
        text-shadow: 0 2px 8px #00000044;
    }
    .subtitle {
        font-size:1.2em; color:#b0b8c9; margin-bottom:1em;
    }
    .stButton>button, .stDownloadButton>button {
        font-size:1.1em;
        background: linear-gradient(90deg, #2d3748 0%, #4a5568 100%);
        color: #f3f6fa;
        border: none;
        border-radius: 6px;
        box-shadow: 0 2px 8px #00000022;
        transition: background 0.2s;
    }
    .stButton>button:hover, .stDownloadButton>button:hover {
        background: linear-gradient(90deg, #4a5568 0%, #2d3748 100%);
        color: #fff;
    }
    .stTextInput>div>input, .stFileUploader>div>input {
        background: #232837;
        color: #f3f6fa;
        border-radius: 6px;
        border: 1px solid #2d3748;
    }
    .stExpander, .stExpanderHeader {
        background: #232837 !important;
        color: #f3f6fa !important;
        border-radius: 8px !important;
    }
    .stAlert, .stSuccess, .stError, .stInfo {
        border-radius: 8px !important;
    }
    .stRadio > div {color: #f3f6fa;}
    .stProgress > div > div {background: #4a90e2 !important;}
    .stTextArea textarea {
        background: #232837;
        color: #f3f6fa;
        border-radius: 6px;
        border: 1px solid #2d3748;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("<div class='big-title'>PhotoFlow: Умная обработка изображений</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitle'>Быстрое и простое преобразование, переименование и защита ваших фото</div>", unsafe_allow_html=True)

# Подробный FAQ в expander
with st.expander("ℹ️ Инструкция и ответы на вопросы (FAQ)", expanded=False):
    st.markdown("""
    **Как пользоваться:**
    1. Выберите режим работы (переименование, конвертация, водяной знак).
    2. Загрузите изображения или архив (ZIP).
    3. Настройте параметры (масштаб, качество, водяной знак).
    4. Нажмите кнопку обработки и скачайте результат.

    **FAQ:**
    - **Почему не все фото обработались?**  
      Некоторые файлы могут быть повреждены, слишком большие или не поддерживаются (см. список форматов).  
      HEIC/HEIF требуют установленного pillow-heif.
    - **Что делать, если архив не скачивается?**  
      Попробуйте уменьшить размер архива или разделить файлы на несколько частей.  
      Проверьте стабильность интернет-соединения.
    - **Как уменьшить размер итоговых файлов?**  
      Используйте слайдер "Масштаб JPG" для уменьшения разрешения.  
      Для JPG можно дополнительно уменьшить качество (по запросу).
    - **Где найти лог ошибок?**  
      После обработки доступен лог — скачайте его или откройте в приложении.
    - **Какие форматы поддерживаются?**  
      JPG, PNG, BMP, WEBP, TIFF, HEIC, HEIF, ZIP (архивы с этими изображениями).
    - **Как добавить свой водяной знак?**  
      Загрузите PNG/JPG-файл водяного знака или выберите из папки watermarks.
    - **Что делать, если приложение "зависло"?**  
      Попробуйте обновить страницу или уменьшить количество/размер файлов.
    """)

if "reset_uploader" not in st.session_state:
    st.session_state["reset_uploader"] = 0
if "log" not in st.session_state:
    st.session_state["log"] = []
if "result_zip" not in st.session_state:
    st.session_state["result_zip"] = None
if "stats" not in st.session_state:
    st.session_state["stats"] = {}
if "mode" not in st.session_state:
    st.session_state["mode"] = "Переименование фото"

def reset_all():
    st.session_state["reset_uploader"] += 1
    st.session_state["log"] = []
    st.session_state["result_zip"] = None
    st.session_state["stats"] = {}
    st.session_state["mode"] = "Переименование фото"

mode = st.radio(
    "Выберите режим работы:",
    ["Переименование фото", "Конвертация в JPG", "Водяной знак"],
    index=0 if st.session_state["mode"] == "Переименование фото" else (1 if st.session_state["mode"] == "Конвертация в JPG" else 2),
    key="mode_radio",
    on_change=lambda: st.session_state.update({"log": [], "result_zip": None, "stats": {}})
)
st.session_state["mode"] = mode

st.markdown(
    """
    <span style='color:#888;'>Перетащите файлы или архив на область ниже или нажмите для выбора вручную</span>
    """,
    unsafe_allow_html=True
)

uploaded_files = st.file_uploader(
    f"Загрузите изображения или архив (до {MAX_SIZE_MB} МБ, поддерживаются JPG, PNG, HEIC, ZIP и др.)",
    type=["jpg", "jpeg", "png", "bmp", "webp", "tiff", "heic", "heif", "zip"],
    accept_multiple_files=True,
    key=st.session_state["reset_uploader"]
)

# --- UI для режима Водяной знак ---
if mode == "Водяной знак":
    st.markdown("**Выберите водяной знак (PNG/JPG):**")
    import glob
    from water import apply_watermark
    watermark_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "watermarks"))
    preset_files = []
    if os.path.exists(watermark_dir):
        preset_files = [f for f in os.listdir(watermark_dir) if f.lower().endswith((".png", ".jpg", ".jpeg"))]
    preset_choice = st.selectbox("Водяные знаки из папки watermarks/", ["Нет"] + preset_files)
    user_wm_file = st.file_uploader("Или загрузите свой PNG/JPG водяной знак", type=["png", "jpg", "jpeg"], key="watermark_upload")
    user_wm_path = None
    if user_wm_file is not None:
        tmp_dir = tempfile.gettempdir()
        user_wm_path = os.path.join(tmp_dir, f"user_wm_{user_wm_file.name}")
        with open(user_wm_path, "wb") as f:
            f.write(user_wm_file.read())
    st.sidebar.header('Настройки водяного знака')
    opacity = st.sidebar.slider('Прозрачность', 0, 100, 60) / 100.0
    size_percent = st.sidebar.slider('Размер (% от ширины фото)', 5, 80, 25)
    position = st.sidebar.selectbox('Положение', [
        'Правый нижний угол',
        'Левый нижний угол',
        'Правый верхний угол',
        'Левый верхний угол',
        'По центру',
    ])
    pos_map = {
        'Правый нижний угол': 'bottom_right',
        'Левый нижний угол': 'bottom_left',
        'Правый верхний угол': 'top_right',
        'Левый верхний угол': 'top_left',
        'По центру': 'center',
    }
    bg_color = st.sidebar.color_picker("Цвет фона предпросмотра", "#CCCCCC")

    # --- Предпросмотр водяного знака ---
    st.markdown("**Предпросмотр водяного знака:**")
    preview_img = None
    def get_first_image(uploaded_files):
        for file in uploaded_files:
            if file.name.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff', '.heic', '.heif')):
                file.seek(0)
                try:
                    return Image.open(file)
                except Exception:
                    continue
            elif file.name.lower().endswith('.zip'):
                import zipfile
                from io import BytesIO
                file.seek(0)
                with zipfile.ZipFile(file, 'r') as zf:
                    for name in zf.namelist():
                        if name.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff', '.heic', '.heif')):
                            with zf.open(name) as imgf:
                                try:
                                    return Image.open(BytesIO(imgf.read()))
                                except Exception:
                                    continue
        return None
    preview_img = get_first_image(uploaded_files) if uploaded_files else None
    if preview_img is None:
        preview_img = Image.new("RGB", (400, 300), bg_color)
    wm_path = None
    if preset_choice != "Нет":
        wm_path = os.path.join(watermark_dir, preset_choice)
    elif user_wm_file:
        tmp_dir = tempfile.gettempdir()
        wm_path = os.path.join(tmp_dir, f"user_wm_{user_wm_file.name}")
        with open(wm_path, "wb") as f:
            f.write(user_wm_file.getvalue() if hasattr(user_wm_file, 'getvalue') else user_wm_file.read())
    try:
        if wm_path:
            preview = apply_watermark(preview_img, watermark_path=wm_path, position=pos_map[position], opacity=opacity, scale=size_percent/100.0)
        else:
            preview = preview_img
        st.image(preview, caption="Предпросмотр", use_container_width=True)
    except Exception as e:
        st.warning(f"Ошибка предпросмотра: {e}")

# Масштаб JPG для всех режимов
st.sidebar.markdown("**Масштаб JPG (разрешение):**")
scale_percent = st.sidebar.slider(
    "Масштабировать изображения (%)",
    min_value=10, max_value=100, value=100, step=5,
    help="Уменьшение разрешения уменьшает размер файла, но может ухудшить детализацию."
)
st.sidebar.caption("Уменьшение разрешения уменьшает размер файла, но может ухудшить детализацию.")
# Предпросмотр итогового размера (примерно)
if uploaded_files:
    try:
        from io import BytesIO
        file = next((f for f in uploaded_files if f.name.lower().endswith((".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff", ".heic", ".heif"))), None)
        if file:
            file.seek(0)
            img = Image.open(file)
            orig_size = file.size if hasattr(file, 'size') else file.getbuffer().nbytes if hasattr(file, 'getbuffer') else None
            w, h = img.size
            new_w = int(w * scale_percent / 100)
            new_h = int(h * scale_percent / 100)
            img_resized = img.resize((new_w, new_h), RESAMPLING)
            buf = BytesIO()
            img_resized.save(buf, format="JPEG", quality=90, optimize=True, progressive=True)
            approx_size = buf.tell()
            st.sidebar.info(f"Примерный размер после сжатия: {approx_size//1024} КБ (было: {orig_size//1024 if orig_size else '?'} КБ)")
    except Exception as e:
        st.sidebar.warning(f"Не удалось рассчитать размер: {e}")

if mode == "Переименование фото":
    process_rename_mode(uploaded_files, scale_percent)
elif mode == "Конвертация в JPG":
    process_convert_mode(uploaded_files, scale_percent)
elif mode == "Водяной знак":
    process_watermark_mode(uploaded_files, preset_choice, user_wm_file, user_wm_path, watermark_dir, pos_map, opacity, size_percent, position, scale_percent)

# Универсальный блок скачивания архива и лога для всех режимов
if st.session_state.get("result_zip"):
    st.success("✅ Архив успешно создан! Готов к скачиванию.")
    result_zip = st.session_state["result_zip"]
    archive_data = None
    archive_size = None
    if isinstance(result_zip, bytes):
        archive_data = result_zip
        archive_size = len(result_zip)
    elif isinstance(result_zip, str) and os.path.exists(result_zip):
        with open(result_zip, "rb") as f:
            archive_data = f.read()
            archive_size = os.path.getsize(result_zip)
    else:
        archive_data = None
    if archive_data:
        st.download_button(
            label="📥 Скачать архив",
            data=archive_data,
            file_name=(
                "renamed_photos.zip" if mode == "Переименование фото"
                else "converted_photos.zip" if mode == "Конвертация в JPG"
                else "watermarked_images.zip"
            ),
            mime="application/zip",
            type="primary"
        )
        if archive_size:
            st.caption(f"Размер архива: {archive_size // 1024} КБ ({archive_size / 1024 / 1024:.2f} МБ)")
    with st.expander("Показать лог обработки", expanded=False):
        st.download_button(
            label="📄 Скачать лог в .txt",
            data="\n".join(st.session_state["log"]),
            file_name="log.txt",
            mime="text/plain"
        )
        st.text_area("Лог:", value="\n".join(st.session_state["log"]), height=300, disabled=True)
else:
    st.info("ℹ️ Архив пока не создан. Загрузите изображения и нажмите кнопку обработки.")

if st.button("🔄 Начать сначала", type="primary"):
    reset_all()
    st.rerun()

# --- Кнопка обработки ---
# Удалён дублирующий вызов:
# if st.button("Обработать и скачать архив"):
#     ...
# (Вся логика обработки уже реализована выше внутри блока 'Водяной знак')

# --- Функция для загрузки на TransferNow ---
def upload_to_transfernow(file_path):
    url = "https://api.transfernow.net/v2/transfers"
    with open(file_path, 'rb') as f:
        files = {'files': (os.path.basename(file_path), f)}
        data = {
            'message': 'Ваш файл готов!',
            'email_from': 'noreply@photoflow.local'
        }
        response = requests.post(url, files=files, data=data)
    if response.status_code == 201:
        return response.json().get('download_url')
    else:
        return None
