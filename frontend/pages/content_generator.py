'''
    Content Generator Page
'''
import streamlit as st
# import pandas as pd
from openai import OpenAI as ai

# from utils.environment import PARAMETERS
from layout.menu import menu
# from utils.create_office_files import create_word_doc

# client = ai(api_key = PARAMETERS.get('OPENAI_KEY'))
client = ai(api_key = st.secrets['OPENAI_KEY'])

def article_generator(subject):
    '''
        Article generator from OpenAI using parameters
    '''
    try:
        response = client.chat.completions.create(
            model = 'gpt-4o',
            messages = [
                {
                    'role': 'system',
                    'content': 'Eres un experto en redacción de artículos SEO.' 
                },
                {
                    'role': 'user',
                    'content': f'Escribe un artículo optimizado para SEO sobre: {subject}' 
                }
            ],
            max_tokens = 1000
        )
        print('RESPONSE:')
        print(response)
        return response.choices[0].message.content.strip()
    except IOError as error:
        st.error(f'Error from OpenAI API: {str(error)}')
        return None


st.set_page_config(
    page_title = 'Content Generator',
    page_icon = '💿',
    layout = 'wide',
    initial_sidebar_state = 'collapsed'
)

st.title('SmartDecisions')
st.header('Content Generator GPT-4o')
menu()

tab1, tab2, tab3, = st.tabs(['Código',
                            'Tablas de Datos',
                            'Artículos'])

with tab1:
    st.subheader('Generación de Código')

    title = st.text_input('Ingresa el título del artículo:')
    topic = st.text_input('Ingresa un tema para el artículo:')

    if st.button('Generar'):
        if topic and title:
            with st.spinner('Generando artículo...'):
                article = article_generator(topic)
                if article:
                    st.success('Succesfully created!')
                    st.markdown('#### Vista previa:')
                    st.markdown(title)
                    st.markdown(article)


with tab2:
    st.subheader('Generación de Tablas de Datos')
    st.markdown('FALTA')

with tab3:
    st.subheader('Generación de Artículos')
    st.markdown('FALTA')
