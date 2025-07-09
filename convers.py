# convers.py
import os
import zipfile
import tempfile
from pathlib import Path
from PIL import Image
RESAMPLING = getattr(getattr(Image, 'Resampling', Image), 'LANCZOS', getattr(Image, 'LANCZOS', getattr(Image, 'NEAREST', 0)))
import streamlit as st
from utils import filter_large_files, SUPPORTED_EXTS


def process_convert_mode(uploaded_files, scale_percent=100):
    uploaded_files = filter_large_files(uploaded_files)
    if uploaded_files and st.button("Обработать и скачать архив", key="process_convert_btn"):
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
                    with zipfile.ZipFile(zip_temp, "r") as zip_ref:
                        for member in zip_ref.namelist():
                            try:
                                zip_ref.extract(member, temp_dir)
                            except Exception as e:
                                log.append(f"❌ Не удалось извлечь {member} из {uploaded.name}: {e}")
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
                result_zip = os.path.join(temp_dir, "result_convert.zip")
                with zipfile.ZipFile(result_zip, "w") as zipf:
                    log_path = os.path.join(temp_dir, "log.txt")
                    with open(log_path, "w", encoding="utf-8") as logf:
                        logf.write("\n".join(log))
                    zipf.write(log_path, arcname="log.txt")
                st.session_state["result_zip"] = None # Удаляю вывод архива
                st.session_state["stats"] = {"total": 0, "converted": 0, "errors": 0}
                st.session_state["log"] = log
            else:
                converted_files = []
                errors = 0
                st.markdown("""
                    <div style='font-size:1.3em;font-weight:600;margin-bottom:0.5em;'>🛠️ Шаг 2: Конвертация изображений</div>
                """, unsafe_allow_html=True)
                progress_bar = st.progress(0)
                status_placeholder = st.empty()
                for i, img_path in enumerate(all_images, 1):
                    rel_path = img_path.relative_to(temp_dir)
                    out_path = os.path.join(temp_dir, str(rel_path.with_suffix('.jpg')))
                    out_dir = os.path.dirname(out_path)
                    os.makedirs(out_dir, exist_ok=True)
                    try:
                        img = Image.open(img_path)
                        icc_profile = img.info.get('icc_profile')
                        img = img.convert("RGB")
                        # Изменение разрешения
                        if scale_percent != 100:
                            w, h = img.size
                            new_w = max(1, int(w * scale_percent / 100))
                            new_h = max(1, int(h * scale_percent / 100))
                            img = img.resize((new_w, new_h), RESAMPLING)
                        img.save(out_path, "JPEG", quality=100, optimize=True, progressive=True, icc_profile=icc_profile)
                        converted_files.append((out_path, rel_path.with_suffix('.jpg')))
                        log.append(f"✅ {rel_path} → {rel_path.with_suffix('.jpg')}")
                    except Exception as e:
                        log.append(f"❌ {rel_path}: ошибка конвертации ({e})")
                        errors += 1
                    progress_bar.progress(i / len(all_images))
                    status_placeholder.markdown(f"<span style='color:#4a90e2;'>Обработано файлов: <b>{i}/{len(all_images)}</b></span>", unsafe_allow_html=True)
                st.markdown("""
                    <div style='font-size:1.3em;font-weight:600;margin:1em 0 0.5em 0;'>📦 Шаг 3: Архивация результата</div>
                """, unsafe_allow_html=True)
                if converted_files:
                    st.success(f"✅ Успешно конвертировано: {len(converted_files)} из {len(all_images)} файлов.")
                    result_zip = os.path.join(temp_dir, "result_convert.zip")
                    with zipfile.ZipFile(result_zip, "w") as zipf:
                        for src, rel in converted_files:
                            zipf.write(src, arcname=rel)
                        # log.txt больше не добавляем в архив
                    with open(result_zip, "rb") as f:
                        st.session_state["result_zip"] = f.read()
                    st.session_state["stats"] = {
                        "total": len(all_images),
                        "converted": len(converted_files),
                        "errors": errors
                    }
                    st.session_state["log"] = log
                else:
                    st.error("❌ Не удалось конвертировать ни одного изображения.")
                    # Создаём архив только с логом ошибок
                    result_zip = os.path.join(temp_dir, "result_convert.zip")
                    with zipfile.ZipFile(result_zip, "w") as zipf:
                        log_path = os.path.join(temp_dir, "log.txt")
                        with open(log_path, "w", encoding="utf-8") as logf:
                            logf.write("\n".join(log))
                        zipf.write(log_path, arcname="log.txt")
                    with open(result_zip, "rb") as f:
                        st.session_state["result_zip"] = f.read()
                    st.session_state["stats"] = {"total": len(all_images), "converted": 0, "errors": errors}
                    st.session_state["log"] = log
                if errors > 0:
                    with st.expander("Показать подробный лог ошибок", expanded=False):
                        st.text_area("Лог:", value="\n".join(log), height=300, disabled=True)
