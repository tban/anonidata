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

---

## ACTUALIZACIÓN - Diagnóstico de Rotación

### Hallazgos Previos

1. ✅ **PyMuPDF dibuja correctamente**: El test `test_transformation.py` confirmó que el rectángulo ROJO (coordenadas directas) aparece en la ubicación correcta
2. ✅ **El problema está en el frontend**: La conversión de coordenadas entre pantalla y PDF tiene algún problema
3. ⚠️ **Síntoma**: Los rectángulos aparecen "girados a la izquierda" (rotación de 90°), NO solo desplazados

### Nueva Hipótesis: Rotación de Página

Si el PDF tiene metadatos de rotación (común en escaneos), las coordenadas necesitan transformarse según la rotación:

- **Rotación 0°**: Sin transformación (x, y) → (x, y)
- **Rotación 90°**: (x, y) → (y, pageWidth - x)
- **Rotación 180°**: (x, y) → (pageWidth - x, pageHeight - y)
- **Rotación 270°**: (x, y) → (pageHeight - y, x)

### Nuevos Logs Agregados

Ahora la aplicación en modo desarrollo muestra:

#### 1. Información de Rotación (PDFViewer.tsx)
```
=== PDF.js PAGE INFO ===
Page number: 1
Rotation: 90 degrees  ← ¡IMPORTANTE!
Original dimensions: { width: XXX, height: XXX }
Scaled dimensions: { width: XXX, height: XXX }
Scale: 1.5
========================
```

#### 2. Coordenadas de Selección Manual (SelectionOverlay.tsx)
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

#### 3. Coordenadas al Mostrar (DetectionOverlay.tsx)
```
=== DETECCIÓN MANUAL - DISPLAY ===
Detection index: X
PDF bbox from detection: { x0: XXX, y0: XXX, x1: XXX, y1: XXX }
Screen rect after pdfToScreen: { x: XXX, y: XXX, width: XXX, height: XXX }
PDF page height: XXX
Scale: XXX
==================================
```

### Pasos de Diagnóstico Actualizados

1. **Ejecutar en modo desarrollo**: `npm run dev`
2. **Cargar PDF con imagen**: Usar `test/pdfs/testpdfimagen.pdf`
3. **Ir a "Revisión manual"**
4. **Verificar rotación en logs**: Buscar "=== PDF.js PAGE INFO ===" y anotar el valor de "Rotation"
5. **Dibujar un rectángulo** en una ubicación conocida (ej: esquina superior izquierda)
6. **Capturar TODOS los logs**:
   - Selección (cuando dibujas)
   - Display (cuando se muestra el rectángulo)
7. **Comparar**:
   - ¿Las coordenadas "PDF bbox" de selección coinciden con "PDF bbox" al mostrar?
   - ¿El "Screen rect" al mostrar coincide con el "Screen rect" original?
   - ¿Hay rotación de página (≠ 0°)?

### Información a Proporcionar

Por favor copia y pega:

1. **Log completo de PDF.js PAGE INFO** (especialmente la rotación)
2. **Log de SELECCIÓN MANUAL** (cuando dibujaste el rectángulo)
3. **Log de DETECCIÓN MANUAL - DISPLAY** (cuando se muestra)
4. **Descripción**:
   - Dónde dibujaste el rectángulo (ej: "esquina superior izquierda, 100px desde arriba y desde la izquierda")
   - Dónde apareció el rectángulo (ej: "esquina inferior derecha, girado 90°")

### Posible Solución

Si la página tiene rotación ≠ 0°, necesitamos:

1. **Capturar la rotación** en `onPageRendered` callback
2. **Pasar la rotación** a `SelectionOverlay` y `DetectionOverlay`
3. **Transformar coordenadas** según la rotación en `pdfCoordinates.ts`

Ejemplo de transformación para rotación 90°:
```typescript
function rotateCoordinates(bbox: PDFBBox, rotation: number, pageWidth: number, pageHeight: number): PDFBBox {
  if (rotation === 90) {
    return {
      x0: bbox.y0,
      y0: pageWidth - bbox.x1,
      x1: bbox.y1,
      y1: pageWidth - bbox.x0
    }
  }
  // ... otros casos
  return bbox
}
```
