"""A single external soil-contact experiment, with explicitly labelled intervals."""
NODES=('EB5','EC5','EE5','EF5')
VOICES={'EB5':'e be cinco','EC5':'e ce cinco','EE5':'e e cinco','EF5':'e efe cinco'}
REST='Ambas manos libres: no toques ninguna planta, punta negra ni el sustrato. El negro EB5 permanece enterrado y fijo; los otros negros quedan libres salvo cuando la indicacion pida tocarlos.'

def build_steps():
    steps=[]
    def add(phase,seconds,block,title,instruction,spoken,plant=None,black=None,posture='standing',condition='no_contact',ground='soil_EB5_pot'):
        steps.append({'step_index':len(steps),'phase':phase,'duration_s':seconds,
                      'repetition':block,'block_node':plant if block else None,
                      'plant_node':plant,'black_node':black,'condition':condition,
                      'posture':posture,'ground_state':ground,
                      'instruction':{'title':title,'instruction':instruction,'spoken':spoken}})
    add('preparation',10,0,'PREPARATE: NEGROS AL AIRE',
        'Ponte de pie con zapatos para toda la corrida. Todos los negros, incluido EB5, estan al aire. Ambas manos libres. No entierres nada hasta el aviso.',
        'Preparate de pie con zapatos. Todos los negros al aire. No toques nada.',ground='all_black_free')
    add('air_reference',120,0,'REFERENCIA: TODOS AL AIRE',
        'Ambas manos libres, sin tocar plantas ni negros. Todos los negros siguen al aire durante dos minutos.',
        'Referencia con todos los negros al aire. No toques nada durante dos minutos.',ground='all_black_free')
    add('ground_placement',60,0,'ENTIERRA SOLO NEGRO EB5',
        'Coloca solo la parte metalica de la punta negra marcada EB5 en el sustrato de la maceta EB5, sin abrir el vidrio ni cambiar conexiones. No toques ninguna planta. Deja el negro fijo, suelta todo y pulsa «EB5 enterrado; manos libres». Hay hasta 60 segundos; la siguiente fase empieza al confirmar.',
        'Ahora entierra solo el negro e be cinco en la maceta e be cinco. Dejalo fijo, suelta todo y pulsa el boton de confirmacion.',
        black='EB5',condition='placement_transient',ground='placement_in_progress')
    add('soil_settle',120,0,'ESTABILIZACION: EB5 ENTERRADO',REST+' Espera dos minutos.',
        'Negro e be cinco enterrado. Estabilizacion durante dos minutos. Manos libres.')
    add('soil_reference',120,0,'REFERENCIA: EB5 ENTERRADO',REST+' Referencia durante dos minutos.',
        'Referencia con negro e be cinco enterrado. No toques nada durante dos minutos.')
    for block,plant in enumerate(NODES,1):
        voice=VOICES[plant]
        posture='standing'
        if block>1:
            position='sentado' if posture.startswith('seated') else 'de pie con los mismos zapatos'
            add('change_node',30,block,f'PREPARA {plant}',
                f'Suelta todo y acomodate {position} junto a la planta de etiqueta roja {plant}. No toques plantas ni negros. No muevas el negro EB5 enterrado. La siguiente indicacion es reposo.',
                f'Suelta todo y prepara la planta {voice}, {position}. Todavia no toques nada.',
                plant=plant,posture=posture,condition='posture_or_position_transition')
        add('rest',20,block,f'REPOSO ANTES DE {plant}',REST,
            f'Reposo para {voice}. Ambas manos libres.',plant=plant,posture=posture)
        if plant=='EB5':
            add('contact',20,block,'SOLO PLANTA EB5',
                'Toca SOLO la planta identificada por rojo EB5 con una mano durante 20 segundos. La otra mano queda libre. No toques ningun negro. El negro EB5 sigue enterrado, sin moverlo.',
                'Toca solo la planta e be cinco. La otra mano libre. No toques ningun negro.',
                plant=plant,posture=posture,condition='plant_only_with_black_in_soil')
        else:
            add('first_contact',20,block,f'1. SOLO PLANTA {plant}',
                f'Toca SOLO la planta identificada por rojo {plant} con una mano durante 20 segundos. La otra mano queda libre; no toca ningun negro. Manten la planta hasta la siguiente fase.',
                f'Primero toca solo la planta {voice}. La otra mano libre, sin tocar negros.',
                plant=plant,posture=posture,condition='plant_only_with_EB5_black_in_soil')
            add('contact',20,block,f'2. AGREGA NEGRO {plant}',
                f'SIN SOLTAR la planta de rojo {plant}, toca la punta negra marcada {plant} con la otra mano. Manten ambos contactos durante 20 segundos. El negro EB5 sigue enterrado; no lo toques ni lo muevas.',
                f'Sin soltar la planta {voice}, agrega su negro {voice} con la otra mano. Manten ambos contactos.',
                plant=plant,black=plant,posture=posture,condition='own_pair_with_EB5_black_in_soil')
        release=f'Suelta la planta {plant}' if plant=='EB5' else f'Suelta AMBOS: planta {plant} y negro {plant}'
        add('release',30,block,f'SUELTA {plant}',release+'. '+REST,
            f'Suelta la planta {voice}. Ambas manos libres.' if plant=='EB5' else f'Suelta planta y negro {voice}. Ambas manos libres.',
            plant=plant,posture=posture,condition='release_recovery')
    add('final_reference',60,0,'REFERENCIA FINAL: EB5 ENTERRADO',REST+' Deja todo quieto durante un minuto. Al terminar, EB5 permanece enterrado para analizar los resultados.',
        'Referencia final. Deja todo quieto durante un minuto. El negro e be cinco sigue enterrado.',posture='standing')
    return steps

def configure(config):
    config.update({'condition':'soil_sequence','plant_node':'EB5','black_node':'EB5',
                   'grounded_black_node':'EB5','soil_location':'substrate_of_EB5_pot',
                   'contact_order':'plant_first','block_count':4,'repetitions_per_plant':1,
                   'fixed_posture':'standing','fixed_footwear':'shoes',
                   'sequence_steps':build_steps(),
                   'ground_is_protective_earth':'not_verified',
                   'end_condition':'Leave black EB5 fixed in soil pending analysis'})
    return config
