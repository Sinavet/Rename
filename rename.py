# rename.py
import os
import zipfile
import tempfile
from pathlib import Path
from PIL import Image
import streamlit as st
from utils import filter_large_files, SUPPORTED_EXTS

def process_rename_mode(uploaded_files):
    uploaded_files = filter_large_files(uploaded_files)
    if uploaded_files and st.button("Обработать и скачать архив", key="process_rename_btn"):
        with tempfile.TemporaryDirectory() as temp_dir:
            all_images = []
            log = []
            st.markdown("""
                <div style='font-size:1.3em;font-weight:600;margin-bottom:0.5em;'>⏳ Шаг 1: Сбор файлов</div>
            """, unsafe_allow_html=True)
            for uploaded in uploaded_files:
                if uploaded.name.lower().endswith(".zip"):
                    zip_temp = os.path.join(temp_dir, uploaded.name)
                    with open(zip_temp, "wb") as f:
                        f.write(uploaded.read())
                    try:
                        with zipfile.ZipFile(zip_temp, "r") as zip_ref:
                            for member in zip_ref.namelist():
                                try:
                                    zip_ref.extract(member, temp_dir)
                                except Exception as e:
                                    log.append(f"❌ Не удалось извлечь {member} из {uploaded.name}: {e}")
                    except Exception as e:
                        log.append(f"❌ Ошибка открытия архива {uploaded.name}: {e}")
                        continue
                    extracted = [file for file in Path(temp_dir).rglob("*") if file.is_file() and file.suffix.lower() in SUPPORTED_EXTS]
                    log.append(f"📦 Архив {uploaded.name}: найдено {len(extracted)} изображений.")
                    all_images.extend(extracted)
                elif uploaded.name.lower().endswith(SUPPORTED_EXTS):
                    img_temp = os.path.join(temp_dir, uploaded.name)
                    with open(img_temp, "wb") as f:
                        f.write(uploaded.read())
                    all_images.append(Path(img_temp))
                    log.append(f"🖼️ Файл {uploaded.name}: добавлен.")
                else:
                    log.append(f"❌ {uploaded.name}: не поддерживается.")
            st.markdown(f"<div style='margin-bottom:1em;'>🔍 Найдено <b>{len(all_images)}</b> изображений для обработки.</div>", unsafe_allow_html=True)
            if not all_images:
                st.error("Не найдено ни одного поддерживаемого изображения.")
                # Создаём пустой архив с логом ошибок
                result_zip = os.path.join(temp_dir, "result_rename.zip")
                with zipfile.ZipFile(result_zip, "w") as zipf:
                    log_path = os.path.join(temp_dir, "log.txt")
                    with open(log_path, "w", encoding="utf-8") as logf:
                        logf.write("\n".join(log))
                    zipf.write(log_path, arcname="log.txt")
                st.session_state["result_zip"] = None # Удаляю блок:
                st.session_state["stats"] = {"total": 0, "renamed": 0, "skipped": 0}
                st.session_state["log"] = log
            else:
                exts = SUPPORTED_EXTS
                renamed = 0
                skipped = 0
                folders = sorted({img.parent for img in all_images})
                if len(folders) > 0:
                    st.markdown("""
                        <div style='font-size:1.3em;font-weight:600;margin-bottom:0.5em;'>🛠️ Шаг 2: Переименование файлов</div>
                    """, unsafe_allow_html=True)
                    progress_bar = st.progress(0)
                    status_placeholder = st.empty()
                    for i, folder in enumerate(folders, 1):
                        photos = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in exts]
                        photos_sorted = sorted(photos, key=lambda x: x.name)
                        relative_folder_path = folder.relative_to(temp_dir)
                        if len(photos_sorted) > 0:
                            for idx, photo in enumerate(photos_sorted, 1):
                                new_name = f"{idx}{photo.suffix.lower()}"
                                new_path = photo.parent / new_name
                                relative_photo_path = photo.relative_to(temp_dir)
                                relative_new_path = new_path.relative_to(temp_dir)
                                if new_path.exists() and new_path != photo:
                                    log.append(f"Пропущено: Файл '{relative_new_path}' уже существует.")
                                    skipped += 1
                                else:
                                    photo.rename(new_path)
                                    log.append(f"Переименовано: '{relative_photo_path}' -> '{relative_new_path}'")
                                    renamed += 1
                        else:
                            log.append(f"Инфо: В папке '{relative_folder_path}' нет фото.")
                            skipped += 1
                        progress = min(i / len(folders), 1.0)
                        progress_bar.progress(progress)
                        status_placeholder.markdown(f"<span style='color:#4a90e2;'>Обработано папок: <b>{i}/{len(folders)}</b></span>", unsafe_allow_html=True)
                st.markdown("""
                    <div style='font-size:1.3em;font-weight:600;margin:1em 0 0.5em 0;'>📦 Шаг 3: Архивация результата</div>
                """, unsafe_allow_html=True)
                # Архивация результата
                extracted_items = [p for p in Path(temp_dir).iterdir() if p.name != uploaded_files[0].name]
                zip_root = Path(temp_dir)
                if len(extracted_items) == 1 and extracted_items[0].is_dir():
                    zip_root = extracted_items[0]
                files_to_zip = [file for file in Path(zip_root).rglob("*") if file.is_file() and file.suffix.lower() in exts or file.name == "log.txt"]
                st.write("[DEBUG] Начинаю архивацию результата...")
                st.write(f"[DEBUG] files_to_zip: {[str(f) for f in files_to_zip]}")
                log_path = os.path.join(temp_dir, "log.txt")
                if os.path.exists(log_path):
                    files_to_zip.append(Path(log_path))
                try:
                    result_zip = os.path.join(temp_dir, "result_rename.zip")
                    with zipfile.ZipFile(result_zip, "w") as zipf:
                        for file in files_to_zip:
                            arcname = file.relative_to(zip_root)
                            zipf.write(file, arcname=arcname)
                    st.write("[DEBUG] Архивация завершена, архив сохранён в session_state")
                    with open(result_zip, "rb") as f:
                        st.session_state["result_zip"] = f.read()
                    st.session_state["stats"] = {
                        "total": len(all_images),
                        "renamed": renamed,
                        "skipped": skipped
                    }
                    st.session_state["log"] = log
                except Exception as e:
                    st.error(f"Ошибка при архивации или чтении архива: {e}")
                    st.write(f"[DEBUG] Ошибка архивации: {e}")
                    result_zip = os.path.join(temp_dir, "result_rename.zip")
                    with zipfile.ZipFile(result_zip, "w") as zipf:
                        log.append(f"Ошибка архивации: {e}")
                        log_path = os.path.join(temp_dir, "log.txt")
                        with open(log_path, "w", encoding="utf-8") as logf:
                            logf.write("\n".join(log))
                        zipf.write(log_path, arcname="log.txt")
                    st.session_state["result_zip"] = None # Теперь только обработка и запись в session_state
                    st.session_state["stats"] = {"total": len(all_images), "renamed": renamed, "skipped": skipped}
                    st.session_state["log"] = log
                st.success(f"✅ Успешно переименовано: {renamed} файлов. Пропущено: {skipped}.")
                if skipped > 0:
                    with st.expander("Показать подробный лог", expanded=False):
                        st.text_area("Лог:", value="\n".join(log), height=300, disabled=True)
