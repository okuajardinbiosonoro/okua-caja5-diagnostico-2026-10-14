"""Close the evidence inventory without changing signals, reports or devices."""
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NOW = datetime.now(timezone.utc).isoformat()
SOIL_ID = "C-EB5-soil-four-plants-01"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


soil_dir = ROOT / "trials" / SOIL_ID
soil = read(soil_dir / "analysis.json")
report = soil["operator_report"]["report"]

# Do not silently turn the unchecked global confirmations into positive labels.
assert report["followed_cues"] is False
assert report["grounded_black_kept_fixed"] is False
assert all(block["confirmed_contacts"] for block in report["block_reports"])

phase_summary = []
for phase in soil["phases"]:
    nodes = {}
    for node, data in phase["nodes"].items():
        metrics = data["metrics"]
        nodes[node] = {
            "frames": data["frames"],
            "stable_frames": data["stable_frames"],
            "stable_native_filt": metrics.get("filt"),
            "stable_adc_mean": metrics.get("rms_mean"),
            "stable_occupancy": metrics.get("occupancy"),
            "stable_adc_peak": metrics.get("adc_peak"),
            "full_phase_active_fraction": data["active_fraction"],
            "full_phase_note_ons": data["midi_note_ons"],
            "full_phase_midi_held_s": data["midi_note_duration_s"],
            "max_gap_including_boundaries_s": (data.get("coverage") or {}).get(
                "max_gap_including_boundaries_s"
            ),
        }
    phase_summary.append({
        "phase": phase["phase"],
        "plant_block": phase["repetition"],
        "planned_plant": phase["sequence_step"].get("plant_node"),
        "planned_black": phase["sequence_step"].get("black_node"),
        "start_utc": phase["start_utc"],
        "end_utc": phase["end_utc"],
        "stable_start_utc": phase["stable_start_utc"],
        "stable_end_utc": phase["stable_end_utc"],
        "nodes": nodes,
    })

qualifications = {
    "recorded_at_utc": NOW,
    "raw_reports_and_recording_preserved": True,
    "complete_planned_continuous_contact_labels": False,
    "original_global_fields": {
        "followed_cues": report["followed_cues"],
        "grounded_black_kept_fixed": report["grounded_black_kept_fixed"],
    },
    "individual_contact_blocks_confirmed": [b["node"] for b in report["block_reports"]],
    "ground_state": {
        "placement_confirmed": True,
        "reported_soil": "Sustrato de maceta EB5, levemente húmedo, profundidad 3 cm",
        "end_state_confirmed_in_chat": "El negro EB5 sigue enterrado",
        "unchanged_throughout_run": "No confirmado por el campo global del formulario; no inferirlo del estado final",
    },
    "per_node": {
        "EB5": {
            "use": "Contacto individual confirmado; sin respuesta audible ni MIDI en la ventana prevista",
            "release_label": "El no en silencio al soltar es ambiguo: tampoco hubo sonido inicial. No clasificarlo como nota atascada",
        },
        "EC5": {
            "use": "Respuesta exploratoria a planta y planta+negro",
            "continuous_hold": False,
            "reason": "El operador soltó y volvió a tocar repetidamente para generar notas; instantes exactos no registrados",
        },
        "EE5": {
            "use": "Respuesta exploratoria a planta y planta+negro",
            "continuous_hold": "No demostrado",
            "reason": "Notas describen respuesta al inicio, similar al caso anterior; no inventar tiempos de recontacto",
        },
        "EF5": {
            "use": "Respuesta exploratoria, principalmente con negro+planta",
            "continuous_hold": False,
            "reason": "El operador informa soltar y apretar; no usar los 20 s como contacto físico continuo",
        },
        "ED5": {
            "use": "Observación exploratoria del operador fuera de protocolo",
            "exact_contact_timing": "Desconocido",
            "reason": "No atribuir automáticamente sus notas durante bloques EE5/EF5 a activación espontánea o interferencia",
        },
    },
    "comparison_limit": "Ensayos previos EB5/EC5 mayormente sentado; corrida en tierra de pie con zapatos. Las comparaciones de contacto entre ambas condiciones también cambian postura. La referencia aire/tierra dentro de esta corrida mantiene la postura prevista",
}
save(soil_dir / "correction.json", {
    "recorded_at_utc": NOW,
    "void_planned_trial": False,
    "scientific_qualifications": qualifications,
    "processing_note": "Estas anotaciones requieren lectura explícita al usar los datos; no sustituyen el clasificador global conservador de analysis.json",
})
save(soil_dir / "interpretation.json", {
    "trial_id": SOIL_ID,
    "recorded_at_utc": NOW,
    "operator_report_verbatim": report,
    "qualifications": qualifications,
    "findings": [
        "Antes del enterrado, la referencia de 120 s presenta señal no nula en EB5, EC5, EE5 y EF5; ED5 emite 9924 NoteOn",
        "Durante 120 s de estabilización y los siguientes 120 s de referencia tras el enterrado, filt es cero en todas las muestras registradas de los cuatro nodos; EB5/EC5 también registran ocupación y pico ADC cero. Los cinco canales registran cero NoteOn",
        "Los cinco nodos siguen en línea, sin disminución de uptime; no hay huecos de telemetría mayores de un segundo en esta corrida",
        "EB5 no responde en su bloque. EC5, EE5 y EF5 presentan respuestas breves según la modalidad y los recontactos descritos por el operador",
        "La caída compartida de señal coincide con el cambio de referencia física común. No demuestra fallo de conectividad ni permite atribuir toda la pérdida a umbrales del firmware",
        "Un ADC en cero no prueba voltaje analógico cero: el circuito bipolar entra a un ADC unipolar sin desplazamiento de nivel dibujado",
    ],
    "metric_note": "Las métricas son de la ventana estable indicada, mientras notas y tiempo MIDI abarcan la fase completa. filt de EB5/EC5 es RMS; EE5/EF5 usan otra implementación. MIDI sostenido no equivale a audio grabado",
    "phase_summary": phase_summary,
    "runtime": soil["runtime"],
    "data_quality": soil["data_quality"],
})

inventory = []
for path in sorted((ROOT / "trials").glob("*/analysis.json")):
    data = read(path)
    correction_path = path.parent / "correction.json"
    correction = read(correction_path) if correction_path.exists() else None
    inventory.append({
        "trial_id": data["trial_id"],
        "analysis_path": str(path),
        "start_utc": data.get("start_utc"),
        "end_utc": data.get("end_utc"),
        "validity": data.get("validity"),
        "correction": correction,
    })

handoff = {
    "title": "Caja 5: cierre de diagnóstico y trabajo remoto sobre firmware",
    "recorded_at_utc": NOW,
    "decision": "Hay material suficiente para desarrollar y evaluar una versión candidata usando los registros. No demuestra detección definitiva en todos los días, plantas y posturas",
    "operator_constraint": "No habrá operador presencial en la próxima sesión. No solicitar nuevas pruebas manuales; usar las grabaciones y sus limitaciones",
    "session_state": {
        "physical_tests_finished": True,
        "collector_and_timer_stopped": True,
        "firmware_and_Ableton_changed_during_20261014": False,
        "glass": "Instalado según condición de preparación",
        "black_EB5": "Permanece enterrado en maceta EB5 según última confirmación",
        "other_black_tips": "Último estado previsto libres; no inspeccionados de nuevo al cerrar",
        "last_test_posture": "De pie con zapatos",
    },
    "hardware_basis": {
        "review": str(ROOT.parent / "hardware_actual_20261014" / "revision_hardware.json"),
        "model": str(ROOT.parent / "hardware_actual_20261014" / "modelo_ideal_verificado.json"),
        "power": "Fuente compartida ±9 V y GND; cada baquela regula alimentación del ESP32",
        "electrodes": "J2 azul: rojo señal de planta; negro GND común entre los cinco nodos. Negro de alimentación J1 es -9 V y no es el electrodo negro",
        "analogue": "TL074, seguidor y filtros pasan banda aproximadamente 0.459–109.28 Hz; sin notch 60 Hz en el modelo ideal",
        "ADC": "GPIO32, lectura unipolar. Esquema no dibuja offset ni protección del ADC frente a la salida bipolar; no interpretar códigos cero como ausencia demostrada de señal analógica",
        "TIP32": "Conexión física aclarada y confirmada por el usuario; no reabrir esa duda sin evidencia nueva",
        "uncertain": "No medidos: tensiones reales de riel, impedancia cuerpo/suelo, unión chasis/tierra, señal bipolar antes del ADC",
    },
    "current_nodes": [
        {"node": "EB5", "id": 21, "last_IP": "192.168.88.217", "MIDI_channel": 6, "version": "1.1.13-box5-touch-pilot", "diagnostics": "PLANTDIAG", "OTA": "Disponible en pruebas previas"},
        {"node": "EC5", "id": 22, "last_IP": "192.168.88.254", "MIDI_channel": 7, "version": "1.1.13-box5-touch-pilot", "diagnostics": "PLANTDIAG", "OTA": "Disponible en pruebas previas"},
        {"node": "ED5", "id": 23, "last_IP": "192.168.88.253", "MIDI_channel": 8, "version": "1.0", "diagnostics": "Solo estado CKv2 y MIDI, sin PLANTDIAG", "OTA": "No verificado; no asumir que tiene OTA"},
        {"node": "EE5", "id": 24, "last_IP": "192.168.88.249", "MIDI_channel": 9, "version": "1.1.7-box5-touch-two-tier", "diagnostics": "PLANTDIAG", "OTA": "Disponible en pruebas previas"},
        {"node": "EF5", "id": 25, "last_IP": "192.168.88.250", "MIDI_channel": 10, "version": "1.1.11-box5-touch-two-tier", "diagnostics": "PLANTDIAG", "OTA": "Disponible en pruebas previas"},
    ],
    "recording": {
        "signals": str(ROOT / "captura_completa" / "signals.jsonl"),
        "markers": str(ROOT / "captura_completa" / "markers.jsonl"),
        "sensor_frames_from_collector_counters": 1390319,
        "ckv2_samples_from_collector_counters": 68440,
        "MIDI_messages_from_collector_counters": 159600,
        "meaning": "Contadores de las dos ejecuciones del colector principal; no son número de toques independientes",
        "contents": "Resumen de adquisición, parámetros del detector, activación, MIDI, estado CKv2, indicaciones temporizadas y observaciones del operador",
        "not_recorded": "Audio continuo ni forma de onda ADC completa; los tiempos de toque siguen indicaciones, no un sensor físico externo",
        "metric_schema": str(ROOT / "telemetry_schema.json"),
        "metric_warning": "EB5/EC5: rms_mean es media aritmética; filt es RMS. No aplicar esa equivalencia a EE5/EF5 sin revisar sus fuentes",
        "cross_day_limit": "La sesión controlada es de un solo día; historias previas no equivalen a validación etiquetada entre días",
    },
    "main_findings": [
        {
            "finding": "Tocar solo un negro, propio o cruzado EB5/EC5, puede activar los cinco nodos antes de tocar una planta",
            "evidence": "Comparaciones EB5/EC5 de negro solo y orden de contacto",
            "firmware_implication": "La respuesta compartida de GND no identifica por sí sola la planta tocada. Un detector local puede carecer de información para separar contacto propio de cambio común",
        },
        {
            "finding": "La respuesta a planta sola existe en algunas repeticiones y falta en otras",
            "evidence": "EB5 planta sola: NoteOn 2/0/18 en tres contactos. EC5 planta sola: operador oye 2/3; una recuperación conserva MIDI 29.168 s de una ventana de 30 s",
            "firmware_implication": "Evaluar sensibilidad, referencia aprendida, falsos positivos y recuperación juntos; bajar un umbral no resuelve todos los fallos",
        },
        {
            "finding": "La referencia congelada y el reinicio del detector a los 30 s merecen corrección",
            "evidence": "Fuente del piloto y transiciones de B-EC5-plant-only-01: una activación continúa aproximadamente 30.009 s; no coincide con reinicio de la placa",
            "firmware_implication": "Evitar aprender una referencia durante un transitorio o mantener actividad por una referencia antigua. Es un mecanismo observado, no explicación única de todo el sistema",
        },
        {
            "finding": "Con negro EB5 en sustrato, la referencia registrada cae a cero en los cuatro nodos observados y ED5 deja de emitir MIDI; los contactos siguientes son mayormente breves",
            "evidence": str(soil_dir / "interpretation.json"),
            "firmware_implication": "Distinguir estado de adquisición sin información de contacto real. No fabricar sostenimiento de contacto si reposo y contacto producen las mismas características observadas",
        },
    ],
    "data_use_rules": [
        "Conservar y leer las correcciones de cada ensayo; excluir las pruebas de planta equivocada y el arranque interrumpido sin contacto",
        "Conservar contactos terminados antes de una anulación final; excluir únicamente los intervalos contaminados documentados",
        "La tercera indicación de EC5 negro primero llegó 4.347 s tarde; la ventana estable ajustada es corta. No equipararla sin ponderación a las otras dos",
        "La corrida en tierra sirve como evidencia exploratoria y de cambio de referencia; EC5/EF5 tuvieron recontactos sin tiempos exactos y EE5 es ambiguo. No etiquetar 20 s completos como contacto físico sostenido",
        "ED5 fue tocado adicionalmente fuera del protocolo final; su momento es desconocido. No clasificar sus notas coincidentes como falsos positivos sin esa salvedad",
        "No hay serie sistemática de EE5/EF5 con todos los negros libres equivalente a la de EB5/EC5; tampoco ADC detallado de ED5",
        "No llamar audio a la duración MIDI; una nota puede permanecer sostenida sin nuevos NoteOn",
    ],
    "trial_inventory": inventory,
    "next_remote_session": [
        {
            "step": 1,
            "work": "Leer este cierre, esquema y correcciones; resolver IP e identidad actuales, registrar versión y configuración sin cambiar Ableton ni cableado",
        },
        {
            "step": 2,
            "work": "Reproducir cronológicamente las características registradas de EB5 y EC5. Usar intervalos completos para conservar adaptación y estado; respetar huecos. No simular muestras ADC de 2 ms que no fueron grabadas",
        },
        {
            "step": 3,
            "work": "Comparar el detector instalado con candidatos adaptativos. Separar bloques completos para ajuste y evaluación, incluyendo ambos órdenes y negros cruzados; no dividir aleatoriamente muestras contiguas",
            "metrics": ["Activaciones en reposos confirmados por unidad de tiempo", "Contactos confirmados con y sin respuesta", "Sostenimiento durante contactos limpios", "Tiempo de recuperación al soltar", "Recalibraciones y sensibilidad a referencias colapsadas"],
        },
        {
            "step": 4,
            "work": "Diseñar aprendizaje de referencia/ruido con calidad de adquisición, estados de candidato/contacto/recuperación y revisión del corte de 30 s. Mantener variación musical mientras la evidencia permita contacto; evitar umbrales absolutos ajustados a una planta concreta",
            "limit": "La telemetría disponible permite probar decisiones sobre características, no validar nuevos filtros de forma de onda completa. Si dos situaciones entregan los mismos datos locales, el firmware no puede distinguirlas con certeza",
        },
        {
            "step": 5,
            "work": "Si se propone usar simultaneidad entre nodos, definir explícitamente un coordinador o intercambio de datos. No asumir que cada ESP32 ya recibe la señal de los demás",
        },
        {
            "step": 6,
            "work": "Antes de OTA, conservar binarios y configuración exactos actualmente instalados, hashes y procedimiento de reversión. Resolver IP en cada operación y confirmar identidad. Probar compilación y reproducción de registros antes de desplegar candidatos por etapas en EB5/EC5",
            "rollback_warning": "Las reversiones previas apuntan a 1.1.12; no son la reversión exacta de los pilotos 1.1.13 actuales. El destino antiguo EB5 .252 está obsoleto",
        },
        {
            "step": 7,
            "work": "Mantener estructura de red/MIDI/OTA. Verificar versión, arranque y comunicación remotamente tras cualquier despliegue futuro. Dejar explícitamente pendiente la confirmación física/audible y estabilidad entre días, porque no habrá operador presencial",
        },
        {
            "step": 8,
            "work": "Tratar ED5 como objetivo independiente de base musical y eventual modulación al tocar. No alterar Ableton ni prometer OTA/ADC detallado en ED5 hasta verificar que ese nodo lo permita",
        },
    ],
    "outcome_now": "Evidencia cerrada y organizada; no se instaló un firmware nuevo ni se efectuaron nuevas pruebas físicas al cerrar",
}
save(ROOT / "firmware_remote_handoff.json", handoff)

recordings = read(ROOT / "recording_sessions.json")
recordings["continued_capture"].update({
    "closed_at_or_before_utc": NOW,
    "stopped_by_operator_request": True,
    "exit_code": 0,
    "sensor_frames": 1055215,
    "ckv2_samples": 51940,
    "midi_messages": 149416,
})
recordings["main_recording_total_counters"] = handoff["recording"]
# Retain counts only, not repeated paths and methodological text, in the counters field.
recordings["main_recording_total_counters"] = {
    k: handoff["recording"][k] for k in [
        "sensor_frames_from_collector_counters", "ckv2_samples_from_collector_counters",
        "MIDI_messages_from_collector_counters"
    ]
}
save(ROOT / "recording_sessions.json", recordings)

closure = read(ROOT / "session_closure.json")
closure.update({
    "collector_exit_code": 0,
    "controller_exit_code": 0,
    "stop_flags_present": {
        "collector": (ROOT / "captura_completa" / "stop").exists(),
        "controller": (ROOT / "stop_controller").exists(),
    },
    "evidence_handoff": str(ROOT / "firmware_remote_handoff.json"),
    "soil_interpretation": str(soil_dir / "interpretation.json"),
    "documentation_finished_at_utc": NOW,
})
save(ROOT / "session_closure.json", closure)
with (ROOT / "captura_completa" / "markers.jsonl").open("a", encoding="utf-8") as stream:
    stream.write(json.dumps({
        "at_utc": NOW,
        "kind": "evidence_closure_and_remote_handoff",
        "soil_trial_id": SOIL_ID,
        "raw_operator_confirmations_preserved": True,
        "handoff": str(ROOT / "firmware_remote_handoff.json"),
        "new_physical_tests": False,
        "device_or_Ableton_changes": False,
    }, ensure_ascii=False) + "\n")

print(json.dumps({
    "handoff": str(ROOT / "firmware_remote_handoff.json"),
    "analysed_trials": len(inventory),
    "soil_original_flags_retained": True,
    "stop_flags_present": closure["stop_flags_present"],
}, ensure_ascii=True))
