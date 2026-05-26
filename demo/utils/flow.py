import logging
from graphviz import Digraph

logging.basicConfig(level = logging.INFO)
logger = logging.getLogger(__name__)

def generate_process_flowchart():
    '''Generates the process flowchart using Graphviz with corrected edge tuples.'''
    try:
        message = 'Starting flowchart generation'
        logger.info(message)

        flow = Digraph(name = 'ProcessFlow', format = 'png')
        flow.attr(rankdir = 'TB', splines = 'ortho')
        flow.attr('node', shape = 'box', style = 'rounded')

        with flow.subgraph(name = 'cluster_0') as stage_1:
            stage_1.attr(label = '1. Preparacion, coordinacion y contratacion')
            stage_1.node('1.1', '1.1 Coordinar Cronograma\n(UCS - 1 dia)')
            stage_1.node('1.2', '1.2 Aprobar Cronograma\n(UCS - 1 dia)')
            stage_1.node('1.3', '1.3 Coordinar con areas\n(UCS - 4 dias)')
            stage_1.edges([('1.1', '1.2'), ('1.2', '1.3')])

        with flow.subgraph(name = 'cluster_1') as stage_2:
            stage_2.attr(label = '2. Convocatoria y realizacion')
            stage_2.node('2.1', '2.1 Convocatoria a medios\n(UCS - 1 dia)')
            stage_2.node('2.5', '2.5 Linea grafica y coordinacion\n(MAE/Viceministros)')
            stage_2.node('2.6', '2.6 Gestion de prensa post evento\n(UCS - 2 dias)')
            stage_2.edges([('2.1', '2.5'), ('2.5', '2.6')])

        with flow.subgraph(name = 'cluster_2') as stage_3:
            stage_3.attr(label = '3. Difusion, distribucion y archivo')
            stage_3.node('3.1', '3.1 Notas de prensa\n(UCS)')
            stage_3.node('3.2', '3.2 Portal del MMM\n(UCS)')
            stage_3.node('3.4', '3.4 Archivo fotografico\n(UCS)')
            stage_3.edges([('3.1', '3.2'), ('3.2', '3.4')])

        flow.edge('1.3', '2.1')
        flow.edge('2.6', '3.1')

        flow.render('process_flowchart', view = False)
        
        message = 'Flowchart successfully generated and saved'
        logger.info(message)

    except Exception as error:
        error_msg = f'Error during flowchart generation: {error}'
        logger.error(error_msg)

if __name__ == '__main__':
    generate_process_flowchart()
    