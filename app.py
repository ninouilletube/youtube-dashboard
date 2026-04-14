import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import json
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import anthropic

st.set_page_config(
    page_title="YouTube Dashboard",
    page_icon="▶",
    layout="wide"
)

st.markdown("""
<style>
[data-testid="stMetricValue"] { font-size: 2rem; }
</style>
""", unsafe_allow_html=True)

if 'youtube' not in st.session_state:
    st.session_state.youtube = None
if 'youtube_analytics' not in st.session_state:
    st.session_state.youtube_analytics = None
if 'credentials' not in st.session_state:
    st.session_state.credentials = None

SCOPES = [
    'https://www.googleapis.com/auth/youtube.readonly',
    'https://www.googleapis.com/auth/yt-analytics.readonly'
]

def get_channel_data():
    youtube = st.session_state.youtube
    response = youtube.channels().list(
        part='snippet,statistics',
        mine=True
    ).execute()
    return response['items'][0]

def get_analytics_data(days=28):
    analytics = st.session_state.youtube_analytics
    aujourd_hui = datetime.today().strftime('%Y-%m-%d')
    debut = (datetime.today() - timedelta(days=days)).strftime('%Y-%m-%d')
    response = analytics.reports().query(
        ids='channel==MINE',
        startDate=debut,
        endDate=aujourd_hui,
        metrics='views,estimatedMinutesWatched,averageViewDuration,subscribersGained,subscribersLost',
        dimensions='day',
        sort='day'
    ).execute()
    return response

def get_top_videos():
    analytics = st.session_state.youtube_analytics
    aujourd_hui = datetime.today().strftime('%Y-%m-%d')
    debut = (datetime.today() - timedelta(days=90)).strftime('%Y-%m-%d')
    response = analytics.reports().query(
        ids='channel==MINE',
        startDate=debut,
        endDate=aujourd_hui,
        metrics='views,estimatedMinutesWatched,averageViewDuration',
        dimensions='video',
        sort='-views',
        maxResults=10
    ).execute()
    return response

def get_traffic_sources():
    analytics = st.session_state.youtube_analytics
    aujourd_hui = datetime.today().strftime('%Y-%m-%d')
    debut = (datetime.today() - timedelta(days=28)).strftime('%Y-%m-%d')
    response = analytics.reports().query(
        ids='channel==MINE',
        startDate=debut,
        endDate=aujourd_hui,
        metrics='views',
        dimensions='insightTrafficSourceType',
        sort='-views'
    ).execute()
    return response

def analyze_with_claude(channel, analytics, top_videos):
    client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
    
    prompt = f"""Tu es un expert en croissance YouTube. Voici les données de la chaîne "{channel['snippet']['title']}" :

STATS GÉNÉRALES :
- Abonnés : {int(channel['statistics']['subscriberCount']):,}
- Vues totales : {int(channel['statistics']['viewCount']):,}
- Vidéos : {channel['statistics']['videoCount']}

28 DERNIERS JOURS :
- Vues : {sum(int(r[1]) for r in analytics['rows']):,}
- Minutes regardées : {sum(int(r[2]) for r in analytics['rows']):,}
- Durée moy. visionnage : {int(analytics['rows'][0][3])} secondes
- Abonnés gagnés : {sum(int(r[4]) for r in analytics['rows']):,}
- Abonnés perdus : {sum(int(r[5]) for r in analytics['rows']):,}

En 3 sections courtes :
1. 🎯 TES ATOUTS (2-3 points)
2. ⚠️ TES FAILLES (2-3 points)  
3. 🚀 TES OBJECTIFS 30 JOURS (3 objectifs concrets et chiffrés)

Sois direct, concret et encourageant."""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text

if st.session_state.youtube is None:
    st.title("▶ YouTube Dashboard")
    st.markdown("### Connecte ta chaîne YouTube")
    
    client_secret = st.file_uploader(
        "Uploade ton fichier JSON Google Cloud",
        type=['json']
    )
    
    if client_secret:
        secret_data = json.load(client_secret)
        with open('client_secret.json', 'w') as f:
            json.dump(secret_data, f)
        
        flow = Flow.from_client_secrets_file(
            'client_secret.json',
            scopes=SCOPES,
            redirect_uri=st.secrets["REDIRECT_URI"]
        )
        
        if 'code' not in st.query_params:
            auth_url, _ = flow.authorization_url(prompt='consent')
            st.link_button("Se connecter avec Google", auth_url)
        else:
            flow.fetch_token(
                authorization_response=f"{st.secrets['REDIRECT_URI']}?code={st.query_params['code']}&state={st.query_params['state']}"
            )
            creds = flow.credentials
            st.session_state.youtube = build('youtube', 'v3', credentials=creds)
            st.session_state.youtube_analytics = build('youtubeAnalytics', 'v2', credentials=creds)
            st.rerun()

else:
    with st.spinner("Chargement de tes données..."):
        channel = get_channel_data()
        analytics = get_analytics_data(28)
        top_videos = get_top_videos()
        traffic = get_traffic_sources()

    nom = channel['snippet']['title']
    abonnes = int(channel['statistics']['subscriberCount'])
    total_vues = int(channel['statistics']['viewCount'])
    nb_videos = int(channel['statistics']['videoCount'])
    
    rows = analytics['rows']
    vues_28j = sum(int(r[1]) for r in rows)
    minutes_28j = sum(int(r[2]) for r in rows)
    duree_moy = int(rows[0][3])
    abonnes_gagnes = sum(int(r[4]) for r in rows)
    abonnes_perdus = sum(int(r[5]) for r in rows)

    st.title(f"▶ {nom}")
    st.caption(f"Mis à jour le {datetime.today().strftime('%d/%m/%Y à %H:%M')}")

    st.markdown("### Vue globale")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Abonnés", f"{abonnes:,}", f"+{abonnes_gagnes - abonnes_perdus} ce mois")
    c2.metric("Vues (28j)", f"{vues_28j:,}")
    c3.metric("Minutes regardées (28j)", f"{minutes_28j:,}")
    c4.metric("Durée moy.", f"{duree_moy//60}min {duree_moy%60}s")

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Vues par jour")
        dates = [r[0] for r in rows]
        vues = [int(r[1]) for r in rows]
        fig = px.area(x=dates, y=vues, labels={'x': '', 'y': 'Vues'})
        fig.update_traces(fill='tozeroy', line_color='#FF0000')
        fig.update_layout(showlegend=False, height=300)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("### Sources de trafic")
        if 'rows' in traffic:
            labels = [r[0] for r in traffic['rows']]
            values = [int(r[1]) for r in traffic['rows']]
            fig2 = px.pie(names=labels, values=values)
            fig2.update_layout(height=300)
            st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")
    st.markdown("### Abonnés : gagnés vs perdus")
    gagnes = [int(r[4]) for r in rows]
    perdus = [-int(r[5]) for r in rows]
    fig3 = go.Figure()
    fig3.add_trace(go.Bar(x=dates, y=gagnes, name='Gagnés', marker_color='#00C851'))
    fig3.add_trace(go.Bar(x=dates, y=perdus, name='Perdus', marker_color='#FF4444'))
    fig3.update_layout(barmode='relative', height=300)
    st.plotly_chart(fig3, use_container_width=True)

    st.markdown("---")
    st.markdown("### Analyse IA de ta chaîne")
    if st.button("Générer l'analyse IA"):
        with st.spinner("Claude analyse ta chaîne..."):
            analyse = analyze_with_claude(channel, analytics, top_videos)
            st.markdown(analyse)

    st.markdown("---")
    st.markdown("### Tes 10 meilleures vidéos (90 jours)")
    if 'rows' in top_videos:
        for i, video in enumerate(top_videos['rows']):
            video_id = video[0]
            vues_v = int(video[1])
            minutes_v = int(video[2])
            duree_v = int(video[3])
            st.markdown(f"**{i+1}.** [Voir la vidéo](https://youtube.com/watch?v={video_id}) — {vues_v:,} vues · {duree_v//60}min{duree_v%60}s moy.")
