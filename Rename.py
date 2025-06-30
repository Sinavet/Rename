import streamlit as st
import os
import zipfile
import tempfile
from pathlib import Path

st.title("🤖 Веб-бот: Переименовать фото в каждой папке в '1'")

uploaded_zip = st.file_uploader("Загрузите zip-архив с папками и фото (до 100 МБ)", type="zip")

if uploaded_zip:
    if uploaded_zip.size > 100 * 1024 * 1024:  # 100 МБ
        st.error("Файл слишком большой! Максимальный размер — 100 МБ.")
    else:
        with st.spinner("Обработка архива, пожалуйста, подождите..."):
            with tempfile.TemporaryDirectory() as tmpdir:
                zip_path = os.path.join(tmpdir, "input.zip")
                with open(zip_path, "wb") as f:
                    f.write(uploaded_zip.read())
                try:
                    with zipfile.ZipFile(zip_path, "r") as zip_ref:
                        zip_ref.extractall(tmpdir)
                except Exception as e:
                    st.error(f"Ошибка при распаковке архива: {e}")
                    st.stop()

                exts = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif')
                log = []
                renamed = 0
                skipped = 0
                folders = [f for f in Path(tmpdir).rglob("*") if f.is_dir()]
                progress_bar = st.progress(0, text="Папки обработаны: 0/")
                for i, folder in enumerate(folders):
                    photos = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in exts]
                    relative_folder_path = folder.relative_to(tmpdir)
                    if len(photos) == 1:
                        photo = photos[0]
                        new_name = f"1{photo.suffix.lower()}"
                        new_path = photo.parent / new_name
                        relative_photo_path = photo.relative_to(tmpdir)
                        relative_new_path = new_path.relative_to(tmpdir)
                        if new_path.exists():
                            log.append(f"{i+1}. Пропущено: Файл '{relative_new_path}' уже существует.")
                            skipped += 1
                        else:
                            photo.rename(new_path)
                            log.append(f"{i+1}. Переименовано: '{relative_photo_path}' -> '{relative_new_path}'")
                            renamed += 1
                    elif len(photos) > 1:
                        log.append(f"{i+1}. Пропущено: В папке '{relative_folder_path}' несколько фото.")
                        skipped += 1
                    else:
                        log.append(f"{i+1}. Инфо: В папке '{relative_folder_path}' нет фото.")
                        skipped += 1
                    progress_bar.progress((i+1)/len(folders), text=f"Папки обработаны: {i+1}/{len(folders)}")

                result_zip_path = os.path.join(tmpdir, "renamed_photos.zip")
                with zipfile.ZipFile(result_zip_path, "w") as zipf:
                    for file in Path(tmpdir).rglob("*"):
                        if file.is_file() and file.name != "input.zip":
                            zipf.write(file, arcname=file.relative_to(tmpdir))

                st.success(f"Переименование завершено! Переименовано: {renamed}, пропущено: {skipped}")

                with open(result_zip_path, "rb") as f:
                    st.download_button(
                        label="Скачать архив с результатом",
                        data=f.read(),
                        file_name="renamed_photos.zip",
                        mime="application/zip"
                    )
                st.text_area("Лог переименования:", "\n".join(log), height=400)
