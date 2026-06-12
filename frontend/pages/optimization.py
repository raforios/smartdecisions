'''
    Optimization Page
'''
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import osmnx as ox
import plotly.express as px
import folium
from streamlit_folium import st_folium #Widget de Streamlit para mostrar los mapas
from folium.plugins import MarkerCluster #Plugin para agrupar marcadores

from services.load_data import get_data, login_api
from utils.data import hexa_color_generator_list, df_animation_multiple_path
from layout.menu import menu

@st.cache_data
def load_dataframes(route_id, day, dist) -> tuple:
    '''
        Load datafroames form API to cache
    '''
    token = login_api()
    data = get_data(token, 'data_model', route_id, day, 1)
    data_final = get_data(token, 'optimal_route', route_id, day, 1, dist)
    data_distances = get_data(token, 'distance_matrix', route_id, day, 2)
    data_route = get_data(token, 'route', route_id, day, 1, dist)

    return data, data_final, data_distances, data_route


st.set_page_config(
    page_title = 'SmartDecisions Optimization',
    page_icon = '🚚',
    layout = 'wide',
    initial_sidebar_state = 'collapsed'
)

st.title('SmartDecisions')
st.header('Optimization')
menu()

st.markdown('### Parameters')
st.text('Se deben ingresar los valores requeridos para generar la optimización')

ROUTE_ID = int(st.number_input('Ingresar el ID de la ruta para el análisis'))
st.caption(f'ID de ruta elegida: **{ROUTE_ID}**.')

week_days = {
    'Lunes': 1,
    'Martes': 2,
    'Miércoles': 3,
    'Jueves': 4,
    'Viernes': 5,
    'Sábado': 6,
    'Domingo': 7,
}
day_lables = list(week_days.keys())
selected_label = st.selectbox('Día de la semana', day_lables)
DAY = week_days[selected_label]
st.caption(f'Has seleccionado: **{selected_label}**.')

RADIO = st.slider('Radio de evalución en metros', min_value = 1500, max_value = 2500, value = 1500)
st.caption(f'El Radio elegido para la evaluación es: **{RADIO}**')

tab1, tab2, tab3, tab4, tab5 = st.tabs(['Initial Data',
                                        'Distances',
                                        'Distance Matrix',
                                        'Start to End',
                                        'Final Route'])

if ROUTE_ID and DAY and RADIO:
    dtf_data, dtf_final, distances, dtf_route = load_dataframes(ROUTE_ID, DAY, RADIO)
    # print(f'DATA: {dtf_data}')
    # print(f'DTF FINAL: {dtf_final}')
    # print(f'DISTANCES: {distances}')
    # print(f'DTF ROUTE: {dtf_route}')

    if 'SERVER ERROR' in dtf_data:
        st.error('### **API ERROR**')
        st.warning(f'''##### No se obtuvo información desde la API
                Parámetros enviados:
                RUTA ID: {ROUTE_ID}
                NÚMERO DE DÍA: {DAY}''')
    else:
        start = dtf_data[dtf_data.index == 0][['y', 'x']].values[0]

        with tab1:
            st.subheader('Data from API')
            st.markdown('#### Data model')
            st.dataframe(dtf_data)

            st.markdown('##### Map')
            st.write(f'starting point: {start}')
            map_draw = folium.Map(location = start, tiles = 'cartodbpositron', zoom_start = 15)

            map_type = st.radio('Tipo de marcadores',options = ['Cluster', 'Individuales'],
                                horizontal = True)

            if map_type == 'Cluster':
                marker_cluster = MarkerCluster().add_to(map_draw)

            for i, row in dtf_data.iterrows():

                marker = folium.CircleMarker(
                    location = [row['y'], row['x']],
                    color = row['color'], fill = True, radius = 8).add_to(map_draw)

                if map_type=='Cluster':
                    marker.add_to(marker_cluster)
                else:
                    marker.add_to(map_draw)

            folium.plugins.Fullscreen(
                    position = 'topright',
                    title = 'Full screen',
                    title_cancel = 'Cancel',
                    force_separate_button = True,
                ).add_to(map_draw)
            out = st_folium(map_draw, height = 600, use_container_width = True)
            st.write(out)

        with tab2:
            st.subheader('Optimal distance algorithm between neighbors')

            if 'SERVER ERROR' in dtf_final:
                st.error('### **API ERROR**')
                st.warning(f'''##### Durante el proceso de optimización no se encontró una ruta
                    óptima o viable
                    Dos o más nodos de los puntos almacenados no tienen proximidad para el algoritmo Dijkstra
                        Parámetros enviados:
                        RUTA ID: {ROUTE_ID}
                        NÚMERO DE DÍA: {DAY}''')
            else:
                st.write(dtf_final)
                route_map = folium.Map(location = start, zoom_start = 16)
                route = []
                size, _ = dtf_final.shape
                for i, row in dtf_final.iterrows() :
                    NUM = f'<b>NUM:</b> {int(i + 1)}<br>'
                    ORIG = f'<b>START:</b> {int(dtf_final.iloc[i]['origin'])}<br>'
                    DEST = f'<b>END:</b> {int(dtf_final.iloc[i]['target'])}<br>'
                    DIST = f'<b>DIST:</b> {round(dtf_final.iloc[i]['distance'], 2)} m<br>'
                    POPUP = f'{NUM}{ORIG}{DEST}{DIST}'
                    folium.Marker(location = [row['y'], row['x']],
                        icon = folium.Icon(color = 'red' if i == 0 else 'green'
                                        if i == size - 1 else 'cadetblue',
                                        icon = 'home' if i == 0 else 'flag'
                                        if i == size - 1 else 'info-sign'),
                        tooltip = POPUP).add_to(route_map)
                    lines = (row['y'], row['x'])
                    route.append(lines)

                line = folium.PolyLine([route], color = 'cadetblue', weight = 3.5, opacity = 0.8)
                route_map.add_child(line)

                # Mostrar el mapa
                out = st_folium(route_map, height = 600, use_container_width = True)
                st.write(out)

        with tab3:
            st.subheader('Distances matrix using graphs')
            df_distances = pd.DataFrame(distances)
            st.dataframe(df_distances)

            heatmap_own = df_distances.copy()
            for col in heatmap_own.columns:
                heatmap_own[col] = heatmap_own[col].apply(lambda x:
                    0.3 if pd.isnull(x) else
                    (0.7 if np.isinf(x) else
                    (0 if x != 0 else 1)) )

            fig, ax = plt.subplots(figsize = (10,5))
            sns.heatmap(heatmap_own, vmin = 0 , vmax = 1 , cbar = False, ax = ax)
            st.pyplot(fig)

        with tab4:
            st.subheader('Maps')
            map_start_end = folium.Map(location = start, zoom_start = 16)
            route = []
            if 'SERVER ERROR' in dtf_final:
                st.error('### **API ERROR**')
                st.warning(f'''##### Durante el proceso de optimización no se encontró una ruta
                    óptima o viable
                    Dos o más nodos de los puntos almacenados no tienen proximidad para el algoritmo Dijkstra
                        Parámetros enviados:
                        RUTA ID: {ROUTE_ID}
                        NÚMERO DE DÍA: {DAY}''')
            else:
                size, _ = dtf_final.shape

                for i, row in dtf_final.iterrows() :
                    NUM = f'<b>NUM:</b> {int(i + 1)}<br>'
                    ORIG = f'<b>START:</b> {int(dtf_final.iloc[i]['origin'])}<br>'
                    DEST = f'<b>END:</b> {int(dtf_final.iloc[i]['target'])}<br>'
                    DIST = f'<b>DIST:</b> {round(dtf_final.iloc[i]['distance'], 2)} m<br>'
                    POPUP = f'{NUM}{ORIG}{DEST}{DIST}'
                    if i == 0 :
                        folium.Marker(location = [row['y'], row['x']],
                                icon = folium.Icon(color = 'red', icon='home'),
                                tooltip = POPUP).add_to(map_start_end)
                    elif i == size - 1 :
                        folium.Marker(location = [row['y'], row['x']],
                                icon = folium.Icon(color = 'green', icon='cloud'),
                                tooltip = POPUP).add_to(map_start_end)

                    lines = (row['y'], row['x'])
                    route.append(lines)

                # Mostrar el mapa
                line = folium.PolyLine([route], color = 'cyan', weight = 3.5, opacity = 0.8)
                map_start_end.add_child(line)

                # Mostrar el mapa
                st.markdown('#### Start To End')
                out = st_folium(map_start_end, height = 600, use_container_width = True)
                st.write(out)

                map_route = folium.Map(location = start, zoom_start = 16)
                for stop in dtf_route.itertuples():
                    initial_stop = stop.Index == 0
                    # marker for current stop
                    icon = folium.Icon(icon = 'home' if initial_stop else 'cloud',
                                    color = 'green' if initial_stop else 'lightgray',
                                    prefix = 'fa')
                    marker = folium.Marker(location = (stop.y, stop.x),
                        icon = icon,
                        tooltip = f'<b>Name</b>: {stop.origin} <br>' \
                            + f'<b>Stop number</b>: {stop.Index} <br>'
                    )

                    # line for the route segment connecting current to next stop
                    line = folium.PolyLine(
                        locations = [(stop.y, stop.x),
                                (stop.y_next, stop.x_next)],
                        # display the start, end, and distance of each segment
                        tooltip = f'<b>From</b>: {stop.origin} <br>' \
                            + f'<b>To</b>: {stop.target} <br>' \
                            + f'<b>Time</b>: {stop.time_seg:.0f} m',
                    )
                    # add elements to the map
                    marker.add_to(map_route)
                    line.add_to(map_route)

                    # add route's last marker, as it wasn't included in for loop
                    folium.Marker(
                        location = (stop.y_next, stop.x_next),
                        tooltip = f'<b>Name</b>: {stop.target} <br>' \
                            + f'<b>Stop number</b>: {stop.Index + 1} <br>',
                        icon = folium.Icon(icon = 'info-sign', color = 'cadetblue')
                    ).add_to(map_route)

                # Mostrar el mapa
                st.markdown('#### Start To End step by step')
                out = st_folium(map_route, height = 600, use_container_width = True)
                st.write(out)

        with tab5:
            st.subheader('Final route with optimization algorithm')
            st.markdown('#### Data Optimized')
            if 'SERVER ERROR' in dtf_final:
                st.error('### **API ERROR**')
                st.warning(f'''##### Durante el proceso de optimización no se encontró una ruta
                    óptima o viable
                    Dos o más nodos de los puntos almacenados no tienen proximidad para el algoritmo Dijkstra
                        Parámetros enviados:
                        RUTA ID: {ROUTE_ID}
                        NÚMERO DE DÍA: {DAY}''')
            else:
                dtf_route.index.name = 'visit_order'
                st.dataframe(dtf_route)

                G = ox.graph_from_point(start, dist = RADIO, network_type = 'drive')
                G = ox.add_edge_speeds(G)
                G = ox.add_edge_travel_times(G)

                lst_routes = dtf_route['route'].tolist()
                route_colors = hexa_color_generator_list(len(lst_routes))
                route_linewidths = [4 for _ in  range(len(lst_routes))]
                df_filtrado = dtf_route.copy()

                lst_routes = df_filtrado['route'].tolist()
                route_colors = hexa_color_generator_list(len(lst_routes))
                route_linewidths = [2 for _ in  range(len(lst_routes))]

                df = pd.DataFrame({
                                'origin': 0,
                                'target': 0,
                                'x': 0,
                                'y': 0,
                                'x_next': 0,
                                'y_next': 0,
                                'distance': 0,
                                'time_seg': 0},
                                index = [0])

                tmp = df_animation_multiple_path(G, lst_routes, df)
                df = pd.concat([df, tmp], axis = 0)
                df = df.reset_index(drop = True)
                df = df.drop(index = 0)

                first_node, last_node = lst_routes[0][0], lst_routes[-1][-1]
                df_start = df_filtrado[df_filtrado['origin_node'] == first_node]
                df_end = df_filtrado[df_filtrado['destination_node'] == last_node]

                fig = px.scatter_map(data_frame = df, lon = 'x', lat = 'y', zoom = 15,
                            width = 1500,
                            height = 1000, animation_frame = 'id', map_style = 'carto-positron')

                fig.data[0].marker = {'size': 12, 'color': 'blue'}

                fig.add_trace(px.scatter_map(data_frame = df, lon = 'x', lat = 'y').data[0])
                fig.data[1].marker = {'size': 10, 'color': 'black'}

                fig.add_trace(px.scatter_map(data_frame = df_start, lon = 'x', lat = 'y').data[0])
                fig.data[2].marker = {'size': 15, 'color': 'red'}

                fig.add_trace(px.scatter_map(data_frame = df_end, lon = 'x', lat = 'y').data[0])
                fig.data[3].marker = {'size': 15, 'color': 'green'}

                fig.add_trace(px.line_map(data_frame = df, lon = 'x', lat = 'y').data[0])

                st.markdown('#### Final Route Map')

                st.markdown('#### Summary')
                NUMBER_STOPS = 'Num stops'
                TOTAL_DISTANCE = 'Distance'
                TOTAL_TIME = 'Duration Time'
                n_stops = dtf_route['origin'].size
                time_distance = float(dtf_route['time_seg'].sum()/60)
                distance = float(dtf_route['distance'].sum())
                st.write(f'**{NUMBER_STOPS}:** {n_stops}')
                st.write(f'**{TOTAL_TIME}:** {time_distance:.2f} minutes')
                st.write(f'**{TOTAL_DISTANCE}:** {distance:.2f} meters')
