import streamlit as st
import os
import zipfile
import tempfile
from pathlib import Path
import shutil

# --- Инициализация состояния сессии ---
# Это нужно, чтобы хранить результаты между действиями пользователя
if 'processing_complete' not in st.session_state:
    st.session_state.processing_complete = False
    st.session_state.log = []
    st.session_state.stats = {}
    st.session_state.result_zip_data = None

def reset_state():
    """Сбрасывает состояние для новой загрузки."""
    st.session_state.processing_complete = False
    st.session_state.log = []
    st.session_state.stats = {}
    st.session_state.result_zip_data = None

st.title("🤖 Веб-бот для переименования фото")
st.markdown("Переименовывает одно фото в каждой папке в `1`.")

# --- Основной интерфейс ---
if st.session_state.processing_complete:
    st.info("Обработка завершена. Можете скачать результат или обработать новый архив.")
    st.button("Обработать новый архив", on_click=reset_state, use_container_width=True)
else:
    uploaded_zip = st.file_uploader(
        "Загрузите zip-архив с папками и фото (до 100 МБ)", 
        type="zip",
        on_change=reset_state # Сброс при загрузке нового файла
    )

    if uploaded_zip:
        if uploaded_zip.size > 100 * 1024 * 1024:  # 100 МБ
            st.error("Файл слишком большой! Максимальный размер — 100 МБ.")
        else:
            with st.spinner("Магия в процессе... Распаковываю, анализирую, переименовываю..."):
                try:
                    with tempfile.TemporaryDirectory() as tmpdir:
                        # --- Логика обработки ---
                        path_tmpdir = Path(tmpdir)
                        zip_path = path_tmpdir / "input.zip"
                        with open(zip_path, "wb") as f:
                            f.write(uploaded_zip.read())
                        
                        with zipfile.ZipFile(zip_path, "r") as zip_ref:
                            zip_ref.extractall(path_tmpdir)

                        exts = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif')
                        log = []
                        renamed = 0
                        skipped = 0
                        
                        folders = sorted([f for f in path_tmpdir.rglob("*") if f.is_dir()])
                        progress_bar = st.progress(0, text="Анализ папок...")

                        for i, folder in enumerate(folders):
                            photos = sorted([f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in exts])
                            relative_folder_path = folder.relative_to(path_tmpdir)

                            if len(photos) == 1:
                                photo = photos[0]
                                new_name = f"1{photo.suffix.lower()}"
                                new_path = photo.parent / new_name
                                relative_photo_path = photo.relative_to(path_tmpdir)
                                relative_new_path = new_path.relative_to(path_tmpdir)
                                if new_path.exists():
                                    log.append(f"Пропущено: Файл '{relative_new_path}' уже существует.")
                                    skipped += 1
                                else:
                                    photo.rename(new_path)
                                    log.append(f"Переименовано: '{relative_photo_path}' -> '{relative_new_path}'")
                                    renamed += 1
                            elif len(photos) > 1:
                                log.append(f"Пропущено: В папке '{relative_folder_path}' несколько фото.")
                                skipped += len(photos)
                            else:
                                log.append(f"Инфо: В папке '{relative_folder_path}' нет фото.")
                                skipped += 1
                            
                            progress_bar.progress((i + 1) / len(folders), text=f"Обработано папок: {i + 1}/{len(folders)}")

                        # --- Архивирование результата ---
                        extracted_items = [p for p in path_tmpdir.iterdir() if p.name != 'input.zip']
                        zip_root = path_tmpdir
                        if len(extracted_items) == 1 and extracted_items[0].is_dir():
                            zip_root = extracted_items[0]

                        # Используем shutil.make_archive для корректного сохранения всей структуры, включая пустые папки
                        archive_base_name = path_tmpdir / "renamed_photos"
                        shutil.make_archive(
                            base_name=str(archive_base_name),
                            format='zip',
                            root_dir=str(zip_root)
                        )
                        result_zip_path = path_tmpdir / "renamed_photos.zip"
                        
                        with open(result_zip_path, "rb") as f:
                            st.session_state.result_zip_data = f.read()

                        # --- Сохранение результатов в состояние ---
                        st.session_state.stats = {'renamed': renamed, 'skipped': skipped, 'folders': len(folders)}
                        st.session_state.log = log
                        st.session_state.processing_complete = True
                        st.rerun()

                except Exception as e:
                    st.error(f"Произошла критическая ошибка: {e}")
                    st.exception(e)


# --- Отображение результатов после завершения ---
if st.session_state.processing_complete:
    stats = st.session_state.stats
    st.success("Обработка успешно завершена!")

    col1, col2, col3 = st.columns(3)
    col1.metric("Папок обработано", stats.get('folders', 0))
    col2.metric("Файлов переименовано", stats.get('renamed', 0))
    col3.metric("Файлов пропущено", stats.get('skipped', 0))
    
    st.download_button(
        label="📥 Скачать результат",
        data=st.session_state.result_zip_data,
        file_name="renamed_photos.zip",
        mime="application/zip",
        use_container_width=True
    )
    
    with st.expander("Показать/скрыть подробный лог"):
        st.text_area(
            label="Лог выполнения:",
            value="\n".join(st.session_state.log),
            height=300,
            disabled=True
        )
