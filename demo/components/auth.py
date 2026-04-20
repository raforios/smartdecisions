''' Authentication Component '''
import streamlit as st
import requests
from utils.config import AUTH_SERVICE_URL

def require_auth():
    if 'auth_token' not in st.session_state:
        st.session_state['auth_token'] = None

    if st.session_state['auth_token'] is None:
        st.title('🔐 Acceso Sistema de Inteligencia Minera')
        with st.form('login'):
            u = st.text_input('Email')
            p = st.text_input('Password', type='password')
            if st.form_submit_button('Ingresar'):
                try:
                    res = requests.post(f'{AUTH_SERVICE_URL}/login', json={'email': u, 'password': p})
                    if res.status_code == 200:
                        st.session_state['auth_token'] = res.json().get('access_token')
                        st.rerun()
                    else:
                        st.error('Credenciales incorrectas.')
                except Exception as e:
                    st.error(f'Error Auth Service: {e}')
        st.stop()
