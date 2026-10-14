# Datos crudos del diagnóstico de caja 5

Capturas de OKUA del 14 de octubre de 2026, con telemetría simultánea, MIDI, indicaciones temporizadas, confirmaciones del operador y documentación del hardware. Los registros incluyen el arranque inicial, los periodos entre ensayos y las pruebas anuladas. Los archivos originales conservan sus valores, orden y finales de línea.

**Configuración prevista para el próximo firmware: negro EB5 enterrado en el sustrato de su maceta.** El operador informó que esa configuración dio el mejor funcionamiento en pruebas adicionales realizadas fuera de las indicaciones coordinadas. Sus instantes y modalidades exactos no quedaron etiquetados. La observación está guardada en `operator_addendum_grounded_EB5.json` y se incorpora al plan de firmware.

## Descargar todos los originales

[Descargar el ZIP completo con los archivos originales](https://github.com/okuajardinbiosonoro/okua-caja5-diagnostico-2026-10-14/releases/download/datos-2026-10-14/OKUA_Caja5_datos_crudos_2026-10-14.zip)

Descomprime ese ZIP en el PC de casa. Contiene `signals.jsonl` completo, sin dividir, y los demás archivos de la sesión con sus rutas originales. Su compresión es sin pérdida. `dataset_manifest.json` identifica tamaños y SHA256; `release_asset_integrity.json` en el repositorio identifica el ZIP de descarga.

## Recuperar los datos desde el repositorio

También puedes usar **Code → Download ZIP** o clonar el repositorio. La captura principal está incluida como partes JSONL de hasta 32 MiB, separadas en límites de línea. No se omiten registros ni se modifican valores. GitHub limita los archivos individuales grandes; la división permite conservar los datos directamente en el repositorio. [Límites de archivos de GitHub](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github).

Con Python 3, desde la carpeta del repositorio:

```text
python tools/reconstruct.py --verify-only
python tools/reconstruct.py --output restored
```

El primer comando comprueba todos los originales contra el manifiesto, concatenando las partes en memoria de forma secuencial. El segundo guarda la reconstrucción en `restored`. Verifica cada parte y el archivo completo mediante SHA256. No necesita paquetes adicionales ni acceso a los nodos.

## Contenido

| Ruta | Contenido |
| --- | --- |
| `diagnostics/caja5_diagnostico_reproducible_20261014/captura_completa/` | Captura principal íntegra y marcas temporales originales |
| `diagnostics/caja5_diagnostico_reproducible_20261014/captura_1700Z/` | Arranque inicial conservado íntegro |
| `diagnostics/caja5_diagnostico_reproducible_20261014/trials/` | Análisis derivados, confirmaciones, correcciones e interpretación de cada ensayo |
| `diagnostics/caja5_diagnostico_reproducible_20261014/telemetry_schema.json` | Significado verificado de las métricas |
| `diagnostics/caja5_diagnostico_reproducible_20261014/firmware_remote_handoff.json` | Hallazgos, configuración prevista y plan para la sesión remota |
| `diagnostics/hardware_actual_20261014/` | PDFs, modelo y revisión del circuito y la fuente |
| `hardware_original/` | Paquete original del hardware aportado por el usuario |
| `dataset_manifest.json` | Inventario y hashes de todos los archivos originales publicados |

Las confirmaciones y observaciones se conservan dentro de `markers.jsonl` y en los análisis de los ensayos. Los informes derivados acompañan a los registros originales. Las correcciones y los informes anteriores a la corrección también están incluidos.

## Interpretar los registros

Los JSONL contienen exactamente los registros que guardó el colector: campos de PLANTDIAG, estado de CKv2 y mensajes MIDI. No incluyen audio continuo ni una forma de onda ADC completa. Los tiempos de contacto corresponden a indicaciones y respuestas del operador.

En EB5 y EC5 con firmware `1.1.13-box5-touch-pilot`, **`filt` es RMS y `rms_mean` es media aritmética** de la ventana ADC. Esa equivalencia debe comprobarse por separado en las otras versiones. Los códigos ADC cero no demuestran voltaje analógico cero en el circuito bipolar. MIDI sostenido tampoco equivale a una grabación de sonido.

Para evaluar detección, usa las correcciones de cada ensayo: contactos adicionales, una prueba con la planta equivocada, una interrupción de arranque y una indicación demorada. En la corrida final con negro EB5 enterrado, el operador soltó y volvió a tocar para obtener notas; esos periodos no tienen etiquetas fiables de contacto continuo. El contacto adicional con ED5 fue exploratorio y no tiene un instante exacto registrado.

EB5 y EC5 tienen la serie de ensayos más completa. EE5 y EF5 tienen telemetría simultánea y la corrida final en tierra. ED5 tiene estado y MIDI, sin la misma telemetría detallada de ADC. El plan contempla una próxima sesión remota usando estos registros; la estabilidad entre días permanece pendiente de demostración.

El manifiesto enumera dos cachés de bytecode Python excluidas. No se elimina ninguna captura por ser inválida, incompleta o discordante con un informe.
