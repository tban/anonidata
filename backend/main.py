#!/usr/bin/env python3
"""
AnoniData Backend - Main Entry Point
Maneja la comunicación con Electron via stdin/stdout
"""

import sys
import json
import os
from pathlib import Path
from typing import Dict, List, Any
from loguru import logger

from core.processor import PDFProcessor
from core.config import Settings
from utils.logging_config import setup_logging


def setup_environment():
    """Configurar entorno de ejecución"""
    # Configurar logging
    setup_logging()

    # Verificar dependencias
    try:
        import fitz  # PyMuPDF
        import cv2
        import spacy
        logger.info("Dependencias verificadas correctamente")
    except ImportError as e:
        logger.error(f"Error importando dependencias: {e}")
        sys.exit(1)


def process_request(request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Procesa una solicitud de Electron

    Args:
        request: Diccionario con la solicitud

    Returns:
        Diccionario con el resultado
    """
    action = request.get("action")

    if action == "anonymize":
        files = request.get("files", [])
        settings_dict = request.get("settings", {})
        options = request.get("options", {})
        file_options = options.get("fileOptions", {}) if isinstance(options, dict) else {}

        # Procesar archivos
        results = []
        for file_path in files:
            try:
                # Obtener opciones específicas para este archivo e incorporarlas a su configuración
                this_file_opts = file_options.get(file_path, {})
                file_settings_dict = settings_dict.copy()
                if isinstance(this_file_opts, dict):
                    file_settings_dict.update(this_file_opts)
                
                settings = Settings(**file_settings_dict)
                processor = PDFProcessor(settings)
                
                result = processor.process_file(file_path)
                results.append(result)
            except Exception as e:
                logger.error(f"Error procesando {file_path}: {e}")
                results.append({
                    "inputFile": file_path,
                    "status": "error",
                    "error": str(e),
                })

        return {
            "success": True,
            "results": results,
        }

    elif action == "detect_only":
        """
        Detecta PII y crea PDF pre-anonimizado sin aplicar redacciones finales
        Retorna rutas al PDF pre-anonimizado y archivo JSON con detecciones
        """
        file_path = request.get("file")
        settings_dict = request.get("settings", {})
        options = request.get("options", {})

        # Combinar settings con opciones específicas de esta llamada
        file_settings_dict = settings_dict.copy()
        if isinstance(options, dict):
            file_settings_dict.update(options)

        # Crear configuración
        settings = Settings(**file_settings_dict)

        try:
            # Importar componentes necesarios
            from processors.pdf_parser import PDFParser
            from processors.ocr_engine import OCREngine
            from detectors.pii_detector import PIIDetector
            from processors.anonymizer import Anonymizer

            # Crear procesadores
            pdf_parser = PDFParser()
            ocr_engine = OCREngine(settings)
            pii_detector = PIIDetector(settings, pdf_path=Path(file_path))
            anonymizer = Anonymizer(settings)

            from utils.progress import emit_progress
            emit_progress(file_path, 2, "Iniciando análisis...")

            # Parsear PDF
            pdf_data = pdf_parser.parse(Path(file_path))
            logger.info(f"PDF parseado: {pdf_data.page_count} páginas")
            emit_progress(file_path, 5, "Analizando estructura del documento...")

            # Procesar con OCR
            def ocr_progress(pct, msg):
                # Mapea OCR del 10% al 60%
                overall_pct = 10 + int(pct * 0.50)
                emit_progress(file_path, overall_pct, f"OCR: {msg}")

            ocr_data = ocr_engine.process(pdf_data, progress_callback=ocr_progress)
            logger.info("OCR procesado")
            emit_progress(file_path, 60, "Buscando datos personales...")

            # Detectar PII
            def pii_progress(pct, msg):
                # Mapea PII del 60% al 95%
                overall_pct = 60 + int(pct * 0.35)
                emit_progress(file_path, overall_pct, msg)

            all_matches = pii_detector.detect(pdf_data, ocr_data, progress_callback=pii_progress)
            pdf_parser.close(pdf_data)
            logger.info(f"Detectados {len(all_matches)} elementos de PII")
            emit_progress(file_path, 95, "Creando documento de revisión...")

            # Crear pre-anonimizado
            pre_anon_path, detections_path = anonymizer.create_pre_anonymized(
                Path(file_path),
                all_matches
            )
            emit_progress(file_path, 100, "Análisis completado")

            return {
                "success": True,
                "preAnonymizedPath": str(pre_anon_path),
                "detectionsPath": str(detections_path),
                "totalDetections": len(all_matches),
            }

        except Exception as e:
            logger.error(f"Error en detect_only: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
            }

    elif action == "finalize_anonymization":
        """
        Aplica redacciones finales SOLO a las detecciones aprobadas
        """
        original_file_path = request.get("originalFile")
        detections_path = request.get("detectionsPath")
        approved_indices = set(request.get("approvedIndices", []))
        settings_dict = request.get("settings", {})

        # Crear configuración
        settings = Settings(**settings_dict)

        try:
            from processors.anonymizer import Anonymizer

            # Crear anonymizer
            anonymizer = Anonymizer(settings)

            # Cargar todas las detecciones
            all_detections = anonymizer.load_detections(Path(detections_path))
            logger.info(f"Cargadas {len(all_detections)} detecciones")

            # Filtrar solo las aprobadas (usar enumerate para obtener el índice correcto)
            approved_detections = [
                det for idx, det in enumerate(all_detections)
                if idx in approved_indices
            ]
            logger.info(f"Aplicando redacciones a {len(approved_detections)} detecciones aprobadas de {len(all_detections)} totales")

            is_image_pdf = request.get("isImagePdf", False)
            if is_image_pdf:
                logger.info("Forzando modo de imagen para anonimización (uso de overlays)")

            # Aplicar redacciones finales
            final_path = anonymizer.apply_final_redactions(
                Path(original_file_path),
                approved_detections,
                force_image_mode=is_image_pdf
            )

            # Eliminar archivos temporales después de finalizar con éxito
            try:
                # Derivar path del archivo _preAnonimizado desde el detectionsPath
                # Ejemplo: /path/file_detections.json -> /path/file_preAnonimizado.pdf
                detections_path_obj = Path(detections_path)
                pre_anonymized_path = detections_path_obj.parent / detections_path_obj.name.replace(
                    "_detections.json", "_preAnonimizado.pdf"
                )

                # Eliminar archivo _preAnonymized.pdf
                if pre_anonymized_path.exists():
                    os.remove(pre_anonymized_path)
                    logger.info(f"Archivo temporal eliminado: {pre_anonymized_path.name}")

                # Eliminar archivo _detections.json
                if detections_path_obj.exists():
                    os.remove(detections_path_obj)
                    logger.info(f"Archivo temporal eliminado: {detections_path_obj.name}")

            except Exception as cleanup_error:
                # No fallar si no se pueden eliminar los archivos temporales
                logger.warning(f"No se pudieron eliminar archivos temporales: {cleanup_error}")

            return {
                "success": True,
                "anonymizedPath": str(final_path),
                "totalApproved": len(approved_detections),
                "totalRejected": len(all_detections) - len(approved_detections),
            }

        except Exception as e:
            logger.error(f"Error en finalize_anonymization: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
            }

    elif action == "health":
        return {
            "success": True,
            "status": "healthy",
            "version": "1.0.0",
        }

    elif action == "fetch_url":
        url = request.get("url")
        try:
            import urllib.request
            import json
            import ssl

            # Deshabilitar verificación SSL por problemas locales de certificados
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            headers = {'User-Agent': 'Mozilla/5.0'}
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
                content = response.read().decode('utf-8')
                return {
                    "success": True,
                    "data": json.loads(content)
                }
        except Exception as e:
            logger.error(f"Error al descargar URL {url}: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    elif action == "check_pdf_type":
        """
        Verifica rápidamente si los archivos son Texto o Imagen usando PyMuPDF
        para consistencia con el motor de procesamiento.
        """
        files = request.get("files", [])
        results = []
        from utils.progress import emit_progress
        import time

        try:
            import fitz  # PyMuPDF
            
            for file_path in files:
                try:
                    emit_progress(file_path, 10, "Abriendo archivo...")
                    time.sleep(0.1)
                    doc = fitz.open(file_path)
                    
                    emit_progress(file_path, 30, "Analizando texto...")
                    time.sleep(0.1)
                    total_text_len = 0
                    pages_to_check = min(doc.page_count, 3)
                    page_count = doc.page_count
                    
                    for i in range(pages_to_check):
                        emit_progress(file_path, 30 + int((i + 1) * (50 / pages_to_check)), f"Analizando texto (pág. {i+1}/{pages_to_check})...")
                        time.sleep(0.1)
                        page = doc[i]
                        # get_text("text") es rápido y extrae texto plano
                        text = page.get_text("text").strip()
                        # Eliminar espacios para contar contenido real
                        dense_text = "".join(text.split())
                        total_text_len += len(dense_text)
                    
                    emit_progress(file_path, 90, "Clasificando formato...")
                    time.sleep(0.1)
                    doc.close()
                    
                    # Criterio: > 300 caracteres reales = texto
                    pdf_type = "text" if total_text_len > 300 else "image"
                    logger.info(f"Check PDF type: {file_path} -> total_text_len={total_text_len}, classified as={pdf_type}")
                    
                    emit_progress(file_path, 100, "Detección finalizada")
                    time.sleep(0.1)
                    
                    results.append({
                        "file": file_path,
                        "type": pdf_type,
                        "textLength": total_text_len,
                        "pages": page_count
                    })
                    
                except Exception as e:
                    logger.error(f"Error analizando tipo de PDF {file_path}: {e}")
                    # Fallback seguro
                    results.append({
                        "file": file_path,
                        "type": "error", # El frontend decidirá qué hacer (image o text default)
                        "error": str(e)
                    })

            return {
                "success": True,
                "results": results
            }

        except ImportError:
            return {
                "success": False,
                "error": "PyMuPDF (fitz) no instalado en backend"
            }
        except Exception as e:
             return {
                "success": False,
                "error": str(e)
            }

    elif action == "apply_ocr":
        """
        Convierte un PDF de imágenes en un PDF con capa de texto buscable usando OCR
        """
        file_path = request.get("file")
        language = request.get("language", "spa")
        
        try:
            import fitz
            import io
            from PIL import Image
            import pytesseract
            import shutil
            from utils.progress import emit_progress
            
            emit_progress(file_path, 0, "Iniciando OCR...")
            
            # Verificar Tesseract cmd (macOS homebrew paths)
            tesseract_path = shutil.which("tesseract")
            if not tesseract_path and sys.platform == "darwin":
                for path in ["/opt/homebrew/bin/tesseract", "/usr/local/bin/tesseract"]:
                    if os.path.exists(path):
                        tesseract_path = path
                        break
            if tesseract_path:
                pytesseract.pytesseract.tesseract_cmd = tesseract_path
 
            logger.info(f"Iniciando conversión OCR de {file_path} a español")
            
            new_doc = fitz.open()
            doc = fitz.open(file_path)
            total_pages = doc.page_count
            
            for page_num in range(total_pages):
                page = doc[page_num]
                
                progress_pct = int((page_num / total_pages) * 95)
                emit_progress(file_path, progress_pct, f"Procesando página {page_num + 1} de {total_pages}...")
                
                pix = page.get_pixmap(dpi=150)
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
                
                # Intentar con el idioma solicitado (español por defecto), si falla caer a inglés
                try:
                    pdf_page_bytes = pytesseract.image_to_pdf_or_hocr(
                        img, extension='pdf', lang=language, config="--oem 3 --psm 6"
                    )
                except Exception as lang_error:
                    logger.warning(f"Error con idioma OCR '{language}': {lang_error}. Reintentando con 'eng'.")
                    pdf_page_bytes = pytesseract.image_to_pdf_or_hocr(
                        img, extension='pdf', lang="eng", config="--oem 3 --psm 6"
                    )
                
                page_doc = fitz.open("pdf", pdf_page_bytes)
                new_doc.insert_pdf(page_doc)
                page_doc.close()
                
            doc.close()
            
            emit_progress(file_path, 95, "Guardando PDF final...")
            
            # Guardar el PDF con la extensión _OCR.pdf
            file_path_obj = Path(file_path)
            new_file_path = file_path_obj.parent / f"{file_path_obj.stem}_OCR.pdf"
            
            new_doc.save(str(new_file_path), garbage=4, deflate=True)
            new_doc.close()
            
            logger.info(f"Conversión OCR exitosa: {new_file_path.name}")
            emit_progress(file_path, 100, "Conversión finalizada")
            
            return {
                "success": True,
                "ocrPdfPath": str(new_file_path),
            }
            
        except Exception as e:
            logger.error(f"Error en apply_ocr: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
            }

    else:
        return {
            "success": False,
            "error": f"Acción desconocida: {action}",
        }


def main():
    """Main loop - lee de stdin y escribe a stdout"""
    setup_environment()

    logger.info("Backend Python iniciado")
    logger.info("Esperando solicitudes...")

    # Enviar señal READY a Electron para indicar que el backend está listo
    ready_signal = {"status": "ready", "message": "Backend iniciado correctamente"}
    sys.stdout.write(json.dumps(ready_signal) + "\n")
    sys.stdout.flush()

    try:
        for line in sys.stdin:
            try:
                # Parsear solicitud
                request = json.loads(line.strip())
                logger.debug(f"Solicitud recibida: {request.get('action')}")
                request_id = request.get("request_id")

                # Procesar
                response = process_request(request)
                if request_id is not None and isinstance(response, dict):
                    response["request_id"] = request_id

                # Enviar respuesta
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()

            except json.JSONDecodeError as e:
                logger.error(f"Error parseando JSON: {e}")
                error_response = {
                    "success": False,
                    "error": f"JSON inválido: {str(e)}",
                }
                sys.stdout.write(json.dumps(error_response) + "\n")
                sys.stdout.flush()

            except Exception as e:
                logger.error(f"Error procesando solicitud: {e}", exc_info=True)
                error_response = {
                    "success": False,
                    "error": str(e),
                }
                try:
                    if 'request' in locals() and isinstance(request, dict):
                        req_id = request.get("request_id")
                        if req_id is not None:
                            error_response["request_id"] = req_id
                except Exception:
                    pass
                sys.stdout.write(json.dumps(error_response) + "\n")
                sys.stdout.flush()

    except KeyboardInterrupt:
        logger.info("Backend detenido por usuario")
    except Exception as e:
        logger.error(f"Error fatal: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
