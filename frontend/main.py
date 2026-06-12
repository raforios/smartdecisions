'''
    Main function for SmartDecisions frontend APP
'''
import streamlit as st
from layout.menu import menu

st.set_page_config(
    page_title = 'SmartDecisions Dashboard',
    page_icon = '🌐',
    layout = 'wide',
    initial_sidebar_state = 'collapsed',
    menu_items={
        'Get Help': 'mailto:raforios@gmail.com',
        'Report a bug': "mailto:raforios@gmail.com",
        'About': "# SmartDecisions APP. This is an *BETA* version!"
    }
)
def main():
    '''
        Main function Frontend SmartDecisions
    '''

    st.title('SmartDecisions')
    st.header('BI - APP')
    menu()


if __name__ == '__main__':
    main()
