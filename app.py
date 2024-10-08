from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for
from neo4j import GraphDatabase
from bs4 import BeautifulSoup
import requests
import re
import os

app = Flask(__name__)

load_dotenv()
# Obtenção das variáveis de ambiente
uri = os.getenv("NEO4J_URI")
username = os.getenv("NEO4J_USERNAME")
password = os.getenv("NEO4J_PASSWORD")
driver = GraphDatabase.driver(uri, auth=(username, password))

# Teste da conexão com o banco Neo4j
with driver.session() as session:
    result = session.run("RETURN 1")
    print(f"Conexão com o Neo4j: {result.single()}")  # Verifica se a conexão está ativa

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    keyword_input = request.form['keyword']
    keywords = extract_keywords(keyword_input)
    keywords = [keyword.strip().lower() for keyword in keywords]  # Converte as palavras-chave para minúsculas
    
    # Verifica se há palavras-chave válidas
    if not keywords:
        print("Nenhuma palavra-chave válida encontrada.")
        return redirect(url_for('index'))  # Redireciona se não houver palavras-chave

    articles = fetch_articles_by_keyword(keyword_input)
    
    if articles:
        insert_articles(articles, keywords)
    else:
        print("Nenhum artigo encontrado para inserção.")
    
    return redirect(url_for('index'))

def extract_keywords(keyword_input):
    # Extrair palavras-chave entre asteriscos (*)
    return re.findall(r'\*(.*?)\*', keyword_input)

def fetch_articles_by_keyword(keyword):
    # Realiza a busca no Google Scholar
    url = f"https://scholar.google.com/scholar?q={keyword}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(url, headers=headers)

    print(f"Status code da resposta: {response.status_code}")

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        articles = []

        for result in soup.find_all('div', class_='gs_ri'):
            title = result.find('h3', class_='gs_rt').text
            title_cleaned = re.sub(r'\[.*?\]', '', title).strip()

            author_info = result.find('div', class_='gs_a').text
            authors = author_info.split(' - ')[0].split(', ')
            authors_cleaned = [author for author in authors if not re.search(r'\d{4}', author)]

            year_match = re.search(r'\d{4}', author_info)
            publication_year = year_match.group(0) if year_match else 'Data não disponível'

            article = {
                'title': title_cleaned,
                'authors': authors_cleaned,
                'publication_year': publication_year
            }
            articles.append(article)
            print(f"Artigo encontrado: {article}")  # Log do artigo encontrado

        return articles
    else:
        print("Erro ao buscar artigos.")
    return []

def insert_article(tx, title, authors, publication_year, keywords):
    print(f"Inserindo artigo: {title}")  # Log para verificar artigo

    # Usar MERGE para evitar duplicação de artigos
    tx.run(
        "MERGE (a:Article {title: $title, publication_year: $publication_year})",
        title=title, publication_year=publication_year
    )
    
    for keyword in keywords:
        print(f"Inserindo palavra-chave: {keyword}")  # Log para verificar palavra-chave
        # Usar MERGE para evitar duplicação de palavras-chave e relacionamentos
        tx.run("MERGE (k:Keyword {name: $keyword})", keyword=keyword)
        tx.run(
            "MATCH (k:Keyword {name: $keyword}), (a:Article {title: $title}) "
            "MERGE (k)-[:RELATED_TO]->(a)", 
            keyword=keyword, title=title
        )
    
    for author in authors:
        print(f"Inserindo autor: {author}")  # Log para verificar autor
        # Usar MERGE para evitar duplicação de autores e relacionamentos
        tx.run("MERGE (au:Author {name: $name})", name=author)
        tx.run(
            "MATCH (a:Article {title: $title}), (au:Author {name: $name}) "
            "MERGE (au)-[:WROTE]->(a)", 
            title=title, name=author
        )

def insert_articles(articles, keywords):
    with driver.session() as session:
        for article in articles:
            session.execute_write(
                insert_article, 
                article['title'], 
                article['authors'], 
                article['publication_year'], 
                keywords
            )

if __name__ == '__main__':
    app.run(debug=True, port=5001)