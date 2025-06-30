import streamlit as st
import os
import zipfile
import tempfile
from pathlib import Path

st.title("🤖 Веб-бот: Переименовать фото в каждой папке в '1'")

uploaded_zip = st.file_uploader("Загрузите zip-архив с папками и фото", type="zip")

if uploaded_zip:
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = os.path.join(tmpdir, "input.zip")
        with open(zip_path, "wb") as f:
            f.write(uploaded_zip.read())
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(tmpdir)

        exts = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif')
        log = []
        # Для каждой папки ищем фото и переименовываем в 1
        for folder in Path(tmpdir).rglob("*"):
            if folder.is_dir():
                photos = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in exts]
                if len(photos) == 1:
                    photo = photos[0]
                    new_name = f"1{photo.suffix.lower()}"
                    new_path = photo.parent / new_name
                    photo.rename(new_path)
                    log.append(f"{photo} → {new_path}")
                elif len(photos) > 1:
                    log.append(f"{folder}: В папке больше одной фотки, ничего не переименовано.")
                else:
                    log.append(f"{folder}: Нет фото для переименования.")

        # Архивируем результат
        result_zip_path = os.path.join(tmpdir, "renamed_photos.zip")
        with zipfile.ZipFile(result_zip_path, "w") as zipf:
            for file in Path(tmpdir).rglob("*"):
                if file.is_file():
                    zipf.write(file, arcname=file.relative_to(tmpdir))

        st.success("Переименование завершено!")
        st.download_button(
            label="Скачать архив с результатом",
            data=open(result_zip_path, "rb").read(),
            file_name="renamed_photos.zip",
            mime="application/zip"
        )
        st.text_area("Лог переименования:", "\n".join(log), height=300)