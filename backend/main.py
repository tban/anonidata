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

        # Crear configuración
        settings = Settings(**settings_dict)

        # Crear procesador
        processor = PDFProcessor(settings)

        # Procesar archivos
        results = []
        for file_path in files:
            try:
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

        # Crear configuración
        settings = Settings(**settings_dict)

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

            # Parsear PDF
            pdf_data = pdf_parser.parse(Path(file_path))
            logger.info(f"PDF parseado: {pdf_data.page_count} páginas")

            # Procesar con OCR
            ocr_data = ocr_engine.process(pdf_data)
            logger.info("OCR procesado")

            # Detectar PII
            all_matches = pii_detector.detect(pdf_data, ocr_data)
            pdf_parser.close(pdf_data)
            logger.info(f"Detectados {len(all_matches)} elementos de PII")

            # Crear pre-anonimizado
            pre_anon_path, detections_path = anonymizer.create_pre_anonymized(
                Path(file_path),
                all_matches
            )

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

    elif action == "check_pdf_type":
        """
        Verifica rápidamente si los archivos son Texto o Imagen usando PyMuPDF
        para consistencia con el motor de procesamiento.
        """
        files = request.get("files", [])
        results = []

        try:
            import fitz  # PyMuPDF
            
            for file_path in files:
                try:
                    doc = fitz.open(file_path)
                    total_text_len = 0
                    pages_to_check = min(doc.page_count, 3)
                    
                    for i in range(pages_to_check):
                        page = doc[i]
                        # get_text("text") es rápido y extrae texto plano
                        text = page.get_text("text").strip()
                        # Eliminar espacios para contar contenido real
                        dense_text = "".join(text.split())
                        total_text_len += len(dense_text)
                    
                    doc.close()
                    
                    # Criterio: > 50 caracteres reales = texto
                    pdf_type = "text" if total_text_len > 50 else "image"
                    
                    results.append({
                        "file": file_path,
                        "type": pdf_type,
                        "textLength": total_text_len
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

                # Procesar
                response = process_request(request)

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
                sys.stdout.write(json.dumps(error_response) + "\n")
                sys.stdout.flush()

    except KeyboardInterrupt:
        logger.info("Backend detenido por usuario")
    except Exception as e:
        logger.error(f"Error fatal: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
