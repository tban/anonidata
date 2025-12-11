# Diagnóstico de Problema de Coordenadas

## Problema Reportado
Los rectángulos de censura en PDFs con imágenes escaneadas aparecen en ubicaciones diferentes a donde se colocaron originalmente.

## Pasos para Diagnosticar

### 1. Ejecutar la aplicación en modo desarrollo

```bash
npm run dev
```

Esto abrirá:
- Terminal 1: Vite dev server (renderer) en http://localhost:3000
- Terminal 2: Electron con DevTools abierto

### 2. Preparar PDF de prueba

Usa el PDF de prueba: `test/pdfs/testpdfimagen.pdf` (o cualquier PDF con imagen escaneada)

### 3. Pasos de prueba

1. En la aplicación, carga el PDF con imagen escaneada
2. Haz clic en "Revisión manual"
3. Cuando se abra la pantalla de revisión, haz clic en "+ Añadir Área"
4. Dibuja UN rectángulo en una ubicación específica y fácil de recordar (por ejemplo, esquina superior izquierda)
5. **IMPORTANTE**: Abre la consola de Chrome DevTools (ya debería estar abierta en desarrollo)
6. Busca el log que dice `=== SELECCIÓN MANUAL ===`
7. **Copia y pega TODA la información del log aquí abajo**

### 4. Información a capturar

El log debe contener:
```
=== SELECCIÓN MANUAL ===
Canvas dimensions: { width: XXX, height: XXX }
PDF page height: XXX
Scale: XXX
Screen rect: { x: XXX, y: XXX, width: XXX, height: XXX }
PDF bbox: { x0: XXX, y0: XXX, x1: XXX, y1: XXX }
Final bbox array: [XXX, XXX, XXX, XXX]
=======================
```

### 5. Continuar el proceso

1. Haz clic en "Finalizar anonimización"
2. Abre el PDF generado
3. Verifica DÓNDE apareció el rectángulo gris
4. Compara con la ubicación donde lo dibujaste

### 6. Proporcionar información

Por favor proporciona:
1. Los logs de la consola (copiados del paso 3.7)
2. Una descripción de dónde dibujaste el rectángulo
3. Una descripción de dónde apareció el rectángulo final
4. Si es posible, una captura de pantalla de ambas ubicaciones

## Script de Prueba de Coordenadas

También puedes ejecutar este script para verificar que PyMuPDF dibuja correctamente en el centro:

```bash
backend/venv/bin/python test_coordinates.py test/pdfs/testpdfimagen.pdf
```

Esto generará `test/pdfs/testpdfimagen_coordinate_test.pdf` con un rectángulo gris en el CENTRO.
Verifica que el rectángulo esté efectivamente centrado.

## Información del Sistema de Coordenadas

### Teoría
- PDF.js y PyMuPDF usan el MISMO sistema de coordenadas:
  - Origen: esquina superior izquierda (0, 0)
  - Eje X: crece hacia la derecha
  - Eje Y: crece hacia ABAJO
  - BBox formato: [x0, y0, x1, y1] donde (x0, y0) es esquina superior izquierda

### Posibles Causas del Problema

1. **Escala incorrecta**: El factor de escala (zoom) no se aplica correctamente
2. **Offset del canvas**: Si el canvas PDF está centrado, hay un offset que no se está considerando
3. **Rotación de página**: Si la página está rotada, las coordenadas no se transforman
4. **Resolución de imagen**: Si la imagen tiene DPI diferente, podría haber desajuste

## Resultado Esperado

Con los logs, podremos identificar exactamente dónde está el problema en la transformación de coordenadas.
